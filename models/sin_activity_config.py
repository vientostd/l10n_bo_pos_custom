import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SinActivityConfig(models.Model):
    _inherit = 'sin.activity.config'

    alias = fields.Char(
        string='Alias POS',
        help='Nombre corto que se muestra en la barra superior del POS para distinguir la actividad',
    )
    activity_id = fields.Many2one(
        'sin.activity',
        string='Actividad SIN',
        help='Actividad del catálogo sincronizado del SIN que autoriza facturar '
             'con esta configuración. Si queda vacía, no se ofrece en el POS.',
    )
    company_id = fields.Many2one(
        'res.company',
        related='config_id.company_id',
        string='Compañía',
        store=True,
        help='Compañía propietaria de esta actividad (a través de la config SIN). '
             'Permite mostrar las actividades en la ficha de la empresa.',
    )

    @api.model
    def pos_search_activities(self):
        """Devuelve SOLO las actividades configuradas que el SIN autoriza para
        facturar (cuya actividad_economica existe en sin.activity, el catálogo
        sincronizado desde la operación sincronizarActividades).

        Así el selector del POS (cambio de actividad al facturar) jamas ofrece
        una actividad que el SIN no haya autorizado (p. ej. la 4761000/Papelería).
        """
        configs = self.sudo().search([])
        auth_codes = set(
            self.env['sin.activity'].sudo().search([]).mapped('code') or []
        )
        result = []
        for rec in configs:
            if rec.actividad_economica not in auth_codes:
                _logger.info(
                    'SIN-POS: omitiendo actividad %s (%s) no autorizada por el SIN',
                    rec.actividad_economica, rec.name)
                continue
            result.append({
                'id': rec.id,
                'activity_id': rec.activity_id.id if rec.activity_id else False,
                'name': rec.name,
                'alias': rec.alias,
                'actividad_economica': rec.actividad_economica,
                'codigo_sistema': rec.codigo_sistema,
                'display_name': rec.display_name,
            })
        return result

    @api.model
    def pos_get_activities_with_default(self, pos_config_id=None):
        """Devuelve las actividades autorizadas + la actividad por defecto del
        punto de venta, para que el dialogo del POS pueda preseleccionarla al
        abrir caja.

        :param pos_config_id: id de pos.config del que se toma la actividad
            por defecto (sin_activity_config_id). Si es None o no está
            autorizada, default_id es False.
        """
        activities = self.pos_search_activities()
        default_id = False
        if pos_config_id:
            pc = self.env['pos.config'].browse(pos_config_id)
            if pc.exists() and pc.sin_activity_config_id:
                cfg_default = pc.sin_activity_config_id.id
                if any(a['id'] == cfg_default for a in activities):
                    default_id = cfg_default
        if not default_id and activities:
            # Si no hay default configurado, preseleccionar la primera autorizada.
            default_id = activities[0]['id']
        return {
            'activities': activities,
            'default_id': default_id,
        }
