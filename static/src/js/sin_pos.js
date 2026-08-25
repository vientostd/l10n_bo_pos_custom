/** @odoo-module */
/**
 * POS Bolivia SIN — Selector de actividad + receipt SIN integrado.
 *
 * Este módulo reemplaza el approach de polling con datos que fluyen
 * naturalmente desde el backend via _load_pos_data_fields.
 */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { _t } from "@web/core/l10n/translation";

// ── Patch PosStore: Selector de actividad al abrir POS ────────
patch(PosStore.prototype, {
    async start() {
        await super.start();

        // Cargar actividades SIN disponibles
        try {
            const activities = await this.data.call(
                "sin.activity.config", "search_read",
                [[]], { fields: ["id", "name", "actividad_economica", "config_id"] }
            );
            this.sin_activities = activities || [];
        } catch (e) {
            this.sin_activities = [];
            console.warn("SIN: No se pudieron cargar actividades", e);
        }

        // Si hay actividades disponibles, pedir selección
        if (this.sin_activities.length > 0) {
            await this._selectSinActivity();
        }
    },

    async _selectSinActivity() {
        const activities = this.sin_activities;
        if (!activities || activities.length === 0) return;

        if (activities.length === 1) {
            // Una sola actividad: seleccionar automáticamente
            this.selectedSinActivity = activities[0];
            return;
        }

        // Múltiples actividades: mostrar popup
        return new Promise((resolve) => {
            this.dialog.add(SinActivityDialog, {
                activities: activities,
                title: _t("Seleccionar Actividad SIN"),
                confirm: (activity) => {
                    this.selectedSinActivity = activity;
                    resolve();
                },
                cancel: () => {
                    // Seleccionar la primera por defecto
                    this.selectedSinActivity = activities[0];
                    resolve();
                },
            });
        });
    },

    async getSinReceiptData(order) {
        if (!order || !order.id) return {};
        try {
            return await this.data.call("pos.order", "get_sin_receipt_data", [[order.id]]);
        } catch (e) {
            console.warn("SIN: Error getting receipt data", e);
            return {};
        }
    },
});


// ── Patch OrderReceipt: Mostrar datos SIN en el receipt ───────
patch(OrderReceipt.prototype, {
    get sinData() {
        const order = this.props.order;
        if (!order) return null;

        // Acceder directamente a los campos del modelo pos.order
        // que llegan via _load_pos_data_fields
        const sinState = order.sin_state;
        const sinCuf = order.sin_cuf;
        const sinMessage = order.sin_message;

        if (!sinState || sinState === 'draft' || sinState === 'not_sent') {
            return null;
        }

        return {
            state: sinState,
            stateLabel: this._getSinStateLabel(sinState),
            cuf: sinCuf || '',
            message: sinMessage || '',
            hasCuf: !!sinCuf,
        };
    },

    _getSinStateLabel(state) {
        const labels = {
            'sending': 'Procesando...',
            'sent': 'Enviado al SIN',
            'validated': 'Validado por SIN',
            'error': 'Error SIN',
        };
        return labels[state] || state;
    },

    get sinQrUrl() {
        const data = this.sinData;
        if (!data || !data.hasCuf) return null;
        const baseUrl = this.order.config._base_url;
        // QR con CUF para verificación
        return `${baseUrl}/sin/validate?cuf=${data.cuf}`;
    },
});


// ── Component: Popup de selección de actividad ────────────────
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class SinActivityDialog extends Component {
    static template = "l10n_bo_pos_custom.SinActivityDialog";
    static components = { Dialog };
    static props = {
        activities: Array,
        title: String,
        confirm: Function,
        cancel: Function,
    };

    setup() {
        this.state = {
            selectedId: this.props.activities.length === 1
                ? this.props.activities[0].id
                : null,
        };
    }

    selectActivity(activity) {
        this.state.selectedId = activity.id;
    }

    onConfirm() {
        const activity = this.props.activities.find(
            (a) => a.id === this.state.selectedId
        );
        if (activity) {
            this.props.confirm(activity);
            this.props.close();
        }
    }

    onCancel() {
        this.props.cancel();
        this.props.close();
    }
}
