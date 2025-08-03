/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.LaundryServiceInfoLoader = publicWidget.Widget.extend({
  selector: "#dynamic_laundry_service_info",

  async willStart() {
    try {
      const html = await rpc("/services-info/snippet", {});
      this.$target.html(html);
    } catch (error) {
      this.$target.html(`
                <div class="col-12 text-center">
                    <div class="alert alert-warning" role="alert">
                        <i class="fa fa-exclamation-triangle me-2"></i>
                        Unable to load services at this time. Please try again later.
                    </div>
                </div>
            `);
    }
  },

  start() {
    // Add hover effects after content is loaded
    this.$target.find(".laundry-card").hover(
      function () {
        $(this).addClass("hover");
      },
      function () {
        $(this).removeClass("hover");
      }
    );

    return this._super.apply(this, arguments);
  },
});

export default publicWidget.registry.LaundryServiceInfoLoader;
