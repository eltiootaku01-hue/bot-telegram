# Telegram / aiogram — riesgos técnicos

## Callback queries

Telegram indica que una callback query debe ser contestada incluso cuando no hay mensaje visible, para evitar que el cliente conserve el indicador de progreso.

Referencia: https://core.telegram.org/bots/api

El proyecto responde las callbacks en todas las rutas de juego y usa el `from_user` de la callback para autenticar quién pulsó el botón.

## Rate limits

Telegram expone `retry_after` cuando una petición supera el control de flood.

Referencia: https://core.telegram.org/bots/api

El proyecto usa `with_retry_after` para publicaciones de fondo y no reintenta indiscriminadamente fallos cuya operación podría haber sido aceptada.

## Bot-to-bot / loops

La documentación de Telegram recomienda deduplicación, límites de tasa y profundidad máxima para evitar loops de bots.

Referencia: https://core.telegram.org/bots/features

Esto refuerza la decisión del proyecto de mantener el runtime social determinista y limitado, sin permitir que una respuesta genere una cadena infinita entre identidades.
