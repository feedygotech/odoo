import logging
_logger = logging.getLogger(__name__)
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class PosOrder(models.Model):
    _inherit = 'pos.order'

    laundry_order_id = fields.Many2one('laundry.order', string='Laundry Order', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('partner_id'):
                raise ValidationError("Customer must be selected before placing the order.")
        return super().create(vals_list)

    @property
    def _prepare_laundry_order_values(self):
        """Prepare values for creating laundry order from POS order"""
        laundry_lines = []

        for line in self.lines:
            service = self._find_or_create_service_from_product(line.product_id)
            laundry_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'qty': line.qty,
                'description': f"POS Order: {self.name}",
                'service_id': service.id if service else False,
                'tax_ids': [(6, 0, [line.tax_ids.ids])],
                'amount': line.price_subtotal_incl
            }))
        return {
            'partner_id': self.partner_id.id,
            'partner_invoice_id': self.partner_id.id,
            'partner_shipping_id': self.partner_id.id,
            'laundry_person_id': self.env.user.id,
            'order_line_ids': laundry_lines,
            'currency_id': self.currency_id.id,
            'state': 'draft',
            'total_amount': self.amount_total,
            'pos_order_id': self.id,
        }

    def _find_or_create_service_from_product(self, product):
        """Returns matching laundry.service or creates one based on POS category"""
        pos_category = product.pos_categ_ids
        parent_category = pos_category.parent_id if pos_category else None
        if not parent_category:
            return False

        service = self.env['laundry.service'].search([
            ('pos_category_id', '=', parent_category.id)
        ], limit=1)

        if not service:
            service = self.env['laundry.service'].create({
                'name': parent_category.name,
                'pos_category_id': parent_category.id
            })
        return service

    def create_laundry_order(self):
        """Create laundry order from POS order"""
        LaundryOrder = self.env['laundry.order']
        for order in self:
            if not order.laundry_order_id and order.partner_id:
                values = order._prepare_laundry_order_values
                laundry_order = LaundryOrder.create(values)
                order.laundry_order_id = laundry_order.id
        return True

    def write(self, vals):
        """Ensure laundry order is updated or created if partner is changed"""
        res = super().write(vals)
        if 'partner_id' in vals:
            for order in self:
                if order.laundry_order_id:
                    # Update customer fields on existing laundry order
                    order.laundry_order_id.partner_id = order.partner_id
                    order.laundry_order_id.partner_invoice_id = order.partner_id
                    order.laundry_order_id.partner_shipping_id = order.partner_id
                elif order.partner_id and order.state == 'paid':
                    # If paid and laundry order doesn't exist, create it
                    order.create_laundry_order()
        return res

    def action_pos_order_paid(self):
        """Inherit to create laundry order when POS order is paid"""
        res = super().action_pos_order_paid()
        self.create_laundry_order()
        return res