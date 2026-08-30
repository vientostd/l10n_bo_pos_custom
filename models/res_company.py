from odoo import fields, models, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    sin_activity_ids = fields.One2many(
        'sin.activity.config',
        'company_id',
        string='Actividades SIN',
        help='Actividades económicas SIN de esta compañía (a través de su config). '
             'Sirven para facturar en el POS y se filtran a las autorizadas por el SIN.',
    )

    def open_sin_config(self):
        """Abre la Configuración SIN de esta compañía (o la crea si no existe)."""
        self.ensure_one()
        config = self.env['sin.config'].search(
            [('company_id', '=', self.id)], limit=1)
        if not config:
            if not self.env.user.has_group('base.group_system'):
                raise UserError(_(
                    'No hay una Configuración SIN para esta compañía. '
                    'Solo un administrador puede crearla.'
                ))
            config = self.env['sin.config'].create({'company_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': 'Configuración SIN',
            'res_model': 'sin.config',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }
