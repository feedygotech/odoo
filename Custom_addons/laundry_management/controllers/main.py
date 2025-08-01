from odoo import http
from odoo.http import request
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

_logger = logging.getLogger(__name__)


class LaundryController(http.Controller):

    @http.route('/laundry/pricing_preview/<int:service_id>', type='http', auth='user', website=True)
    def pricing_preview(self, service_id, **kw):
        service = request.env['laundry.service'].sudo().browse(service_id)
        if not service.exists():
            return request.not_found()
        
        pricing_data = self._build_pricing_data_unified(service, show_current_values=True)
        
        # Handle success/error messages from republish action
        success_message = None
        error_message = None
        if kw.get('success'):
            success_message = "Pricing republished successfully!"
        if kw.get('error'):
            error_message = kw.get('error')
        
        return request.render('laundry_management.pricing_preview', {
            'service': service,
            'pricing_data': pricing_data,
            'is_preview': True,
            'success_message': success_message,
            'error_message': error_message,
        })

    @http.route('/laundry/republish_pricing/<int:service_id>', type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def republish_pricing_form(self, service_id, **kw):
        """Handle form submission to republish pricing"""
        service = request.env['laundry.service'].sudo().browse(service_id)
        if not service.exists():
            return request.not_found()
        
        try:
            # Call the model's publish action
            service.action_publish_pricing()
            # Redirect back to preview page with success message
            return request.redirect(f'/laundry/pricing_preview/{service_id}?success=1')
        except Exception as e:
            # Redirect back to preview page with error message
            return request.redirect(f'/laundry/pricing_preview/{service_id}?error={str(e)}')

    def _build_pricing_data_unified(self, service, show_current_values=False):
        """
        Unified pricing data builder
        Args:
            service: The laundry service record
            show_current_values: If True, shows current prices/names (for preview)
                                If False, shows published prices/names (for customers)
        """
        # Get company currency for formatting
        company = request.env.company
        currency = company.currency_id
        
        service_data = {
            'id': service.id,
            'name': service.name,
            'tagline': service.tagline,
            'image_url': f'/web/image/laundry.service/{service.id}/image' if service.image else None,
            'currency': {
                'id': currency.id,
                'name': currency.name,
                'symbol': currency.symbol,
                'position': currency.position,  # 'before' or 'after'
            },
            'categories': []
        }
        
        # Use published snapshot data
        if service.is_pricing_published and service.pricing_snapshot_ids:
            categories_data = {}
            # Only include active products in customer view
            for snapshot in service.pricing_snapshot_ids.filtered(lambda s: s.product_active).sorted(lambda s: (s.category_sequence, s.product_sequence)):
                if snapshot.category_id.id not in categories_data:
                    categories_data[snapshot.category_id.id] = {
                        'id': snapshot.category_id.id,
                        'name': snapshot.category_name,
                        'sequence': snapshot.category_sequence,
                        'products': []
                    }
                # Choose which values to show based on mode
                if show_current_values:
                    # Preview mode: show current values if changed, otherwise published
                    display_name = snapshot.current_name if snapshot.name_changed else snapshot.product_name
                    display_price = snapshot.current_price if snapshot.price_changed else snapshot.published_price
                else:
                    # Customer mode: always show published values
                    display_name = snapshot.product_name
                    display_price = snapshot.published_price
                categories_data[snapshot.category_id.id]['products'].append({
                    'id': snapshot.product_id.id,
                    'name': display_name,
                    'price': display_price,
                    'published_name': snapshot.product_name,
                    'published_price': snapshot.published_price,
                    'has_changes': snapshot.has_changes,
                    'price_changed': snapshot.price_changed,
                    'name_changed': snapshot.name_changed,
                    'change_status': 'modified' if snapshot.has_changes else 'published',
                    'current_price': snapshot.current_price,
                    'current_name': snapshot.current_name,
                })
            
            # Check for new products not in snapshots (only show in preview mode)
            if show_current_values:
                snapshot_product_ids = set(service.pricing_snapshot_ids.mapped('product_id.id'))
                for category in service.pos_category_id.child_ids:
                    products = request.env['product.product'].sudo().search([('pos_categ_ids', '=', category.id)])
                    new_products = products.filtered(lambda p: p.id not in snapshot_product_ids)
                    
                    if new_products:
                        if category.id not in categories_data:
                            categories_data[category.id] = {
                                'id': category.id,
                                'name': category.name,
                                'sequence': 10,
                                'products': []
                            }
                        
                        for product in new_products:
                            categories_data[category.id]['products'].append({
                                'id': product.id,
                                'name': product.name,
                                'price': product.lst_price,
                                'published_name': '',
                                'published_price': 0,
                                'has_changes': True,
                                'price_changed': False,
                                'name_changed': False,
                                'change_status': 'new',
                                'current_price': product.lst_price,
                                'current_name': product.name,
                            })
            
            # Sort categories by sequence and add to service data
            for cat_data in sorted(categories_data.values(), key=lambda x: x['sequence']):
                if cat_data['products']:
                    service_data['categories'].append(cat_data)
        else:
            # Fallback: if not published, show current live data
            for category in service.pos_category_id.child_ids:
                category_data = {
                    'id': category.id,
                    'name': category.name,
                    'products': []
                }
                products = request.env['product.product'].sudo().search([('pos_categ_ids', '=', category.id)])
                for product in products:
                    category_data['products'].append({
                        'id': product.id,
                        'name': product.name,
                        'price': product.lst_price,
                        'has_changes': True,
                        'price_changed': False,
                        'name_changed': False,
                        'change_status': 'new',
                        'current_price': product.lst_price,
                        'current_name': product.name,
                    })
                if category_data['products']:
                    service_data['categories'].append(category_data)
        
        return {'services': [service_data]}

    # Update method calls to use the unified method
    def _build_pricing_data(self, services):
        """Build pricing data for customers (published data only)"""
        result = []
        for service in services:
            service_result = self._build_pricing_data_unified(service, show_current_values=False)
            result.extend(service_result['services'])
        return {'services': result}

    def _build_preview_data(self, service):
        """Build pricing data for admin preview (current data)"""
        return self._build_pricing_data_unified(service, show_current_values=True)


class LaundryWebsite(http.Controller):

    @http.route('/services/snippet', type='json', auth='public', website=True)
    def laundry_services_snippet(self, **kw):
        services = request.env['laundry.service'].sudo().search([
            ('is_published', '=', True), ('active', '=', True)
        ])
        return request.env['ir.qweb']._render(
        'laundry_management.laundry_services_snippet_content',
        {'services': services}
        )

    @http.route(['/services/<path:slug>'], type='http', auth='public', website=True)
    def service_detail_by_slug(self, slug):
        service = request.env['laundry.service'].sudo().search([
            ('url', '=', slug),
            ('is_published', '=', True),
            ('active', '=', True)
        ], limit=1)
        if not service:
            return request.not_found()
        categories = service.pos_category_id.child_ids
        
        # Get features and benefits for the service
        features = service.feature_ids.sorted('sequence')
        benefits = service.benefit_ids.sorted('sequence')
        
        return request.render('laundry_management.laundry_service_detail', {
            'service': service,
            'categories': categories,
            'features': features,
            'benefits': benefits,
        })

    @http.route('/prices/snippet', type='json', auth='public', website=True)
    def laundry_pricing_data(self, **kw):
        services = request.env['laundry.service'].sudo().search([
            ('is_published', '=', True), 
            ('active', '=', True),
            ('is_pricing_published', '=', True)  # Only show services with published pricing
        ])
        # Use LaundryController's method to build pricing data
        controller = LaundryController()
        return controller._build_pricing_data(services)

    @http.route('/contact/submit', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def contact_form_submit(self, **post):
        """Handle contact form submission"""
        try:
            # Validate required fields
            required_fields = ['name', 'phone', 'email', 'subject', 'message']
            missing_fields = [field for field in required_fields if not post.get(field)]
            
            if missing_fields:
                return request.render('laundry_management.contact_form_response', {
                    'success': False,
                    'message': f'Please fill in all required fields: {", ".join(missing_fields)}'
                })
            
            # Create contact query record
            query_vals = {
                'name': post.get('name'),
                'phone': post.get('phone'),
                'email': post.get('email'),
                'subject': post.get('subject'),
                'message': post.get('message'),
            }
            
            request.env['laundry.contact.query'].sudo().create(query_vals)
            
            return request.render('laundry_management.contact_form_response', {
                'success': True,
                'message': 'Thank you for contacting us! We will get back to you soon.',
                'customer_name': post.get('name')
            })
            
        except Exception as e:
            _logger.error(f"Error submitting contact form: {str(e)}")
            return request.render('laundry_management.contact_form_response', {
                'success': False,
                'message': 'Sorry, there was an error submitting your message. Please try again later.'
            })

class PickupRequestController(http.Controller):
    @http.route('/pickup/submit', type='http', auth='public', website=True, csrf=False)
    def pickup_submit(self, **post):
        # Extract form data with structured address fields
        vals = {
            'name': post.get('name'),
            'email': post.get('mail'), # Keep for legacy/compatibility
            'pickup_street': post.get('pickup_street'),
            'pickup_city': post.get('pickup_city'),
            'pickup_state': post.get('pickup_state'),
            'pickup_zip': post.get('pickup_zip'),
            'pickup_country': post.get('pickup_country'),
            'landmark': post.get('address'),
            'phone': post.get('phone'),
        }
        request.env['laundry.pickup.request'].sudo().create(vals)
        return request.render('laundry_management.pickup_thank_you')

    @http.route('/pickup/get_api_key', type='json', auth='public', website=True)
    def get_api_key(self):
        # Use the existing Google Maps API key from website settings
        api_key = request.website.google_maps_api_key
        return {'api_key': api_key or ''}