from odoo import models, fields, api
from datetime import datetime


class LaundryPickupRequest(models.Model):
    _name = 'laundry.pickup.request'
    _description = 'Laundry Pickup Request'
    _order = 'create_date desc'
    _inherit = ['mail.thread']
    _rec_name = 'reference'

    reference = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    name = fields.Char(string='Customer Name', required=True, tracking=True)
    email = fields.Char(string='Email', required=True)
    pickup_street = fields.Char(string='Street Address', required=True)
    pickup_city = fields.Char(string='City', required=True)
    pickup_state = fields.Char(string='State', required=True)
    pickup_zip = fields.Char(string='Zip Code', required=True)
    pickup_country = fields.Char(string='Country', required=True)
    landmark = fields.Char(string='Landmark')
    phone = fields.Char(string='Phone Number', required=True)
    
    # Simple status tracking
    state = fields.Selection([
        ('new', 'New Request'),
        ('contacted', 'Customer Contacted'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', tracking=True)
    
    # Basic notes field for staff
    notes = fields.Text(string='Notes')
    
    # Customer relation

    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    customer_exists = fields.Boolean(string='Customer Exists', compute='_compute_customer_exists')
    phone_mismatch = fields.Boolean(string='Phone Number Mismatch', default=False, help='Set to True if phone number differs from existing customer record.')
    

    def _find_partner_and_mismatch(self, email, phone):
        """Helper to find partner by email only, and detect phone mismatch. Ignore phone-only matches."""
        partner = False
        phone_mismatch = False
        if email:
            partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
            if partner:
                if phone and partner.phone and phone != partner.phone:
                    phone_mismatch = True
        return partner, phone_mismatch

    @api.depends('email', 'phone')
    def _compute_customer_exists(self):
        for record in self:
            partner, phone_mismatch = record._find_partner_and_mismatch(record.email, record.phone)
            record.customer_exists = bool(partner)
            record.partner_id = partner
            record.phone_mismatch = phone_mismatch
    

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence and check customer existence by email/phone, notify if phone mismatch"""
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('laundry.pickup.request') or 'New'

        records = super().create(vals_list)
        for record in records:
            partner, phone_mismatch = record._find_partner_and_mismatch(record.email, record.phone)
            record.customer_exists = bool(partner)
            record.partner_id = partner
            record.phone_mismatch = phone_mismatch
            # If customer exists, update their address with the new pickup address fields
            if partner:
                if record.pickup_street:
                    partner.street = record.pickup_street
                if record.pickup_city:
                    partner.city = record.pickup_city
                if record.pickup_state:
                    partner.state_id = False
                    state_obj = record.env['res.country.state'].search([('name', '=', record.pickup_state)], limit=1)
                    if state_obj:
                        partner.state_id = state_obj.id
                if record.pickup_zip:
                    partner.zip = record.pickup_zip
                if record.pickup_country:
                    partner.country_id = False
                    country_obj = record.env['res.country'].search([('name', '=', record.pickup_country)], limit=1)
                    if country_obj:
                        partner.country_id = country_obj.id
            if phone_mismatch:
                record.message_post(
                    body=(
                        f"<b>Phone Number Mismatch:</b> The phone number provided ({record.phone}) does not match the one on file for this customer ({partner.phone}). "
                        "Please confirm the correct phone number with the customer."
                    ),
                    message_type='notification',
                )
        return records

    def action_update_customer_phone(self):
        """Action to update the linked customer's phone number to the new one from the request."""
        for rec in self:
            if rec.partner_id and rec.phone_mismatch:
                rec.partner_id.phone = rec.phone
                rec.phone_mismatch = False
                rec.message_post(body=f"Customer phone number updated to {rec.phone} by {self.env.user.name}")
    
    def action_mark_contacted(self):
        """Simple action to mark as contacted"""
        self.state = 'contacted'
        self.message_post(body=f"Customer contacted by {self.env.user.name}")
        
        # Check if customer exists
        self._compute_customer_exists()
    
    def action_mark_completed(self):
        """Mark as completed"""
        self.state = 'completed'
        self.message_post(body=f"Request completed by {self.env.user.name}")
    
    def action_mark_cancelled(self):
        """Mark as cancelled"""
        self.state = 'cancelled'
        self.message_post(body=f"Request cancelled by {self.env.user.name}")
    
    def action_create_customer(self):
        """Create customer from pickup request and reload the form view."""
        if self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Customer Already Exists',
                    'message': f'Customer {self.name} already exists in contacts.',
                    'type': 'warning'
                }
            }

        # Create new customer using structured address fields
        partner_vals = {
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'street': self.pickup_street,
            'city': self.pickup_city,
            'zip': self.pickup_zip,
            'is_company': False,
            'customer_rank': 1,
        }
        # Set country and state if found
        if self.pickup_country:
            country_obj = self.env['res.country'].search([('name', '=', self.pickup_country)], limit=1)
            if country_obj:
                partner_vals['country_id'] = country_obj.id
        if self.pickup_state:
            state_obj = self.env['res.country.state'].search([('name', '=', self.pickup_state)], limit=1)
            if state_obj:
                partner_vals['state_id'] = state_obj.id

        partner = self.env['res.partner'].create(partner_vals)
        self.partner_id = partner.id

        self.message_post(body=f"Customer {self.name} created and linked by {self.env.user.name}")

        # Reload the form view after customer creation
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'laundry.pickup.request',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_create_pos_order(self):
        """Open POS with customer pre-selected via URL parameter"""
        if not self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Customer Linked',
                    'message': 'Please create the customer first before creating a POS order.',
                    'type': 'warning'
                }
            }
        
        # Find the POS config (use the first active one)
        pos_config = self.env['pos.config'].search([('current_session_state', '!=', 'closed')], limit=1)
        if not pos_config:
            pos_config = self.env['pos.config'].search([], limit=1)
        
        if not pos_config:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No POS Configuration',
                    'message': 'No POS configuration found. Please set up POS first.',
                    'type': 'warning'
                }
            }
        
        # Ensure there's an active session
        if not pos_config.current_session_id:
            self.env['pos.session'].create({'user_id': self.env.uid, 'config_id': pos_config.id})
        
        # Construct POS URL with partner_id parameter (JavaScript will handle it)
        path = '/pos/web' if pos_config._force_http() else '/pos/ui'
        pos_url = f"{path}?config_id={pos_config.id}&partner_id={self.partner_id.id}&from_pickup_request=true"
        
        return {
            'type': 'ir.actions.act_url',
            'url': pos_url,
            'target': 'self',
        }
    
    def action_open_pos_for_customer(self):
        """Alternative method - open customer form"""
        if not self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Customer Linked',
                    'message': 'Please create the customer first.',
                    'type': 'warning'
                }
            }
        
        # Open customer form
        return {
            'type': 'ir.actions.act_window',
            'name': f'Customer: {self.partner_id.name}',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
