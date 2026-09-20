# Auditoría de acceso de eventos Telegram — 2026-09-19

## Hallazgo

El middleware central controla updates de mensajes y callbacks, pero los updates `chat_member` y `my_chat_member` pueden llegar por rutas de eventos distintas. Por ello, los handlers que producen mensajes a comunidades no pueden asumir que el middleware de mensajes ya validó la allowlist.

## Corrección

Se endurecieron tres puntos:

- `SystemModule.bot_added()` no envía mensajes a un grupo/supergrupo fuera de `AUTHORIZED_CHAT_IDS`.
- `ChieModule.member_joined()` no envía bienvenidas fuera de `AUTHORIZED_CHAT_IDS`.
- `SystemModule` recibe la misma instancia de `Settings` usada por la composición del bot, evitando que una configuración inyectada sea reemplazada por defaults.

La excepción de bootstrap de Chie permanece separada: el middleware permite únicamente el comando exacto `/configurar` desde un administrador real para completar el alta inicial; la actividad normal continúa bloqueada mientras la comunidad no esté autorizada.

## Regresiones

`tests/test_system_events_access.py` verifica:

- bot añadido a comunidad no autorizada → ningún envío;
- bot añadido a comunidad autorizada → envío permitido;
- Sunna mantiene su teclado de juegos al entrar en comunidad autorizada.

`tests/test_chie_world_panel.py` verifica que una bienvenida de Chie no se emite en una comunidad retirada de la allowlist.

## Validación

El estado de código quedó en:

`d6dd8ccaad0128e4daa15b96e3465c98e0f09cf1`

CI #1004 terminó en **SUCCESS** para este SHA. La validación Windows correspondiente quedó en ejecución al momento de registrar esta auditoría; no se considera finalizada hasta su conclusión.

## Invariante

Cualquier futuro handler Telegram que pueda enviar contenido automáticamente a una comunidad debe volver a comprobar su autorización antes del envío cuando el evento no sea una ruta normal de mensaje/callback cubierta por `ChatAccessMiddleware`.
