# Investigación comparativa: medios, pedidos y automatización de Telegram

Fecha: 2026-09-20

## Fuentes y patrones observados

### Telegram Bot API

- `file_id` permite reutilizar un archivo ya almacenado en los servidores de Telegram; Telegram recomienda este mecanismo para evitar volver a cargar el mismo archivo.
- `file_unique_id` identifica de forma estable el mismo archivo y se describe como consistente a lo largo del tiempo y entre bots, pero no sirve para descargar/reutilizar el archivo.
- Los grupos de medios pueden enviarse como álbum mediante `sendMediaGroup`.
- Los topics/foros admiten `message_thread_id`, por lo que una misma comunidad puede organizar publicaciones por área sin multiplicar chats.

Decisión para este proyecto: guardar ambos identificadores. `file_id` es el handle operativo de envío y `file_unique_id` es la señal de deduplicación/identidad del medio.

### Botatobot

El proyecto `scristobal/botatobot` describe explícitamente una cola de trabajo acotada (bounded worker queue) entre las solicitudes de Telegram y el servidor de Stable Diffusion.

Patrón adoptado conceptualmente: el ingreso de pedidos debe desacoplarse de la ejecución pesada. La capacidad de procesamiento debe estar limitada para que un pico de solicitudes no consuma todos los recursos.

### Tanscope

`tantaneity/tanscope` combina aiogram, SQLite/SQLAlchemy, Redis y almacenamiento de `file_id`. Su README destaca:

- cachear consultas para no golpear repetidamente el proveedor;
- cachear medios ya subidos para evitar descargas y ancho de banda;
- limitar descargas concurrentes con un semáforo;
- mantener estadísticas agregadas;
- hacer fallar el arranque de forma explícita si falta una credencial obligatoria;
- usar despliegues que preservan volumen/estado para no perder estadísticas.

Patrón adoptado: en nuestro bot, la durabilidad y la identidad del asset deben sobrevivir a reinicios, y las operaciones pesadas futuras deben tener concurrencia limitada.

### BooruBot

`AtoraSuunva/BooruBot` ofrece un flujo de exploración y publicación con:

- filtros por canal;
- tags por defecto;
- navegación anterior/siguiente;
- ocultar resultados;
- búsqueda privada y posterior publicación pública.

Patrón adoptado: separar descubrimiento/revisión de la publicación definitiva. Cami puede trabajar primero con una bandeja privada y solo publicar después de una decisión explícita.

### Telegram Moderation Bot

`aglvetik/telegram-moderation-bot` mantiene historial de moderación y estados activos recuperables después de reinicio.

Patrón adoptado: toda operación de estado que tenga efecto real debe poder auditarse y recuperarse.

### OpenAI Image Telegram Bot

`chigerartem/openai-image-telegram-bot` usa lista blanca, historial de generaciones, configuración por usuario y manejo de errores legible.

Patrón adoptado: las preferencias y el historial operativo deben ser persistentes y las respuestas de error deben explicar al operador qué hacer, sin exponer detalles internos innecesarios.

### Stable Diffusion Bot

`capslock/stable-diffusion-bot` separa el bot Telegram de una abstracción API para Stable Diffusion/ComfyUI y exige una lista de usuarios permitidos.

Patrón adoptado: el backend de generación, el transporte Telegram y la política de acceso deben mantenerse desacoplados.

### ComfyUI

Los ejemplos oficiales de ComfyUI muestran el patrón `queue prompt -> esperar ejecución por WebSocket -> consultar history -> recuperar outputs`. Las APIs de cola expuestas directamente no llevan autenticación incorporada en el servidor de referencia; si se exponen fuera de localhost, la capa de red/proxy debe hacerse cargo de protegerlas.

Patrón adoptado: cualquier futuro backend local de generación debe quedar detrás de una interfaz propia y no exponerse directamente al exterior. La ejecución debe tener estado consultable, cancelación y recuperación.

## Errores recurrentes que evitaremos

1. Ejecutar procesamiento pesado dentro del handler de Telegram.
2. No limitar concurrencia y dejar que un pico de mensajes agote CPU/RAM/VRAM.
3. Tratar `file_id` como identidad absoluta del contenido; el Bot API admite distintos `file_id` válidos para un mismo archivo.
4. Perder estado al reiniciar porque el historial o la cola viven solo en memoria.
5. Mezclar "descubrir/revisar" con "publicar".
6. Marcar un trabajo como válido o completado demasiado pronto.
7. Exponer un backend pesado local sin una política de acceso externa.
8. Dejar que un fallo de telemetría destruya la operación principal del usuario.

## Nueva metodología propuesta para Cami

```text
INGESTA
  ↓
IDENTIDAD DEL MEDIO (file_id + file_unique_id)
  ↓
BANDEJA PRIVADA
  ↓
ETIQUETADO / CLASIFICACIÓN
  ↓
VALIDACIÓN DE DESTINO
  ↓
PROGRAMACIÓN DURABLE
  ↓
CLAIM ATÓMICO
  ↓
ENVÍO TELEGRAM
  ↓
CONFIRMACIÓN / ENTREGA AMBIGUA
  ↓
RECUPERACIÓN HUMANA
  ↓
CATÁLOGO
```

Cada etapa tiene que ser reiniciable sin duplicar efectos. La futura evolución puede añadir procesamiento local (FFmpeg, miniaturas, OCR o clasificación) como workers separados, nunca bloqueando el receptor de Telegram.

## Métricas que deben crecer con el sistema

- tiempo desde recepción hasta etiquetado;
- tiempo desde etiquetado hasta publicación;
- trabajos reintentados;
- entregas ambiguas;
- duplicados detectados por `file_unique_id`;
- publicaciones por destino;
- fallos por tipo;
- profundidad máxima de la cola;
- tiempo de espera promedio del pedido.

La IA, cuando exista, debe servir como herramienta opcional de clasificación/sugerencia. No debe ser la autoridad sobre canon, identidad de personajes, permisos ni estados de publicación.


## Evolución integrada el 2026-09-20: tablero de trabajo

A partir de los patrones anteriores, Cami incorpora una vista privada /tablero que unifica pedidos y materiales pendientes. No sustituye las colas persistentes: funciona como una capa de routing para decidir qué trabajo merece atención primero.

La prioridad actual favorece:

1. entregas ambiguas que podrían producir duplicados;
2. pedidos cuyo SLA ya venció;
3. pedidos pendientes de información o aprobación;
4. medios que bloquean la cadena de publicación;
5. programación futura.

Cada elemento incluye una siguiente acción concreta. Esto evita el problema operativo de tener varias bandejas correctas pero no saber cuál atender primero.

## Álbumes como unidad de trabajo

La ingesta de Cami reconoce media_group_id y crea una identidad persistente de álbum. Los elementos siguen guardándose individualmente para conservar trazabilidad, pero la interfaz evita pedir una decisión por cada foto.

Este equilibrio permite dos propiedades que suelen competir entre sí:

- agrupación para el operador;
- trazabilidad individual para publicación, recuperación y catálogo.

La futura publicación de álbumes puede usar sendMediaGroup cuando el destino y la política de publicación lo justifiquen, conservando estados por elemento y una estrategia explícita para entregas ambiguas.
