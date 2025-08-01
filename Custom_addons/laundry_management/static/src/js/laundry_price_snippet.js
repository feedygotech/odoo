/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.LaundryPriceSnippet = publicWidget.Widget.extend({
  selector: ".s_laundry_price_snippet",

  async willStart() {
    this.data = null;
    try {
      this.data = await rpc("/prices/snippet", {});
    } catch (error) {
      console.error("Error loading pricing data:", error);
      this.$target
        .find(".pricing-details-panel")
        .html(
          `<div class='alert alert-warning text-center'>Unable to load pricing data.</div>`
        );
    }
  },

  start() {
    if (!this.data) return;
    const services = this.data.services || [];
    // Render service list
    const $serviceList = this.$target.find(".service-list");
    $serviceList.empty();
    services.forEach((service, idx) => {
      $serviceList.append(
        `<li class="service-item${
          idx === 0 ? " active" : ""
        }" data-service-id="${service.id}">
          <span>${service.name}</span>
        </li>`
      );
    });
    // Initial render for first service
    this.renderPricingTable(services[0]);
    // Handle service selection
    $serviceList.on("click", ".service-item", (ev) => {
      $serviceList.find(".service-item").removeClass("active");
      const $item = $(ev.currentTarget);
      $item.addClass("active");
      const serviceId = $item.data("service-id");
      const service = services.find((s) => s.id === serviceId);
      this.renderPricingTable(service);
    });
  },

  renderPricingTable(service) {
    const $panel = this.$target.find(".pricing-details-panel");
    if (!service) {
      $panel.html(
        `<div class='alert alert-info text-center'>No pricing data available.</div>`
      );
      return;
    }
    
    // Get currency information
    const currency = service.currency || { symbol: 'AED', position: 'before' };
    const formatPrice = (price) => {
      const formattedPrice = parseFloat(price).toFixed(2);
      return currency.position === 'before' 
        ? `${currency.symbol} ${formattedPrice}`
        : `${formattedPrice} ${currency.symbol}`;
    };
    
    let html = `<div class="pricing-header p-3 mb-3">
      <h3 class="fw-bold mb-0">${service.name} - Pricing Details</h3>
    </div>
    <table class="table pricing-table mb-0">
      <thead>
        <tr>
          <th>Category</th>
          <th>Item</th>
          <th class="text-end">Price</th>
        </tr>
      </thead>
      <tbody>`;
    service.categories.forEach((cat) => {
      if (!cat.products.length) return;
      html += `<tr class="category-row">
        <td rowspan="${cat.products.length}" class="align-middle category-cell">
          <span class="category-icon"><i class="fa fa-folder"></i></span>
          <span class="fw-bold">${cat.name}</span>
        </td>
        <td>${cat.products[0].name}</td>
        <td class="text-end text-primary fw-bold">${formatPrice(cat.products[0].price)}</td>
      </tr>`;
      for (let i = 1; i < cat.products.length; i++) {
        html += `<tr><td>${cat.products[i].name}</td><td class="text-end text-primary fw-bold">${formatPrice(cat.products[i].price)}</td></tr>`;
      }
    });
    html += `</tbody></table>`;
    $panel.html(html);
  },
});

export default publicWidget.registry.LaundryPriceSnippet;
