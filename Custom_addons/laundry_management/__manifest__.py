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
{
    'name': 'Laundry Management',
    'version': '18.0.1.0.0',
    "category": "Industries",
    'summary': """Complete Laundry Service Management""",
    'description': 'This module is very useful to manage all process of laundry'
                   'service',
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': ['sale_management', 'account', 'point_of_sale', 'website_sale', 'website', 'mail'],
    'data': [
        'data/ir_sequenca_data.xml',
        'data/email_templates.xml',
        'security/laundry_management_security.xml',
        'security/ir.model.access.csv',
        'views/laundry_order_views.xml',
        'views/washing_washing_views.xml',
        'views/label_templates.xml',
        'views/service_views.xml',
        'views/website_templates.xml',
        'views/snippets/snippets.xml',
        'views/snippets/laundry_price_snippet.xml',
        'views/snippets/laundry_service_snippets.xml',
        'views/snippets/contact_form_snippet.xml',
        'views/laundry_service_detail.xml',
        'views/pricing_preview.xml',
        'views/laundry_order_analysis_views.xml',
        'views/laundry_analysis_menu.xml',
        'views/contact_query_views.xml',
        'views/pickup_request_views.xml',
        'views/pickup_thank_you_template.xml',
        'views/pickup_floating_widget.xml',
        'views/website_layout_extend.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'laundry_management/static/src/js/laundry_snippet_loader.js',
            'laundry_management/static/src/js/laundry_price_snippet.js',
            'laundry_management/static/src/css/laundry_snippet.css',
        ],
        'website.assets_editor': [
            'laundry_management/static/src/js/laundry_snippet_loader.js',
            'laundry_management/static/src/js/laundry_price_snippet.js',
            'laundry_management/static/src/css/laundry_snippet.css',
        ],
        'point_of_sale._assets_pos': [
            'laundry_management/static/src/js/pos_partner_loader.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
