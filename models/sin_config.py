import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SinConfig(models.Model):
    _inherit = 'sin.config'

    ACTIVITY_CONFIG_DEFAULTS = [
        ('1811000', '1811000 · Actividades de impresión', 'DTF'),
        ('6209300', '6209300 · Instalación de programas informáticos', 'PROG'),
        ('6209200', '6209200 · Instalación de ordenadores personales', 'EQUIPOS'),
    ]

    sin_activity_id = fields.Many2one(
        'sin.activity',
        string='Actividad Económica',
        compute='_compute_sin_activity_id',
        inverse='_set_sin_activity_id',
        help='Actividad económica (del catálogo sincronizado del SIN). '
             'Al elegirla se guarda su código en "actividad_economica".',
    )

    @api.depends('actividad_economica')
    def _compute_sin_activity_id(self):
        act_model = self.env['sin.activity']
        for rec in self:
            act = False
            if rec.actividad_economica:
                act = act_model.search(
                    [('code', '=', rec.actividad_economica)], limit=1)
            rec.sin_activity_id = act.id if act else False

    def _set_sin_activity_id(self):
        for rec in self:
            rec.actividad_economica = (
                rec.sin_activity_id.code if rec.sin_activity_id else False
            )

    def _ensure_activity_configs(self):
        """Crea (si faltan) las configuraciones POS de las actividades
        autorizadas por el SIN para este NIT. Idempotente: busca por
        (config_id, actividad_economica) y NO toca las existentes, para que
        los datos ya ajustados a mano (alias, nro. solicitud, etc.) se
        conserven."""
        self.ensure_one()
        AC = self.env['sin.activity.config'].sudo()
        existing = AC.search([('config_id', '=', self.id)])
        base_code = self.codigo_sistema or (
            existing[:1].codigo_sistema if existing else '')
        if not base_code:
            _logger.warning(
                'SIN-POS: sin codigo_sistema en sin.config %s; no se crean '
                'actividades POS', self.id)
            return AC
        base_solicitud = existing[:1].solicitud_number or '9552'
        base_sector = existing[:1].document_sector_code or '1'
        catalog = {a.code: a
                   for a in self.env['sin.activity'].sudo().search([])}
        for code, name, alias in self.ACTIVITY_CONFIG_DEFAULTS:
            if AC.search([('config_id', '=', self.id),
                          ('actividad_economica', '=', code)], limit=1):
                continue
            act = catalog.get(code)
            rec = AC.create({
                'config_id': self.id,
                'name': name,
                'actividad_economica': code,
                'codigo_sistema': base_code,
                'solicitud_number': base_solicitud,
                'document_sector_code': base_sector,
                'alias': alias,
                'activity_id': act.id if act else False,
            })
            _logger.info(
                'SIN-POS: creada actividad POS %s (id=%s)', code, rec.id)
        return AC

    def action_ensure_activity_configs(self):
        """Boton de la Configuracion SIN: asegura las actividades POS."""
        self._ensure_activity_configs()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _cron_ensure_activity_configs(self):
        """Cron diario: auto-repara las actividades POS de todas las
        configuraciones (p. ej. tras restaurar una base de datos)."""
        for cfg in self.env['sin.config'].search([]):
            try:
                cfg._ensure_activity_configs()
            except Exception:
                _logger.exception(
                    'SIN-POS: cron fallo al asegurar actividades de la '
                    'config %s', cfg.id)
        return True