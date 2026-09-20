# Método operativo de los cuatro bots

## Regla transversal

El sistema trata a Cari, Sunna, Cami y Chie como identidades con trabajos concretos, no como cuatro chatbots genéricos.

Cadena común:
entrada -> validación -> decisión determinista -> ejecución -> verificación -> recuperación -> observación

La IA es una capa opcional de escalado. No puede saltarse permisos, inventar capacidades ni escribir directamente en estados sin validación.

## Cari

Trabajo: anfitriona del Café Otaku, conversación cotidiana authored-only, recomendaciones, pequeños eventos, contexto del café, moderación administrativa y transporte de solicitudes de Tío Otaku.

Mejora operativa: clasificar intención localmente, responder desde repertorio autorizado, registrar observaciones agregadas y mantener la moderación como acción administrativa auditable.

## Sunna

Trabajo: WaifuMon, gacha, encuentros, captura, colección, evolución, puntos, trivia y combate.

Mejora operativa: reglas locales, transiciones SQL condicionadas, recompensas idempotentes, estados terminales protegidos, jobs durables y validación de la comunidad antes de envíos automáticos.

## Cami

Trabajo: ingestión de imágenes/documentos, deduplicación, clasificación, catálogo local, asociación de pedidos, programación, publicación y recuperación.

Nuevo pipeline: ingest -> dedupe -> classify -> queue -> publish -> verify -> recover.

Telegram conserva el media y el sistema reutiliza file_id/file_unique_id en lugar de descargar copias innecesarias.

Los álbumes se identifican por source_chat_id + media_group_id y cada elemento mantiene su propio MediaAsset. El operador puede etiquetar el conjunto sin sobrescribir elementos que ya avanzaron individualmente.

Las publicaciones usan una reclamación atómica antes del envío. Una entrega cuyo resultado no pudo persistirse pasa a delivery_unknown y requiere decisión humana.

## Chie

Trabajo: onboarding, permisos, temas, reglas, recepción de pedidos, notificaciones, seguimiento, salud y revisión de Ciudad Animals.

Mejora operativa: verificar permisos reales en Telegram, configurar de forma idempotente, usar eventos durables y mantener la consulta de pedidos limitada a sus propietarios.

## Tío Otaku

Tío Otaku sigue siendo operador humano. El sistema transporta solicitudes, contexto, reconocimiento y resolución, pero no redacta ni envía automáticamente respuestas como él.

## Catálogo de procesos

app/services/process_catalog.py define las capacidades permitidas de cada identidad.

Embudo futuro: evento -> recuperación determinista -> hasta 8 candidatos -> hasta 3 candidatos -> 1 proceso permitido.

La IA, cuando sea necesaria, selecciona entre candidatos existentes. El ejecutor valida de nuevo la identidad del proceso y sus allowed_actions antes de ejecutar.

## Lecciones aplicadas desde otros proyectos

Addarr Refresh combina configuración asistida, autenticación, salud, validación y notificaciones. Se adopta la separación entre configuración, ejecución y observabilidad, pero no su dependencia de Radarr/Sonarr/Lidarr.

XTV-MediaStudio concentra biblioteca, cola y operaciones de media en Telegram. Se adopta el patrón de pipeline, sin convertir Cami en una herramienta de transformaciones innecesarias.

Shield separa ingestión, comprobaciones rápidas, escalado lento, política y enforcement. Este patrón se adopta para mantener las comprobaciones deterministas antes de la IA.

Vixen combina SQLite, alcance por grupo, verificación y reportes. Se adopta la idea de alcance explícito y observable.

El trabajo de aiogram sobre MediaGroupAggregatorMiddleware documenta que Telegram no emite un evento de final de álbum y que la agrupación requiere coordinación; esta implementación usa identidad durable del álbum e idempotencia SQLite para el entorno local.

## Criterio de terminado

Una capacidad nueva debe tener contrato, estado persistente, estrategia contra duplicados, recuperación ante efectos externos, observabilidad y pruebas. Cuando corresponda, también debe quedar validada por CI y Windows.
