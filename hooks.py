"""Hooks de instalacion de l10n_bo_pos_custom.

post_init_hook se registra en __manifest__.py y se ejecuta al INSTALAR el
modulo: crea (si faltan) las configuraciones POS de las actividades
autorizadas por el SIN para que viajen con el modulo en git y se auto-recreen
en cualquier ambiente."""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Tras instalar el modulo, asegura las actividades POS de la(s)
    configuracion(es) SIN ya existentes (no hace nada si aun no hay)."""
    for cfg in env['sin.config'].sudo().search([]):
        cfg._ensure_activity_configs()
    env.cr.commit()
    _logger.info('SIN-POS: post_init_hook aseguro actividades POS')