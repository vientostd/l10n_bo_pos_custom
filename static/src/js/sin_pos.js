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
        pos._setSinActivity(result);
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
            this.pos._setSinActivity(result);
        }
    },
});

// ═══════════════════════════════════════════════════════════════
//  Patch PosStore — Set activity on new orders
// ═══════════════════════════════════════════════════════════════
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setup(...args) {
        // Inicializar de forma reactiva ANTES del primer render del Navbar.
        // selectedSinActivity (objeto) alimenta el badge; selectedActivityConfigId
        // (int) alimenta el boton "Facturar SIN" del modulo l10n_bo_electronic_invoice.
        // Se declara desde el inicio para que OWL rastree los cambios y el badge
        // no desaparezca al cerrar el dialogo de apertura de caja.
        if (!("selectedSinActivity" in this)) {
            this.selectedSinActivity = null;
        }
        if (!("selectedActivityConfigId" in this)) {
            this.selectedActivityConfigId = null;
        }
        return super.setup(...args);
    },
    createNewOrder(data = {}) {
        const order = super.createNewOrder(data);
        const act = this.selectedSinActivity;
        if (act && order) {
            try {
                order.sin_activity_config_id = act.id;
            } catch (e) {
                console.warn("[SIN] Could not set activity on order:", e);
            }
        }
        return order;
    },
    // Mantener sincronizado el id usado por el boton "Facturar SIN"
    _setSinActivity(act) {
        this.selectedSinActivity = act || null;
        this.selectedActivityConfigId = act ? act.id : null;
    },
    // Suprimir el selector original de l10n_bo_electronic_invoice cuando
    // nuestro sistema con aliases esta activo. El modulo SIN muestra un
    // SelectionPopup automaticamente en start(); si no lo suprimimos, el
    // usuario veeria DOS selectores de actividad. Nuestro dialogo (con alias)
    // ya setea selectedActivityConfigId, asi que el envio SIN funciona igual.
    async _selectSinActivity() {
        if (this.config && this.config.sin_enabled) {
            // Nuestro dialogo (LoginScreen.openRegister) maneja la seleccion.
            // Dejar selectedActivityConfigId en null para que se setee desde
            // _setSinActivity al confirmar.
            this.selectedActivityConfigId = null;
            return;
        }
        // Si sin_enabled esta desactivado, dejar el comportamiento original.
        return super._selectSinActivity(...arguments);
    },
});

// ═══════════════════════════════════════════════════════════════
//  Patch OrderReceipt — SIN data
//  (ELIMINADO: el modulo l10n_bo_electronic_invoice ya maneja el
//   receipt SIN completo (QR, leyenda, polling, hoja carta). Nuestro
//   getter sinData competia por el mismo nombre y podia romper el
//   receipt. Nuestro unico aporte es el badge de alias + selector.)
// ═══════════════════════════════════════════════════════════════
