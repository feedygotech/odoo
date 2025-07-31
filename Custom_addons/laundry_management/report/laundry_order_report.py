# -*- coding: utf-8 -*-
# Part of Laundry Management. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class LaundryOrderAnalysis(models.Model):
    _name = "laundry.order.analysis"
    _description = "Laundry Orders Analysis"
    _auto = False
    _order = 'date desc'
    _rec_name = 'order_id'

    # Basic order information
    date = fields.Datetime(string='Order Date', readonly=True)
    order_id = fields.Many2one('laundry.order', string='Laundry Order', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    laundry_person_id = fields.Many2one('res.users', string='Laundry Person', readonly=True)
    
    # Order status and financial data
    state = fields.Selection([
        ('draft', 'Draft'),
        ('order', 'Laundry Order'),
        ('process', 'Processing'),
        ('done', 'Done'),
        ('delivery', 'Delivered'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)
    
    # Service and product information
    service_id = fields.Many2one('laundry.service', string='Service', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    
    # Financial data
    total_amount = fields.Float(string='Total Amount', readonly=True)
    line_amount = fields.Float(string='Line Amount', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    unit_price = fields.Float(string='Unit Price', readonly=True)
    
    # Customer analysis fields
    customer_order_count = fields.Integer(string='Customer Total Orders', readonly=True)
    customer_total_spent = fields.Float(string='Customer Total Spent', readonly=True)
    customer_first_order_date = fields.Datetime(string='Customer First Order', readonly=True)
    customer_last_order_date = fields.Datetime(string='Customer Last Order', readonly=True)
    days_since_last_order = fields.Integer(string='Days Since Last Order', readonly=True)
    
    # Customer status analysis
    customer_status = fields.Selection([
        ('new', 'New Customer'),
        ('active', 'Active Customer'),
        ('inactive', 'Inactive Customer'),
        ('returning', 'Returning Customer'),
    ], string='Customer Status', readonly=True)
    
    # Company and currency
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    # Count fields for aggregation
    nbr_lines = fields.Integer(string='Order Line Count', readonly=True)
    order_count = fields.Integer(string='Order Count', readonly=True)

    def _select(self):
        return """
            WITH customer_stats AS (
                SELECT 
                    lo.partner_id,
                    COUNT(DISTINCT lo.id) as total_orders,
                    SUM(lo.total_amount) as total_spent,
                    MIN(lo.order_date) as first_order_date,
                    MAX(lo.order_date) as last_order_date,
                    EXTRACT(DAY FROM (NOW() - MAX(lo.order_date))) as days_since_last
                FROM laundry_order lo
                WHERE lo.state != 'cancel'
                GROUP BY lo.partner_id
            ),
            customer_status_calc AS (
                SELECT 
                    cs.*,
                    CASE 
                        WHEN cs.total_orders = 1 THEN 'new'
                        WHEN cs.days_since_last <= 30 THEN 'active'
                        WHEN cs.days_since_last > 90 THEN 'inactive'
                        ELSE 'returning'
                    END as customer_status
                FROM customer_stats cs
            )
            SELECT
                row_number() OVER () AS id,
                lo.order_date AS date,
                lo.id AS order_id,
                lo.partner_id,
                lo.laundry_person_id,
                lo.state,
                lo.total_amount,
                lo.company_id,
                lo.currency_id,
                lol.service_id,
                lol.product_id,
                pt.categ_id AS product_categ_id,
                lol.amount AS line_amount,
                lol.quantity,
                lol.price_unit AS unit_price,
                1 AS nbr_lines,
                1 AS order_count,
                cs.total_orders AS customer_order_count,
                cs.total_spent AS customer_total_spent,
                cs.first_order_date AS customer_first_order_date,
                cs.last_order_date AS customer_last_order_date,
                cs.days_since_last AS days_since_last_order,
                cs.customer_status
        """

    def _from(self):
        return """
            FROM laundry_order_line lol
                JOIN laundry_order lo ON (lo.id = lol.laundry_id)
                LEFT JOIN product_product pp ON (lol.product_id = pp.id)
                LEFT JOIN product_template pt ON (pp.product_tmpl_id = pt.id)
                LEFT JOIN customer_status_calc cs ON (lo.partner_id = cs.partner_id)
                LEFT JOIN res_company rc ON (lo.company_id = rc.id)
        """

    def _group_by(self):
        return """
            GROUP BY
                lo.order_date,
                lo.id,
                lo.partner_id,
                lo.laundry_person_id,
                lo.state,
                lo.total_amount,
                lo.company_id,
                lo.currency_id,
                lol.service_id,
                lol.product_id,
                pt.categ_id,
                lol.amount,
                lol.quantity,
                lol.price_unit,
                cs.total_orders,
                cs.total_spent,
                cs.first_order_date,
                cs.last_order_date,
                cs.days_since_last,
                cs.customer_status
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                %s
                %s
                %s
            )
        """ % (self._table, self._select(), self._from(), self._group_by()))
