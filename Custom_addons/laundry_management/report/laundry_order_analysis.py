# -*- coding: utf-8 -*-
from odoo import fields, models, tools, api
from datetime import datetime, timedelta


class LaundryOrderAnalysis(models.Model):
    _name = "laundry.order.analysis"
    _description = "Laundry Orders Analysis Report"
    _auto = False
    _order = 'date desc'
    _rec_name = 'order_id'

    # Order Information
    date = fields.Datetime(string='Order Date', readonly=True)
    order_id = fields.Many2one('laundry.order', string='Order', readonly=True)
    name = fields.Char(string='Order Number', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('order', 'Laundry Order'),
        ('process', 'Processing'),
        ('done', 'Done'),
        ('delivery', 'Delivered'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)
    
    # Customer Information
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    customer_status = fields.Selection([
        ('active', 'Active Customer'),
        ('inactive', 'Inactive Customer'),
        ('new', 'New Customer')
    ], string='Customer Status', readonly=True)
    
    # Service Information
    service_id = fields.Many2one('laundry.service', string='Service', readonly=True)
    service_name = fields.Char(string='Service Name', readonly=True)
    
    # Financial Information
    total_amount = fields.Float(string='Total Amount', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    # Company Information
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    
    # Metrics
    order_count = fields.Integer(string='Order Count', readonly=True)
    customer_order_count = fields.Integer(string='Customer Total Orders', readonly=True)
    days_since_last_order = fields.Integer(string='Days Since Last Order', readonly=True)
    is_repeat_customer = fields.Boolean(string='Repeat Customer', readonly=True)

    def _select(self):
        return """
            SELECT 
                (lo.id::text || '-' || COALESCE(lol.id::text, '0'))::bigint as id,
                lo.id as order_id,
                lo.name as name,
                lo.order_date as date,
                lo.state as state,
                lo.partner_id as partner_id,
                lo.total_amount as total_amount,
                1 as company_id,
                lo.currency_id as currency_id,
                lol.service_id as service_id,
                ls.name as service_name,
                1 as order_count,
                
                -- Customer status calculation
                CASE 
                    WHEN customer_stats.total_orders = 1 THEN 'new'
                    WHEN customer_stats.days_since_last > 90 THEN 'inactive'
                    ELSE 'active'
                END as customer_status,
                
                customer_stats.total_orders as customer_order_count,
                customer_stats.days_since_last as days_since_last_order,
                CASE WHEN customer_stats.total_orders > 1 THEN true ELSE false END as is_repeat_customer
        """

    def _from(self):
        return """
            FROM laundry_order lo
            LEFT JOIN laundry_order_line lol ON (lo.id = lol.laundry_id)
            LEFT JOIN laundry_service ls ON (lol.service_id = ls.id)
            LEFT JOIN (
                -- Customer statistics subquery
                SELECT 
                    lo2.partner_id,
                    COUNT(lo2.id) as total_orders,
                    COALESCE(
                        EXTRACT(DAY FROM (NOW() - MAX(lo2.order_date))), 
                        0
                    ) as days_since_last
                FROM laundry_order lo2
                WHERE lo2.partner_id IS NOT NULL
                GROUP BY lo2.partner_id
            ) customer_stats ON (lo.partner_id = customer_stats.partner_id)
        """

    def _where(self):
        return """
            WHERE lo.partner_id IS NOT NULL
              AND lo.order_date IS NOT NULL
        """

    def _group_by(self):
        return """
            GROUP BY 
                lo.id, lo.name, lo.order_date, lo.state, lo.partner_id, 
                lo.total_amount, lo.currency_id,
                lol.id, lol.service_id, ls.name, customer_stats.total_orders, customer_stats.days_since_last
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                %s
                %s
                %s
                %s
            )
        """ % (self._table, self._select(), self._from(), self._where(), self._group_by()))


class LaundryCustomerAnalysis(models.Model):
    _name = "laundry.customer.analysis"
    _description = "Laundry Customer Analysis Report"
    _auto = False
    _order = 'total_orders desc'

    # Customer Information
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    customer_name = fields.Char(string='Customer Name', readonly=True)
    customer_email = fields.Char(string='Email', readonly=True)
    customer_phone = fields.Char(string='Phone', readonly=True)
    
    # Customer Status
    customer_status = fields.Selection([
        ('active', 'Active Customer'),
        ('inactive', 'Inactive Customer'),
        ('new', 'New Customer')
    ], string='Customer Status', readonly=True)
    
    # Order Statistics
    total_orders = fields.Integer(string='Total Orders', readonly=True)
    total_amount = fields.Float(string='Total Amount Spent', readonly=True)
    average_order_value = fields.Float(string='Average Order Value', readonly=True)
    first_order_date = fields.Datetime(string='First Order Date', readonly=True)
    last_order_date = fields.Datetime(string='Last Order Date', readonly=True)
    days_since_last_order = fields.Integer(string='Days Since Last Order', readonly=True)
    
    # Company Information
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    def _select(self):
        return """
            SELECT 
                ROW_NUMBER() OVER (ORDER BY p.id) as id,
                p.id as partner_id,
                p.name as customer_name,
                p.email as customer_email,
                p.phone as customer_phone,
                
                -- Customer status calculation
                CASE 
                    WHEN customer_stats.total_orders = 1 THEN 'new'
                    WHEN customer_stats.days_since_last > 90 THEN 'inactive'
                    ELSE 'active'
                END as customer_status,
                
                COALESCE(customer_stats.total_orders, 0) as total_orders,
                COALESCE(customer_stats.total_amount, 0) as total_amount,
                CASE 
                    WHEN customer_stats.total_orders > 0 
                    THEN customer_stats.total_amount / customer_stats.total_orders 
                    ELSE 0 
                END as average_order_value,
                customer_stats.first_order_date,
                customer_stats.last_order_date,
                customer_stats.days_since_last as days_since_last_order,
                customer_stats.company_id,
                customer_stats.currency_id
        """

    def _from(self):
        return """
            FROM res_partner p
            LEFT JOIN (
                -- Customer order statistics
                SELECT 
                    lo.partner_id,
                    COUNT(lo.id) as total_orders,
                    SUM(lo.total_amount) as total_amount,
                    MIN(lo.order_date) as first_order_date,
                    MAX(lo.order_date) as last_order_date,
                    COALESCE(
                        EXTRACT(DAY FROM (NOW() - MAX(lo.order_date))), 
                        999
                    ) as days_since_last,
                    1 as company_id,
                    MAX(lo.currency_id) as currency_id
                FROM laundry_order lo
                WHERE lo.partner_id IS NOT NULL
                  AND lo.order_date IS NOT NULL
                GROUP BY lo.partner_id
            ) customer_stats ON (p.id = customer_stats.partner_id)
        """

    def _where(self):
        return """
            WHERE p.is_company = false
              AND (customer_stats.total_orders > 0 OR p.customer_rank > 0)
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                %s
                %s
                %s
            )
        """ % (self._table, self._select(), self._from(), self._where()))
