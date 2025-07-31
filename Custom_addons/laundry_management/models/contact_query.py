# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class LaundryContactQuery(models.Model):
    """Contact Query Model for Laundry Management"""
    _name = 'laundry.contact.query'
    _description = 'Customer Contact Queries'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'reference'

    reference = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    name = fields.Char(string='Customer Name', required=True, help='Full name of the customer')
    phone = fields.Char(string='Phone Number', required=True, help='Contact phone number')
    email = fields.Char(string='Email Address', required=True, help='Customer email address')
    subject = fields.Char(string='Subject', required=True, help='Query subject/topic')
    message = fields.Text(string='Message', required=True, help='Detailed message from customer')
    
    # Additional fields for better management
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string='Status', default='new', tracking=True, help='Query status')
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'), 
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Priority', default='normal', tracking=True)
    
    assigned_to = fields.Many2one('res.users', string='Assigned To', tracking=True, help='Staff member assigned to handle this query')
    response = fields.Text(string='Response', help='Response to customer query')
    response_date = fields.Datetime(string='Response Date', readonly=True)
    
    # Computed fields
    days_since_received = fields.Integer(string='Days Since Received', compute='_compute_days_since_received')
    
    # Customer relation (optional - if customer exists in system)
    partner_id = fields.Many2one('res.partner', string='Related Customer', help='Link to existing customer if found')
    
    @api.depends('create_date')
    def _compute_days_since_received(self):
        for record in self:
            if record.create_date:
                delta = datetime.now() - record.create_date.replace(tzinfo=None)
                record.days_since_received = delta.days
            else:
                record.days_since_received = 0
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence, try linking existing customer and send confirmation email"""
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('laundry.contact.query') or 'New'
        
        queries = super().create(vals_list)
        
        # Process each query for customer linking and email
        for query in queries:
            self._process_new_query(query)
        
        return queries
    
    def _process_new_query(self, query):
        """Process a newly created query for customer linking and email"""
        
        # Try to find existing customer by email or phone
        if query.email:
            partner = self.env['res.partner'].search([
                ('email', '=', query.email)
            ], limit=1)
            if partner:
                query.partner_id = partner.id
        
        # Send confirmation email to customer only
        try:
            template = self.env.ref('laundry_management.email_template_contact_confirmation')
            if template:
                template.send_mail(query.id, force_send=True)
        except Exception as e:
            _logger.warning(f"Failed to send customer confirmation email for query ID {query.id}: {str(e)}")
    
    def action_progress(self):
        """Mark query as in progress and assign to current user if not assigned"""
        self.state = 'in_progress'
        if not self.assigned_to:
            self.assigned_to = self.env.user
            self.send_staff_notification_email()
    
    def action_resolve(self):
        """Mark query as resolved - requires response"""
        if not self.response:
            raise UserError("Cannot resolve query without providing a response to the customer.")
        
        self.state = 'resolved'
        if not self.response_date:
            self.response_date = fields.Datetime.now()
        # Send response email to customer when resolving
        self.send_response_email()
    
    def action_close(self):
        """Mark query as closed - just changes state"""
        self.state = 'closed'
    
    def send_response_email(self):
        """Send response email to customer"""
        if not self.response or not self.email:
            return
        
        try:
            template = self.env.ref('laundry_management.email_template_customer_response', raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=True)
                # Log the email sending in chatter
                self.message_post(
                    body=f"Response email sent to customer at {self.email}",
                    message_type='comment'
                )
        except Exception as e:
            _logger.error(f"Failed to send response email to {self.email}: {str(e)}")
            # Log error in chatter for visibility
            self.message_post(
                body=f"Failed to send response email to {self.email}: {str(e)}",
                message_type='comment'
            )
    
    def write(self, vals):
        """Override write method to prevent changes after closure and auto-progress on assignment"""
        # Prevent priority changes after resolved/closed
        if 'priority' in vals and self.state in ['resolved', 'closed']:
            raise UserError("Cannot change priority after query is resolved or closed.")
        
        result = super().write(vals)
        
        # Auto-progress when someone is assigned to a new query
        if 'assigned_to' in vals and vals['assigned_to'] and self.state == 'new':
            self.state = 'in_progress'
            # Send staff notification email when assigned
            self.send_staff_notification_email()
        
        return result
    
    def send_staff_notification_email(self):
        """Send notification email to assigned staff member"""
        if not self.assigned_to or not self.assigned_to.email:
            return
        
        try:
            template = self.env.ref('laundry_management.email_template_staff_notification', raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=True)
                # Log the email sending in chatter
                self.message_post(
                    body=f"Staff notification email sent to {self.assigned_to.name} ({self.assigned_to.email})",
                    message_type='comment'
                )
        except Exception as e:
            _logger.error(f"Failed to send staff notification email to {self.assigned_to.email}: {str(e)}")
            # Log error in chatter for visibility
            self.message_post(
                body=f"Failed to send staff notification email to {self.assigned_to.name}: {str(e)}",
                message_type='comment'
            )
