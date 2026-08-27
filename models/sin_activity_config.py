import logging
from odoo import models, fields, api, _
_logger = logging.getLogger(__name__)
class SinActivityConfig(models.Model):
    _inherit = 'sin.activity.config'
    alias = fields.Char(
        string='Alias POS',
        help='Nombre corto que se muestra en la barra superior del POS para distinguir la actividad',
    )
    @api.model
    def pos_search_activities(self):
        return self.sudo().search_read(
            [],
            ['id', 'name', 'actividad_economica', 'display_name', 'alias'],
        )
