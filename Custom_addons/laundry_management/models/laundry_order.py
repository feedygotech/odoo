# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Ammu Raj (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from datetime import datetime
from odoo import api, Command, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class LaundryOrder(models.Model):
    """laundry orders generating model"""
    _name = 'laundry.order'
    _inherit = 'mail.thread'
    _description = "Laundry Order"
    _order = 'order_date desc, id desc'

    name = fields.Char(string="Label", copy=False, help="Name of the record")
    sale_id = fields.Many2one('sale.order',
                              help="sequence name of sale order")
    invoice_status = fields.Selection(string='Invoice Status', related='sale_id.invoice_status',
        store=True, help="Status of invoice")
    invoice_count = fields.Integer(compute='_compute_invoice_count',
                                   string='#Invoice',
                                   help="Number of invoice count")
    work_count = fields.Integer(compute='_compute_work_count', string='# Works',
                                help="Number of work count")
    partner_id = fields.Many2one('res.partner', string='Customer',
                                 readonly=True,
                                 required=True,
                                 change_default=True, index=True,
                                 help="Name of customer"
                                 )
    partner_invoice_id = fields.Many2one('res.partner',
                                         string='Invoice Address',
                                         readonly=True, required=True,
                                         help="Invoice address for current"
                                              "sales order.")
    partner_shipping_id = fields.Many2one('res.partner',
                                          string='Delivery Address',
                                          readonly=True, required=True,
                                          help="Delivery address for current"
                                               "sales order.")
    order_date = fields.Datetime(string='Date', readonly=True, index=True,
                                 copy=False, default=fields.Datetime.now,
                                 help="Date of order")
    laundry_person_id = fields.Many2one('res.users', string='Laundry Person',
                                        required=True,
                                        help="Name of laundry person")
    order_line_ids = fields.One2many('laundry.order.line', 'laundry_id',
                                     required=True, ondelete='cascade',
                                     help="Order lines of laundry orders")
    total_amount = fields.Float(compute='_compute_total_amount', string='Total',
                                store=True,
                                help="To get the Total amount")
    currency_id = fields.Many2one("res.currency", string="Currency",
                                  readonly="state != 'draft'",
                                  default=lambda self: self.env.company.currency_id,
                                  help="Currency used for this order")
    note = fields.Text(string='Terms and conditions',
                       help='Add terms and conditions')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('order', 'Laundry Order'),
        ('process', 'Processing'),
        ('done', 'Done'),
        ('return', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True,
        track_visibility='onchange', default='draft', help="State of the Order")
    company_id = fields.Many2one('res.company', string='Company',
                               default=lambda self: self.env.company,
                               required=True)
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, 
                                     compute='_compute_amount', tracking=True)
    amount_tax = fields.Monetary(string='Taxes', store=True, 
                                compute='_compute_amount', tracking=True)
    amount_total = fields.Monetary(string='Total', store=True, 
                                  compute='_compute_amount', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Creating the record of Laundry order."""
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('laundry.order')
        return super().create(vals_list)

    # Update the _compute_total_amount method to use the amounts calculated by _compute_amount
    @api.depends('amount_untaxed', 'amount_tax')
    def _compute_total_amount(self):
        """Computing the total of total_amount for compatibility with existing references."""
        for order in self:
            # Use the tax-inclusive amount
            order.total_amount = order.amount_total

    def confirm_order(self):
        """Confirming the order and after confirming order,it will create the washing model"""
        self.state = 'order'
        product_id = self.env.ref('laundry_management.product_product_laundry_service')
        
        # Get all unique tax IDs from order lines
        tax_ids = []
        for line in self.order_line_ids:
            for tax in line.tax_id:
                if tax.id not in tax_ids:
                    tax_ids.append(tax.id)
        
        # Create sale order with tax information
        self.sale_id = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'partner_invoice_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'user_id': self.laundry_person_id.id,
            'order_line': [Command.create({
                'product_id': product_id.id,
                'name': 'Laundry Service',
                'price_unit': self.amount_untaxed,  # Use untaxed amount as base price
                'tax_id': [(6, 0, tax_ids)] if tax_ids else False,  # Add tax information
            })]
        })
        
        # Rest of the method remains the same
        for order in self:
            for line in order.order_line_ids:
                self.env['washing.washing'].create({
                    'name': line.product_id.name + '-Washing',
                    'user_id': line.washing_type_id.assigned_person_id.id,
                    'description': line.description,
                    'laundry_id': line.id,
                    'state': 'draft',
                    'washing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

    def action_create_invoice(self):
        """Creating a new invoice for the laundry orders."""
        if self.sale_id.state in ['draft', 'sent']:
            self.sale_id.action_confirm()
        self.invoice_status = self.sale_id.invoice_status
        return {
            'name': 'Create Invoice',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.advance.payment.inv',
            'type': 'ir.actions.act_window',
            'context': {'laundry_sale_id': self.sale_id.id},
            'target': 'new'
        }

    def action_return_dress(self):
        """Return dress after laundry"""
        self.state = 'return'

    def action_cancel_order(self):
        """Cancel the laundry order"""
        self.state = 'cancel'

    def _compute_invoice_count(self):
        """Compute the invoice count."""
        for order in self:
            order.invoice_count = len(order.env['account.move'].search(
                [('invoice_origin', '=', order.sale_id.name)]))

    def _compute_work_count(self):
        """Computing the work count"""
        if self.id:
            wrk_ordr_ids = self.env['washing.washing'].search(
                [('laundry_id.laundry_id.id', '=', self.id)])
            self.work_count = len(wrk_ordr_ids)
        else:
            self.work_count = False

    def action_view_laundry_works(self):
        """Function for viewing the laundry works."""
        work_obj = self.env['washing.washing'].search(
            [('laundry_id.laundry_id.id', '=', self.id)])
        work_ids = []
        for each in work_obj:
            work_ids.append(each.id)
        view_id = self.env.ref('laundry_management.washing_washing_view_form').id
        if work_ids:
            if len(work_ids) <= 1:
                value = {
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'washing.washing',
                    'view_id': view_id,
                    'type': 'ir.actions.act_window',
                    'name': _('Works'),
                    'res_id': work_ids and work_ids[0]
                }
            else:
                value = {
                    'domain': str([('id', 'in', work_ids)]),
                    'view_type': 'form',
                    'view_mode': 'list,form',
                    'res_model': 'washing.washing',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'name': _('Works'),
                }
            return value

    def action_view_invoice(self):
        """Function for viewing Laundry orders invoices."""
        self.ensure_one()
        inv_ids = []
        for each in self.env['account.move'].search(
                [('invoice_origin', '=', self.sale_id.name)]):
            inv_ids.append(each.id)
        if inv_ids:
            if len(inv_ids) <= 1:
                value = {
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'view_id': self.env.ref('account.view_move_form').id,
                    'type': 'ir.actions.act_window',
                    'name': _('Invoice'),
                    'res_id': inv_ids and inv_ids[0]
                }
            else:
                value = {
                    'domain': str([('id', 'in', inv_ids)]),
                    'view_type': 'form',
                    'view_mode': 'list,form',
                    'res_model': 'account.move',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'name': _('Invoice'),
                }
            return value

    @api.depends('order_line_ids.amount')
    def _compute_amount(self):
        """Compute the amounts of the Laundry order."""
        for order in self:
            # Use the amounts from the lines which already include tax calculations
            order_lines = order.order_line_ids
            
            # Get the untaxed amounts from each line
            amount_untaxed = sum(line.amount / (1 + sum(tax.amount / 100 for tax in line.tax_id)) 
                                 if line.tax_id else line.amount 
                                 for line in order_lines)
            
            # Total is the sum of all line amounts (which already include taxes)
            amount_total = sum(line.amount for line in order_lines)
            
            # Tax is the difference
            amount_tax = amount_total - amount_untaxed
            
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_total,
            })


class LaundryOrderLine(models.Model):
    """Laundry order lines generating model"""
    _name = 'laundry.order.line'
    _description = "Laundry Order Line"

    product_id = fields.Many2one('product.product', string='Dress',
                                 required=True, help="Name of the product")
    qty = fields.Integer(string='No of items', required=True,
                         help="Number of quantity")
    description = fields.Text(string='Description',
                              help='Description of the line.')
    washing_type_id = fields.Many2one('washing.type', string='Washing Type',
                                      required=True,
                                      help='Select the type of wash')
    extra_work_ids = fields.Many2many('washing.work', string='Extra Work',
                                      help='Add if any extra works')
    amount = fields.Float(compute='_compute_amount', string='Amount',
                          help='Total amount of the line.')
    laundry_id = fields.Many2one('laundry.order', string='Laundry Order',
                                 help='Corresponding laundry order')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('wash', 'Washing'),
        ('extra_work', 'Make Over'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status of the line', readonly=True, copy=False, index=True,
        default='draft')
    price_unit = fields.Float(string='Unit Price', digits='Product Price', store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes')

    @api.depends('washing_type_id', 'qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """Compute the amount including taxes"""
        for line in self:
            # Calculate base price
            if line.price_unit and line.price_unit > 0:
                base_price = line.price_unit * line.qty
            else:
                base_price = (line.washing_type_id.amount if line.washing_type_id else 0.0) * line.qty
            
            # Calculate tax amount
            tax_amount = 0.0
            if line.tax_id:
                for tax in line.tax_id:
                    if tax.amount_type == 'percent':
                        tax_amount += base_price * (tax.amount / 100.0)
            
            # Set amount INCLUDING tax
            line.amount = base_price + tax_amount

    @api.depends('product_id', 'qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """Compute the total amount with taxes"""
        for line in self:
            # Determine the price to use
            if line.price_unit and line.price_unit > 0:
                price_unit = line.price_unit
            else:
                price_unit = line.product_id.list_price or (line.washing_type_id.amount if line.washing_type_id else 0.0)
                
            quantity = line.qty or 0
            
            # Use the tax computation engine
            if line.tax_id:
                taxes = line.tax_id.compute_all(
                    price_unit,
                    quantity=quantity,
                    product=line.product_id,
                    partner=line.laundry_id.partner_id
                )
                line.amount = taxes['total_included']
            else:
                line.amount = price_unit * quantity
