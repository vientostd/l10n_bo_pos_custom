from odoo import models


class SinActivity(models.Model):
    _inherit = 'sin.activity'

    def name_get(self):
        """Muestra 'código · descripción' en los desplegables (p. ej. el
        selector de actividad económica de la Configuración SIN), para que
        junto al código se vea la actividad que representa."""
        result = []
        for rec in self:
            if rec.code:
                result.append((rec.id, f"{rec.code} · {rec.description}"))
            else:
                result.append((rec.id, rec.description))
        return result
