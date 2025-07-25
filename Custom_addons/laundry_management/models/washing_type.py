# -*- coding: utf-8 -*-
from odoo import fields, models, api


class WashingType(models.Model):
    """Washing types generating model"""
    _name = 'washing.type'
    _description = "Washing Type"

    name = fields.Char(string='Name', required=True,
                      help='Name of Washing type.')
    assigned_person_id = fields.Many2one('res.users',
                                       string='Assigned Person',
                                       required=False,  # Changed to False
                                       help="Name of assigned person")
    amount = fields.Float(string='Service Charge', required=False,
                        help='Service charge of this type')
    
    @api.model_create_multi
    def create(self, vals_list):
        # For washing types created from POS, use current user as assigned person
        if self._context.get('create_from_pos'):
            for vals in vals_list:
                if 'assigned_person_id' not in vals:
                    vals['assigned_person_id'] = self.env.user.id
        return super(WashingType, self).create(vals_list)
