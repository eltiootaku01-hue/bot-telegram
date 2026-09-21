# Pipeline técnico de stickers de Telegram

Revisión: 2026-09-21.

## Formato recomendado

Para el paquete inicial del bot se usa sticker estático WEBP con transparencia. Telegram exige que uno de los lados sea de 512 px; para stickers estáticos también acepta PNG, con un límite de tamaño definido por el formato de sticker. La documentación oficial recomienda usar un contorno claro y admite transparencia. Fuente: Telegram Bot API y documentación de stickers.

## Producción

1. Generar el arte desde el prompt del catálogo.
2. Mantener fondo transparente.
3. Exportar a PNG maestro.
4. Convertir a WEBP estático conservando transparencia.
5. Validar que ancho o alto sea 512 px.
6. Asociar al menos un emoji al sticker.
7. Crear o ampliar el sticker set mediante la API de Telegram.
8. Guardar el file_id devuelto por Telegram junto al sticker_key estable.

## Organización del pack

Las 48 expresiones actuales caben en un único conjunto estático porque Telegram admite conjuntos de stickers regulares y el flujo de Bot API permite añadir stickers individualmente. Para evitar acoplar el código al identificador remoto, el repositorio guarda primero la clave autoral y deja el file_id como configuración de despliegue.

## Riesgos evitados

- No dependemos de URLs remotas para enviar stickers una vez que existe file_id.
- No mezclamos identidad visual y personalidad.
- No generamos poses sexuales o desnudez en las variantes del pack.
- No hacemos que una falla al registrar un sticker pueda modificar la personalidad de una identidad.

## Fuentes oficiales

- https://core.telegram.org/bots/api
- https://core.telegram.org/stickers
- https://core.telegram.org/api/stickers
