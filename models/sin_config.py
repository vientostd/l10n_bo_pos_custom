from odoo import models, fields, api


class SinConfig(models.Model):
    _inherit = 'sin.config'

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
