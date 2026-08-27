/** @odoo-module */
/**
 * POS Bolivia SIN — Activity selector + Receipt SIN.
 *
 * - LoginScreen: intercepts "Open Register" → shows activity dialog first
 * - Navbar: shows activity badge (alias) in top-right header
 * - OrderReceipt: shows SIN data (CUF, estado, QR)
 */
import { patch } from "@web/core/utils/patch";
import { LoginScreen } from "@point_of_sale/app/screens/login_screen/login_screen";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

console.log("[SIN] sin_pos.js loaded");

// ═══════════════════════════════════════════════════════════════
//  Activity Dialog — OWL Component
// ═══════════════════════════════════════════════════════════════
export class SinActivityDialog extends Component {
    static components = { Dialog };
    static template = "l10n_bo_pos_custom.SinActivityDialog";
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            activities: [],
            loading: true,
            selectedId: null,
        });
        this.loadActivities();
    }
    async loadActivities() {
        try {
            const activities = await this.orm.call(
                "sin.activity.config",
                "pos_search_activities",
                []
            );
            this.state.activities = activities || [];
        } catch (e) {
            console.error("[SIN] Error cargando actividades:", e);
            this.state.activities = [];
        }
        this.state.loading = false;
    }
    selectActivity(act) {
        this.state.selectedId = act.id;
    }
    onConfirm() {
        const selected = this.state.activities.find(
            (a) => a.id === this.state.selectedId
        );
        this.props.getPayload(selected);
        this.props.close();
    }
    onCancel() {
        this.props.getPayload(null);
        this.props.close();
    }
}

// ═══════════════════════════════════════════════════════════════
//  Patch LoginScreen — Activity dialog before entering POS
// ═══════════════════════════════════════════════════════════════
patch(LoginScreen.prototype, {
    async openRegister() {
        const pos = this.env.services.pos;
        const config = pos.config;
        if (!config.sin_enabled) {
            return super.openRegister();
        }
        const result = await makeAwaitable(
            this.env.services.dialog,
            SinActivityDialog,
            {}
        );
        if (!result) {
            return;
        }
        pos.selectedSinActivity = result;
        return super.openRegister();
    },
});

// ═══════════════════════════════════════════════════════════════
//  Patch Navbar — Activity badge + switch activity
// ═══════════════════════════════════════════════════════════════
patch(Navbar.prototype, {
    get sinActivityAlias() {
        const act = this.pos.selectedSinActivity;
        if (!act) return null;
        return act.alias || act.name || null;
    },
    get sinActivityName() {
        const act = this.pos.selectedSinActivity;
        if (!act) return null;
        return act.name || null;
    },
    async switchSinActivity() {
        const result = await makeAwaitable(
            this.dialog,
            SinActivityDialog,
            {}
        );
        if (result) {
            this.pos.selectedSinActivity = result;
        }
    },
});

// ═══════════════════════════════════════════════════════════════
//  Patch PosStore — Set activity on new orders
// ═══════════════════════════════════════════════════════════════
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    createNewOrder(data = {}) {
        const order = super.createNewOrder(data);
        if (this.selectedSinActivity && order) {
            try {
                order.sin_activity_config_id = this.selectedSinActivity.id;
            } catch (e) {
                console.warn("[SIN] Could not set activity on order:", e);
            }
        }
        return order;
    },
});

// ═══════════════════════════════════════════════════════════════
//  Patch OrderReceipt — Show SIN data on receipt
// ═══════════════════════════════════════════════════════════════
patch(OrderReceipt.prototype, {
    get sinData() {
        const order = this.props.order;
        if (!order) return null;
        const sinState = order.sin_state;
        const sinCuf = order.sin_cuf;
        const sinMessage = order.sin_message;
        if (!sinState || sinState === "draft" || sinState === "not_sent") {
            return null;
        }
        return {
            state: sinState,
            stateLabel: this._getSinStateLabel(sinState),
            cuf: sinCuf || "",
            message: sinMessage || "",
            hasCuf: !!sinCuf,
        };
    },
    _getSinStateLabel(state) {
        const labels = {
            sending: "Procesando...",
            sent: "Enviado al SIN",
            validated: "Validado por SIN",
            error: "Error SIN",
        };
        return labels[state] || state;
    },
    get sinQrUrl() {
        const data = this.sinData;
        if (!data || !data.hasCuf) return null;
        const baseUrl = this.order.config._base_url;
        return `${baseUrl}/sin/validate?cuf=${data.cuf}`;
    },
});
