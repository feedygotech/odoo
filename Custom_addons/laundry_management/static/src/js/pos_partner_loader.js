/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

// Patch PosStore to auto-select customer when opened from pickup request
patch(PosStore.prototype, {
  async setup(...args) {
    const result = await super.setup(...args);
    // Wait for data to be fully loaded then check if opened from pickup request
    setTimeout(() => {
      this._checkPickupRequestCustomer();
    }, 2000);
    return result;
  },

  _checkPickupRequestCustomer() {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const partnerId = urlParams.get("partner_id");
      const fromPickupRequest = urlParams.get("from_pickup_request");

      // Only proceed if opened from pickup request with a partner_id
      if (!fromPickupRequest || !partnerId) {
        return;
      }

      // Access partner data in Odoo 18 - direct approach
      let partners = [];
      if (this.models && this.models["res.partner"]) {
        partners = this.models["res.partner"].getAll();
      }

      if (Array.isArray(partners) && partners.length > 0) {
        const partner = partners.find((p) => p.id == parseInt(partnerId));

        if (partner && this.get_order) {
          const currentOrder = this.get_order();

          if (currentOrder && currentOrder.set_partner) {
            currentOrder.set_partner(partner);

            // Show notification that customer was pre-selected
            if (this.notification) {
              this.notification.add(
                `Customer ${partner.name} has been automatically selected from pickup request.`,
                {
                  type: "success",
                  sticky: false,
                }
              );
            }
          }
        }
      }
    } catch (error) {
      console.error("Error in pickup request customer selection:", error);
    }
  },
});
