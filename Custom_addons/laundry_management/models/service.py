from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re

class LaundryService(models.Model):
    """Laundry Service generating model"""
    _name = 'laundry.service'
    _description = 'Laundry Service'
    _inherit = ['website.published.mixin']

    name = fields.Char(string='Service Name', required=True, copy=False)
    tagline = fields.Char(string='Tagline', help='Short catchy phrase for the service')
    overview = fields.Text(string='Overview', help='Short description of the service')
    description = fields.Text(string='Description', help='Detailed description of the service')
    image = fields.Image(string='Image', store=True)
    pos_category_id = fields.Many2one('pos.category', string='POS Category', ondelete='restrict', required=True)
    public_categ_id = fields.Many2one('product.public.category', string='Website Category',
                                      help="Category for eCommerce and online orders.", default=False)
    active = fields.Boolean(default=True, help="Set active to false to hide the service without removing it.")
    url = fields.Char(compute='_compute_website_url', store=True, readonly=True)
    
    # One2many relationships for features and benefits
    feature_ids = fields.One2many('laundry.service.feature', 'service_id', string='Features')
    benefit_ids = fields.One2many('laundry.service.benefit', 'service_id', string='Benefits')
    
    # Pricing publication control
    is_pricing_published = fields.Boolean(string='Pricing Published', default=False, 
                                         help='Control whether pricing information is visible to customers')
    pricing_last_updated = fields.Datetime(string='Pricing Last Updated', readonly=True)
    pricing_pending_changes = fields.Boolean(string='Has Pending Changes', compute='_compute_pricing_pending_changes', 
                                            help='Indicates if there are new/updated products not yet published')
    pricing_snapshot_ids = fields.One2many('laundry.service.pricing.snapshot', 'service_id', string='Pricing Snapshots')

    def slugify(self, text):
        if not text:
            return ''
        text = str(text).lower()
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip('-')

    @api.depends('name')
    def _compute_website_url(self):
        for rec in self:
            if rec.name:
                slug = rec.slugify(rec.name)
                rec.url = slug
            else:
                rec.url = ''

    @api.depends('pricing_last_updated', 'pricing_snapshot_ids.has_changes')
    def _compute_pricing_pending_changes(self):
        """Check if there are products with price or name changes since last publication"""
        for rec in self:
            if not rec.pricing_last_updated or not rec.pricing_snapshot_ids:
                # If never published or no snapshots, check if there are any products
                rec.pricing_pending_changes = bool(rec._get_all_pricing_products())
            else:
                # Check if any snapshot shows changes (price or name)
                changed_snapshots = rec.pricing_snapshot_ids.filtered('has_changes')
                
                # Also check for new products not in snapshots
                all_products = rec._get_all_pricing_products()
                snapshot_product_ids = set(rec.pricing_snapshot_ids.mapped('product_id.id'))
                new_products = all_products.filtered(lambda p: p.id not in snapshot_product_ids)
                
                rec.pricing_pending_changes = bool(changed_snapshots or new_products)

    def _get_all_pricing_products(self):
        """Get all products associated with this service's categories"""
        if not self.pos_category_id:
            return self.env['product.product']
        
        all_products = self.env['product.product']
        for category in self.pos_category_id.child_ids:
            products = self.env['product.product'].search([('pos_categ_ids', '=', category.id)])
            all_products |= products
        return all_products

    def action_publish_pricing(self):
        """Publish the current pricing configuration by creating snapshots"""
        self.ensure_one()
        
        # Track changes before clearing snapshots
        old_snapshots = self.pricing_snapshot_ids
        price_changes = old_snapshots.filtered('price_changed')
        name_changes = old_snapshots.filtered('name_changed')
        
        # Clear existing snapshots
        self.pricing_snapshot_ids.unlink()
        
        # Create new snapshots from current product prices and names
        snapshot_vals = []
        category_seq = 10
        
        for category in self.pos_category_id.child_ids:
            products = self.env['product.product'].search([('pos_categ_ids', '=', category.id)])
            if products:
                product_seq = 10
                for product in products:
                    snapshot_vals.append({
                        'service_id': self.id,
                        'category_id': category.id,
                        'category_name': category.name,
                        'category_sequence': category_seq,
                        'product_id': product.id,
                        'product_name': product.name,
                        'published_price': product.lst_price,
                        'product_sequence': product_seq,
                        'snapshot_date': fields.Datetime.now(),
                    })
                    product_seq += 10
                category_seq += 10
        
        # Create all snapshots
        if snapshot_vals:
            self.env['laundry.service.pricing.snapshot'].create(snapshot_vals)
        
        # Update publication status
        self.pricing_last_updated = fields.Datetime.now()
        self.is_pricing_published = True
        
        # Prepare notification message
        changes_info = []
        if price_changes:
            changes_info.append(f"{len(price_changes)} price changes")
        if name_changes:
            changes_info.append(f"{len(name_changes)} name changes")
        
        changes_text = " and ".join(changes_info) if changes_info else "no pending changes"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_context',
            'params': {
                'field_names': ['is_pricing_published', 'pricing_pending_changes', 'pricing_last_updated', 'pricing_snapshot_ids']
            }
        }

    def action_unpublish_pricing(self):
        """Unpublish the pricing (remove from customer view)"""
        self.ensure_one()
        self.is_pricing_published = False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_context',
            'params': {
                'field_names': ['is_pricing_published', 'pricing_pending_changes']
            }
        }

    def action_preview_pricing(self):
        """Preview the pricing as customers would see it"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/laundry/pricing_preview/{self.id}',
            'target': 'new',
        }

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Service name must be unique.'),
        ('unique_pos_category', 'unique(pos_category_id)', 'This POS category is already linked to another service.'),
        ('unique_website_url', 'unique(website_url)', 'Website URL (slug) must be unique.')

    ]
    @api.constrains('pos_category_id')
    def _check_pos_category_is_top_level(self):
        for rec in self:
            if rec.pos_category_id and rec.pos_category_id.parent_id:
                raise ValidationError("POS category must be top-level (no parent category).")

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('name', f"{self.name} (Copy)")
        default.setdefault('pos_category_id', False)
        return super().copy(default)


class LaundryServiceFeature(models.Model):
    """Service Features - Simple list of feature names"""
    _name = 'laundry.service.feature'
    _description = 'Service Feature'
    _order = 'sequence, id'

    service_id = fields.Many2one('laundry.service', string='Service', required=True, ondelete='cascade')
    name = fields.Char(string='Feature', required=True, help='Feature name (e.g., "Express Service", "Eco-Friendly")')
    sequence = fields.Integer(string='Sequence', default=10, help='Order of appearance')


class LaundryServiceBenefit(models.Model):
    """Service Benefits - Name with detailed description"""
    _name = 'laundry.service.benefit'
    _description = 'Service Benefit'
    _order = 'sequence, id'

    service_id = fields.Many2one('laundry.service', string='Service', required=True, ondelete='cascade')
    name = fields.Char(string='Benefit', required=True, help='Benefit name (e.g., "Save Time", "Professional Results")')
    description = fields.Text(string='Description', help='Detailed explanation of the benefit')
    sequence = fields.Integer(string='Sequence', default=10, help='Order of appearance')


class LaundryServicePricingSnapshot(models.Model):
    product_active = fields.Boolean(string='Product Active', compute='_compute_product_active', store=True)

    @api.depends('product_id.active')
    def _compute_product_active(self):
        for record in self:
            record.product_active = record.product_id.active if record.product_id else False
    """Snapshot of pricing data for published display"""
    _name = 'laundry.service.pricing.snapshot'
    _description = 'Service Pricing Snapshot'
    _order = 'service_id, category_sequence, product_sequence'

    service_id = fields.Many2one('laundry.service', string='Service', required=True, ondelete='cascade')
    category_id = fields.Many2one('pos.category', string='Category', required=True)
    category_name = fields.Char(string='Category Name', required=True)
    category_sequence = fields.Integer(string='Category Order', default=10)
    
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_name = fields.Char(string='Product Name', required=True)
    published_price = fields.Float(string='Published Price', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency', store=True)
    current_price = fields.Float(string='Current Product Price', compute='_compute_current_price')
    current_name = fields.Char(string='Current Product Name', compute='_compute_current_name')
    price_changed = fields.Boolean(string='Price Changed', compute='_compute_changes')
    name_changed = fields.Boolean(string='Name Changed', compute='_compute_changes')
    has_changes = fields.Boolean(string='Has Changes', compute='_compute_changes')
    product_sequence = fields.Integer(string='Product Order', default=10)
    
    snapshot_date = fields.Datetime(string='Snapshot Date', default=fields.Datetime.now)

    @api.depends('product_id.lst_price')
    def _compute_current_price(self):
        for record in self:
            record.current_price = record.product_id.lst_price if record.product_id else 0.0

    @api.depends('product_id.name')
    def _compute_current_name(self):
        for record in self:
            record.current_name = record.product_id.name if record.product_id else ''

    @api.depends('product_id.currency_id')
    def _compute_currency(self):
        for record in self:
            # Try to get currency from product, fallback to company currency
            if record.product_id and record.product_id.currency_id:
                record.currency_id = record.product_id.currency_id
            else:
                record.currency_id = self.env.company.currency_id

    @api.depends('published_price', 'current_price', 'product_name', 'current_name')
    def _compute_changes(self):
        for record in self:
            record.price_changed = abs(record.published_price - record.current_price) > 0.01
            record.name_changed = record.product_name != record.current_name
            record.has_changes = record.price_changed or record.name_changed