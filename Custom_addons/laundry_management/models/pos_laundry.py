from odoo import fields, models, api, _
from odoo.exceptions import ValidationError  # Add this import
from datetime import datetime

class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    # Keep this field to support category-based washing types
    default_washing_type_id = fields.Many2one('washing.type', string='Default Washing Type',
                                            help='Default washing type for products in this category')

class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    # Override partner_id to make it required
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    
    laundry_order_id = fields.Many2one('laundry.order', string='Laundry Order',
                                      readonly=True, copy=False)
    @api.model_create_multi

    def create(self, vals_list):

        for vals in vals_list:

            if not vals.get('partner_id'):

                raise ValidationError("Customer must be selected before placing the order.")

        return super().create(vals_list)
 
    
    # Create laundry order after POS order is confirmed
    def action_pos_order_paid(self):
        result = super(PosOrder, self).action_pos_order_paid()
        # Create laundry order automatically for all paid POS orders
        self._process_laundry_order()
        return result
    
    def _process_laundry_order(self):
        """Create a laundry order based on the POS order"""
        LaundryOrder = self.env['laundry.order']
        LaundryOrderLine = self.env['laundry.order.line']
        WashingType = self.env['washing.type']
        
        # Skip if this order already has a laundry order
        if self.laundry_order_id:
            return False
            
        # Create laundry order with company_id
        laundry_order_vals = {
            'partner_id': self.partner_id.id,
            'partner_invoice_id': self.partner_id.id,
            'partner_shipping_id': self.partner_id.id,
            'order_date': fields.Datetime.now(),
            'laundry_person_id': self.env.user.id,
            'state': 'draft',
            'company_id': self.company_id.id,  # Add company_id
        }
        
        laundry_order = LaundryOrder.create(laundry_order_vals)
        
        # Create laundry order lines for ALL products in the POS order
        order_lines_created = False
        for line in self.lines:
            product = line.product_id
            
            # Get POS category from product
            pos_category = False
            if hasattr(product, 'pos_categ_ids') and product.pos_categ_ids:
                pos_category = product.pos_categ_ids[0] if product.pos_categ_ids else False
            
            # Get category name 
            if pos_category:
                categ_name = pos_category.name
            elif product.categ_id:
                categ_name = product.categ_id.name
            else:
                categ_name = 'Others'
            
            # Find or create washing type
            washing_type = WashingType.search([('name', '=', categ_name)], limit=1)
            if not washing_type:
                washing_type = WashingType.with_context(create_from_pos=True).create({
                    'name': categ_name,
                    'assigned_person_id': self.env.user.id,
                })
            
            # Get tax information from product
            taxes = line.tax_ids or product.taxes_id
            
            # Create laundry order line with tax info
            laundry_line = LaundryOrderLine.create({
                'laundry_id': laundry_order.id,
                'product_id': product.id,
                'qty': line.qty,
                'description': product.name,
                'washing_type_id': washing_type.id,
                'price_unit': line.price_unit,
                'tax_id': [(6, 0, taxes.ids)] if taxes else False,
            })
            
            order_lines_created = True
    
        # If no lines were created, delete the laundry order
        if not order_lines_created:
            laundry_order.unlink()
            return False
        
        # Link the laundry order to the POS order
        self.write({'laundry_order_id': laundry_order.id})
        
        return laundry_order

    def _get_washing_type_from_category_hierarchy(self, category, default_washing_type_id):
        """
        Get washing type by traversing up the product category hierarchy.
        If no washing type is found in the category or its parents, return the default.
        """
        if not category:
            return default_washing_type_id
        
        # Check if current category has a washing type
        if category.default_washing_type_id:
            return category.default_washing_type_id.id
        
        # If not, check parent category recursively
        if category.parent_id:
            return self._get_washing_type_from_category_hierarchy(category.parent_id, default_washing_type_id)
        
        # If no washing type found in hierarchy, return default
        return default_washing_type_id

    def _process_payment_lines(self, pos_order, order, pos_session, draft):
        """Extend to create laundry orders after payment processing"""
        res = super(PosOrder, self)._process_payment_lines(pos_order, order, pos_session, draft)
        # Create laundry order
        if not draft:
            order._process_laundry_order()
        return res

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'
    
    washing_type_id = fields.Many2one('washing.type', string='Washing Type')

    @api.depends('washing_type_id', 'extra_work_ids', 'qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """Compute the total amount including taxes"""
        for line in self:
            # If price_unit is set (from POS), use it, otherwise use washing_type amount
            if line.price_unit and line.price_unit > 0:
                base_price = line.price_unit
            else:
                base_price = line.washing_type_id.amount if line.washing_type_id else 0.0
                
            # Calculate subtotal before tax
            subtotal = base_price * line.qty
            
            # Add extra work costs
            if line.extra_work_ids:
                for work in line.extra_work_ids:
                    subtotal += work.amount * line.qty
            
            # Apply taxes (simple percentage calculation)
            if line.tax_id:
                tax_amount = 0
                for tax in line.tax_id:
                    if tax.amount_type == 'percent':
                        tax_amount += subtotal * (tax.amount / 100.0)
                line.amount = subtotal + tax_amount
            else:
                line.amount = subtotal
      
class PosSession(models.Model):
    _inherit = 'pos.session'
    
    def _pos_data_process(self, loaded_data):
        """Add product laundry flag to loaded data"""
        super()._pos_data_process(loaded_data)
        
        if 'product.product' in loaded_data:
            products = loaded_data['product.product']
            product_ids = [p['id'] for p in products]
            product_laundry_items = self.env['product.product'].search_read(
                [('id', 'in', product_ids)],
                ['id', 'is_laundry_item']
            )
            laundry_dict = {item['id']: item['is_laundry_item'] for item in product_laundry_items}
            
            for product in products:
                product['is_laundry_item'] = laundry_dict.get(product['id'], False)

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    def get_pos_category_name(self):
        """Get the POS category name for this product"""
        self.ensure_one()
        if hasattr(self, 'pos_category_id') and self.pos_category_id:
            return self.pos_category_id.name
        elif self.categ_id:
            return self.categ_id.name
        return 'Others'