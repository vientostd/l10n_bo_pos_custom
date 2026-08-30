# HANDOFF — POS Bolivia SIN (Odoo 19)
## Contexto para continuar en nueva sesión
Fecha: 2026-08-30

## OBJETIVO GENERAL
Que el POS de Odoo 19 (módulos `l10n_bo_pos_custom` + `l10n_bo_electronic_invoice` en 192.168.1.100)
facture correctamente al SIN de Bolivia. Último hito: la actividad económica se define en la
Configuración SIN (`sin.config` → `sin_activity_id`, desplegable "código · descripción"), y el POS
avisa al cajero cuando el SIN rechaza una factura (ej. NIT inválido).

## INFRAESTRUCTURA (CRÍTICO)
- Servidor: `192.168.1.100` (SSH root vía `rtk ssh`), usuario Odoo `viento`, DB `odoo`, servicio `odoo19.service`
- Binario `/opt/odoo19/odoo-bin`, venv `/opt/odoo19/venv/bin/python3`, config `/etc/odoo.conf`
- Addons: `/opt/odoo19/addons, /opt/odoo/custom-addons`; addon base real en `/opt/odoo19/odoo/addons/base`
- Ambiente SIN: sandbox, codigo_sistema `2284D475D4560D3EA7F36`
- `sin.config` id=1 (actividad_economica=1811000, state=configured). `pos.config` id=1 "casa"
- `sin.activity`: id=1 (1811000 "Actividades de impresión"), 2 (6209300), 3 (6209200)
- `sin.activity.config` id=1 "Impresion DTF" (1811000, config_id=1, activity_id=1)

## PATRÓN DE COMANDOS (IMPORTANTE PARA NO ROMPER)
- **PowerShell local rompe** escapes anidados, `$()`, pipelines, comillas en doble-ssh ("unexpected EOF").
- Patrón FIABLE: `write` local → `scp` a `/tmp/x.sh` → `rtk ssh root@192.168.1.100 "bash /tmp/x.sh"`.
- `write` NO sobreescribe archivos existentes → usar `edit` si ya existe.
- Actualización de módulo: `odoo-bin -u <mod> -c /etc/odoo.conf -d odoo --stop-after-init --no-http
  --logfile=/tmp/upd.log --log-level=info` como `sudo -u viento -- sh -c "..."`, luego `systemctl restart odoo19`.
- Para cambios de assets estáticos (JS/XML del POS): basta subir con scp y `systemctl restart odoo19`
  (Odoo regenera los assets al detectar checksum cambiado). NO hace falta `-u` de módulo.
- **Log del servidor** se rota; los errores históricos se pierden. Buscar en `/var/log/odoo/odoo.log`.

## REPOS GIT (2 repos separados, UNO POR MÓDULO) — TODO COMMITEADO Y PUSHEADO
### l10n_bo_pos_custom — `main`, remoto HTTPS+token, push OK
- Último commit: `e415562 feat: actividad economica configurable desde la Configuracion SIN (desplegable)`
- Historial: e415562 → 05d91ae (badge stability) → 1e18cd5 (multi-activity) → b7b5a19 (POS crash fix) → ...
- Remoto: `https://<GITHUB_TOKEN>@github.com/vientostd/l10n_bo_pos_custom.git`
- Árbol limpio (git status vacío)

### l10n_bo_electronic_invoice — `main`, remoto SSH (FALLA publickey, usar token HTTPS para push)
- Último commit: `1b8ac9d fix: congelamiento de pantalla al facturar una orden rechazada por el SIN`
- Historial: 1b8ac9d → db2d3a9 (aviso rechazo SIN) → b651a02 (multi-activity + cola offline) → ...
- Remoto: `git@github.com:vientostd/l10n_bo_electronic_invoice.git` (SSH — NO funciona, sin clave)
- **Para push usar URL con token**: `https://<GITHUB_TOKEN>@github.com/vientostd/l10n_bo_electronic_invoice.git`
- Árbol limpio (git status vacío)

## ÚLTIMA PIEZA DE TRABAJO (lo que se acaba de hacer)
### Objetivo: avisar al cajero cuando el SIN rechaza una factura (ej. NIT inválido)
**Problema original**: El SIN rechazó `casa - 000017` por "EL NUMERO DOCUMENTO DE TIPO NIT NO ES VALIDO.
Nit enviado 1020149023" (cliente "Cliente Certificacion"). El mensaje se guardaba en `sin_message` pero
el ticket del POS solo mostraba "Procesando factura..." y luego "El servidor SIN no respondió".

**Solución (2 commits en l10n_bo_electronic_invoice):**
1. `db2d3a9` — `static/src/js/sin_pos.js`:
   - `loadSinReceiptData` guarda datos también cuando `sin_state === 'error'` (antes solo con `cuf`)
   - El polling y `onWillStart` detectan `sin_state === 'error'` → detienen el polling
   - Nuevo getter `sinError` en OrderReceipt que expone `sin_message` cuando estado es error
   - `static/src/xml/sin_pos_templates.xml`: bloque `t-if="sinError"` que muestra en rojo
     "LA FACTURA FUE RECHAZADA POR EL SIN" + motivo + "Revise los datos del cliente (NIT/Razon Social)"
   - También incluía: guarda anti-orden-sin-pago en `action_send_sin_from_pos`, `pos_search_activities` en sin_config
2. `1b8ac9d` — FIX del congelamiento: el bloque principal de factura `t-if="sinData"` → `t-if="sinData and sinData.cuf"`
   (porque al guardar datos en estado error, `sinData.lines` era undefined y OWL lanzaba
   "Invalid loop expression: undefined is not iterable" → pantalla congelada)

## ARCHIVOS LOCALES (en C:\Users\Viento\AppData\Local\Temp\opencode\)
- `base_sin_pos.js` (JS editado, ya desplegado/committeado)
- `base_sin_pos_templates.xml` (XML editado, ya desplegado/committeado)
- `custom_sin_pos.js` (JS del módulo custom, referencia)
- Varios `diag_*.sh`, `verify_*.sh`, `commit_*.sh`, `git_*.sh` (scripts de diagnóstico/deploy)

## ESTADO DE SANIDAD
- Ambos repos: árbol limpio, todo pusheado a GitHub
- Servicio `odoo19`: **active**
- Trimestre final de la última prueba: el usuario reportó "se congeló la pantalla" al facturar un
  NIT inválido → se corrigió con `1b8ac9d` → DESPLEGADO y servicio reiniciado.

## PENDIENTE / PRÓXIMO PASO
1. **El usuario debe probar en el cajero (192.168.1.9)**:
   - RECARGAR la página del POS (F5 o cerrar/reabrir navegador) para cargar los assets nuevos
   - Facturar a un cliente con NIT inválido
   - Confirmar que AHORA ve el mensaje en rojo "LA FACTURA FUE RECHAZADA POR EL SIN" + motivo,
     y que la pantalla NO se congela
2. Si persiste el congelamiento, el error está EN LA CONSOLA DEL NAVEGADOR del cajero (no en el log
   de Odoo). Pedir al usuario el texto de `D:\descargas\datos (2).txt` (así reportó el último error).

## ARQUITECTURA CLAVE (para debugging rápido)
- **Dos `sin_pos.js`**: módulo base (`l10n_bo_electronic_invoice/static/src/js/sin_pos.js`) y módulo
  custom (`l10n_bo_pos_custom/static/src/js/sin_pos.js`). Ambos parchean PosStore/OrderReceipt.
  El CUSTOM ya NO parchea OrderReceipt (fue eliminado por conflicto); solo el BASE lo hace.
- **PosStore `_selectSinActivity`**: ambos parchean. El custom lo suprime cuando `sin_enabled` para
  evitar doble selector; su `LoginScreen.openRegister` muestra `SinActivityDialog`.
- **Flujo de envío**: POST `/pos/order/send_sin` (controller `send_sin_from_pos`) → `action_send_sin_from_pos()`
  → crea factura + envía al SIN. La guarda anti-orden-sin-pago devuelve success=False con mensaje.
- **Receipt**: polling `get_sin_receipt_data` cada 3s (tope 45s). El método custom (override) devuelve
  `sin_state`, `sin_cuf`, `sin_message`, `sin_activity`, `sin_activity_code`.
- **sin_config dropdown**: módulo custom `models/sin_config.py` (campo Many2one `sin_activity_id` que
  sincroniza `actividad_economica`), `models/sin_activity.py` (name_get "código · descripción").
- **Cola Offline fix**: `views/sin_offline_queue_views.xml` (custom) cambia `column_invisible` a
  `invisible` en el botón "Reintentar" (Odoo 19 evalúa column_invisible contra contexto global).
