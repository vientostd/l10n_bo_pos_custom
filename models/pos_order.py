import logging
import threading as _threading
import time as _time
from odoo import models, fields, api, _
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)
class PosOrder(models.Model):
    _inherit = 'pos.order'
    # ── Campos SIN ──────────────────────────────────────────────
    sin_state = fields.Selection([
        ('draft', 'Borrador'),
        ('sending', 'Enviando al SIN'),
        ('sent', 'Enviado al SIN'),
        ('validated', 'Validado por SIN'),
        ('error', 'Error al enviar'),
        ('not_sent', 'No enviado'),
    ], string='Estado SIN', default='draft', copy=False, index=True)
    sin_cuf = fields.Char(string='CUF', copy=False, index=True)
    sin_message = fields.Text(string='Mensaje SIN', copy=False)
    sin_json_request = fields.Text(string='JSON Request SIN', copy=False)
    sin_json_response = fields.Text(string='JSON Response SIN', copy=False)
    sin_activity_config_id = fields.Many2one(
        'sin.activity.config', string='Actividad SIN', copy=False)
    # ── Override: _load_pos_data_fields ─────────────────────────
    # FIX: Do NOT include sin_activity_config_id in POS data fields.
    # sin.activity.config is not registered as a POS model, so processModelClasses
    # fails to resolve the relation, breaking the lines getter and crashing _computeAllPrices.
    # If activity data is needed in the UI, fetch it via RPC in PosStore.start().
    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        sin_fields = [
            'sin_state', 'sin_cuf', 'sin_message',
        ]
        for f in sin_fields:
            if f not in fields_list:
                fields_list.append(f)
        return fields_list
    # ── Override: _generate_pos_order_invoice ───────────────────
    def _generate_pos_order_invoice(self):
        invoice = super()._generate_pos_order_invoice()
        if not invoice:
            return invoice
        if not self._is_sin_enabled():
            return invoice
        try:
            self._send_to_sin_async(invoice)
        except Exception:
            _logger.exception('POS-SIN: Error launching async send for order %s', self.id)
            self.write({
                'sin_state': 'error',
                'sin_message': str(_.je('Error', 'No se pudo iniciar el envío al SIN')),
            })
        return invoice
    def _is_sin_enabled(self):
        self.ensure_one()
        config = self.env['ir.config_parameter'].sudo()
        if config.get_param('sin.automatic_mode') != 'auto':
            return False
        sin_config = self.env['sin.config'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'configured'),
        ], limit=1)
        if not sin_config:
            return False
        if not self.sin_activity_config_id:
            pos_config = self.config_id
            if pos_config.sin_activity_config_id:
                self.sin_activity_config_id = pos_config.sin_activity_config_id
            else:
                return False
        return True
    def _send_to_sin_async(self, invoice):
        self.ensure_one()
        db_name = self.env.cr.dbname
        order_id = self.id
        move_id = invoice.id
        company_id = self.company_id.id
        self.write({'sin_state': 'sending'})
        _time.sleep(0.5)
        thread = _threading.Thread(
            target=self._async_send_sin_background,
            args=(db_name, order_id, move_id, company_id),
            daemon=True,
            name=f'sin-send-{order_id}',
        )
        thread.start()
        _logger.info('POS-SIN: Thread started for order %s → move %s', order_id, move_id)
    @staticmethod
    def _async_send_sin_background(db_name, order_id, move_id, company_id):
        MAX_RETRIES = 3
        RETRY_DELAYS = [2, 5, 10]
        bg_log = logging.getLogger('pos.sin_thread')
        try:
            from odoo.modules.registry import Registry as odoo_registry
        except ImportError:
            bg_log.error('POS-SIN: Cannot import odoo registry')
            return
        for attempt in range(MAX_RETRIES):
            try:
                with odoo_registry(db_name).cursor() as cr:
                    from odoo import api, SUPERUSER_ID
                    env = api.Environment(cr, SUPERUSER_ID, {'company_id': company_id})
                    move = env['account.move'].browse(move_id)
                    order = env['pos.order'].browse(order_id)
                    if not move.exists():
                        bg_log.error('POS-SIN: Move %s does not exist', move_id)
                        return
                    if move.sin_state in ('sent', 'validated'):
                        bg_log.info('POS-SIN: Move %s already sent, skipping', move_id)
                        return
                    bg_log.info('POS-SIN: Attempt %d/%d for order %s → move %s',
                                attempt + 1, MAX_RETRIES, order_id, move_id)
                    sin_api = env['sin.api']
                    result = sin_api.send_invoice(move)
                    if result and result.get('success'):
                        cuf = result.get('cuf', '')
                        env.cr.execute(
                            """UPDATE pos_order SET sin_state='sent', sin_cuf=%s
                               WHERE id=%s""",
                            (cuf, order_id))
                        env.cr.execute(
                            """UPDATE account_move SET sin_state='sent', sin_cuf=%s
                               WHERE id=%s""",
                            (cuf, move_id))
                        env.cr.commit()
                        bg_log.info('POS-SIN: Order %s SENT successfully. CUF=%s', order_id, cuf[:20])
                        return
                    else:
                        error_msg = result.get('message', 'Unknown error') if result else 'No result'
                        bg_log.warning('POS-SIN: Attempt %d failed for order %s: %s',
                                       attempt + 1, order_id, error_msg)
            except Exception:
                bg_log.exception('POS-SIN: Exception on attempt %d for order %s', attempt + 1, order_id)
            if attempt < MAX_RETRIES - 1:
                _time.sleep(RETRY_DELAYS[attempt])
        bg_log.error('POS-SIN: Gave up for order %s after %d attempts', order_id, MAX_RETRIES)
        try:
            with odoo_registry(db_name).cursor() as cr:
                from odoo import api, SUPERUSER_ID
                env = api.Environment(cr, SUPERUSER_ID, {'company_id': company_id})
                env.cr.execute(
                    """UPDATE pos_order SET sin_state='error', sin_message='Agotados reintentos SIN'
                       WHERE id=%s""",
                    (order_id,))
                env.cr.commit()
        except Exception:
            bg_log.exception('POS-SIN: Failed to mark order %s as error', order_id)
    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        if self.sin_activity_config_id:
            vals['sin_activity_config_id'] = self.sin_activity_config_id.id
        return vals
    def get_sin_receipt_data(self):
        self.ensure_one()
        return {
            'sin_state': self.sin_state or 'draft',
            'sin_cuf': self.sin_cuf or '',
            'sin_message': self.sin_message or '',
            'sin_activity': self.sin_activity_config_id.name if self.sin_activity_config_id else '',
            'sin_activity_code': self.sin_activity_config_id.actividad_economica if self.sin_activity_config_id else '',
        }
