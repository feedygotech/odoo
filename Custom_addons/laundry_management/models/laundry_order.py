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
from odoo.exceptions import ValidationError
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
                                  help="Name of currency")
    note = fields.Text(string='Terms and conditions',
                       help='Add terms and conditions')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('order', 'Laundry Order'),
        ('process', 'Processing'),
        ('done', 'Done'),
        ('delivery', 'Delivered'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True,
        tracking=True, default='draft', help="State of the Order")
    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Creating the record of Laundry order."""
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('laundry.order')
        return super().create(vals_list)

    @api.depends('order_line_ids')
    def _compute_total_amount(self):
        """Computing the total of total_amount in order lines."""
        for order in self:
            order.total_amount = sum(line.amount for line in order.order_line_ids)

    def confirm_order(self):
        """Confirming the order and creating work records for each order line."""
        self.state = 'order'
        order_lines = []
        for line in self.order_line_ids:
            order_lines.append(Command.create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty,
                'price_unit': line.product_id.list_price,
            }))
        self.sale_id = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'partner_invoice_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'user_id': self.laundry_person_id.id,
            'order_line': order_lines
             })

        for order in self:
            for line in order.order_line_ids:
                self.env['washing.washing'].create({
                    'name': line.product_id.name + ' Work',
                    'description': line.description,
                    'laundry_id': line.id,
                    'user_id': order.laundry_person_id.id,
                    'state': 'draft',
                    'washing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })

    def action_create_invoice(self):
        """Only create invoice if not already invoiced via POS."""
        _logger.info("sale")
        if self.sale_id.state in ['draft', 'sent']:
            self.sale_id.action_confirm()
        self.invoice_status = self.sale_id.invoice_status
        return {
            'name': 'Create Invoice',
            'view_mode': 'form',
            'res_model': 'sale.advance.payment.inv',
            'type': 'ir.actions.act_window',
            'context': {'laundry_sale_id': self.sale_id.id},
            'target': 'new'
        }

    def action_delivery_order(self):
        """Deliver order after laundry completion"""
        self.state = 'delivery'

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
        works = self.env['washing.washing'].search([
            ('laundry_id.laundry_id.id', '=', self.id)
        ])
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'washing.washing',
            'name': _('Works'),
        }
        if len(works) == 1:
            action.update({'view_mode': 'form', 'res_id': works.id})
        else:
            action.update({'view_mode': 'list,form', 'domain': [('id', 'in', works.ids)]})
        return action

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

class LaundryOrderLine(models.Model):
    """Laundry order lines generating model"""
    _name = 'laundry.order.line'
    _description = "Laundry Order Line"
    
    product_id = fields.Many2one('product.product', string='Product', required=True, help="Name of the product")
    service_id = fields.Many2one('laundry.service', string='Service', help='Laundry service type', readonly=True)
    qty = fields.Integer(string='Quantity', required=True, help="Number of items")
    description = fields.Text(string='Description', help='Description of the line.')
    tax_ids = fields.Many2many('account.tax', string='Taxes', related='product_id.taxes_id', readonly=True)
    amount = fields.Float(compute='_compute_amount', string='Amount',
                          help='Total amount of the line.')
    laundry_id = fields.Many2one('laundry.order', string='Laundry Order',
                                 help='Corresponding laundry order')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('wash', 'Washing'),
        ('process', 'Processing'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', help="State of the Order Line")

    @api.depends('product_id', 'qty')
    def _compute_amount(self):
        """Compute the total amount"""
        for line in self:
            price_unit = line.product_id.list_price or 0.0
            quantity =  line.qty or 0
            taxes = line.tax_ids.compute_all(price_unit, quantity=quantity) if line.tax_ids else {'total_included': price_unit * quantity}
            line.amount = taxes['total_included']

    @api.onchange('product_id')
    def _onchange_product_id_set_service(self):
        if self.product_id and not self.service_id:
            pos_categories = self.product_id.pos_categ_ids
            if pos_categories:
                # Find the top-level parent category
                top_category = pos_categories[0]
                while top_category.parent_id:
                    top_category = top_category.parent_id

                # Search for an existing service
                    service = self.env['laundry.service'].search([
                    ('pos_category_id', '=', top_category.id)
                ], limit=1)

                # If no service exists, create one
                if not service:
                    # Also find a matching public category for website sales
                    public_category = self.env['product.public.category'].search([
                        ('name', '=', top_category.name)
                    ], limit=1)
                    service_vals = {
                        'name': top_category.name,
                        'pos_category_id': top_category.id,
                    }
                    if public_category:
                        service_vals['public_categ_id'] = public_category.id

                    service = self.env['laundry.service'].create(service_vals)

                self.service_id = service.id

    def _onchange_product_id_set_taxes(self):
        if self.product_id:
            self.tax_ids = self.product_id.taxes_id