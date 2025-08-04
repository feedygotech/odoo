/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.LaundryPriceLoader = publicWidget.Widget.extend({
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

  if (!service || !service.categories || service.categories.length === 0) {
    $panel.html(
      `<div class='alert alert-info text-center'>Select a service to view pricing.</div>`
    );
    return;
  }

  const currency = service.currency || { symbol: 'AED', position: 'before' };
  const formatPrice = (price) => {
    const formattedPrice = parseFloat(price).toFixed(2);
    return currency.position === 'before'
      ? `${currency.symbol} ${formattedPrice}`
      : `${formattedPrice} ${currency.symbol}`;
  };

  let html = `<div class="pricing-header p-3 mb-1">
    <h3 class="fw-bold mb-2">${service.name}</h3>
  </div>`;

  let hasProducts = false;

  service.categories.forEach((cat, index) => {
    if (!cat.products.length) return;
    hasProducts = true;
    const collapseId = `collapse-${index}`;
    html += `
      <div class="category-block mb-3">
        <div class="category-header p-3 border rounded d-flex justify-content-between align-items-center" 
             data-bs-toggle="collapse" data-bs-target="#${collapseId}" style="cursor:pointer; background: #deeeffff">
          <span class="fw-bold text-dark">${cat.name}</span>
          <i class="fa fa-chevron-down text-muted"></i>
        </div>
        <div id="${collapseId}" class="collapse mt-2">
          <table class="table table-sm mb-0">
            <thead>
              <tr>
                <th>Item</th>
                <th>Price</th>
              </tr>
            </thead>
            <tbody>
              ${cat.products.map(p => `
                <tr>
                  <td>${p.name}</td>
                  <td class="text-primary fw-bold">${formatPrice(p.price)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>`;
  });

  if (!hasProducts) {
    html += `<div class='alert alert-warning text-center'>No items found in this service.</div>`;
  }

  $panel.html(html);
  },
});

export default publicWidget.registry.LaundryPriceLoader;
