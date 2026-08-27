import logging
from odoo import models, fields, api, _
_logger = logging.getLogger(__name__)
class PosConfig(models.Model):
    _inherit = 'pos.config'
    sin_activity_config_id = fields.Many2one(
        'sin.activity.config',
        string='Actividad SIN por defecto',
        help='Actividad económica que se usará por defecto en este punto de venta',
    )
    sin_enabled = fields.Boolean(
        string='SIN Habilitado',
        compute='_compute_sin_enabled',
        store=True,
    )
    @api.depends('sin_activity_config_id')
    def _compute_sin_enabled(self):
        config = self.env['ir.config_parameter'].sudo()
        auto_mode = config.get_param('sin.automatic_mode')
        for rec in self:
            rec.sin_enabled = (
                auto_mode == 'auto'
                and bool(rec.sin_activity_config_id)
            )
    @api.model
    def _load_pos_data_fields(self, config):
        # Exclude sin_activity_config_id: sin.activity.config is not in ir_model,
        # so processModelClasses cannot resolve the relation and crashes,
        # preventing pos.order.line from registering and breaking _computeAllPrices.
        return [f for f in self._fields if f != 'sin_activity_config_id']
