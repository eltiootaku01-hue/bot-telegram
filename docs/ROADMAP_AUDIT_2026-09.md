# Auditoría progresiva — septiembre de 2026

## Decisiones confirmadas

- Equipo de referencia: Ryzen 5 5600G, 16 GB RAM, GPU integrada.
- Núcleo local-first y determinista.
- SQLite/FTS5 como primera capa de búsqueda local.
- Índices derivados y reconstruibles.
- Embeddings y modelos locales sólo como capacidades opcionales y bajo demanda.
- No convertir memoria, web o API en canon automáticamente.
- Aislamiento obligatorio por universo/proyecto.

## FASE 0.3 — 2026-09-27

Se añadió el registro persistente de la auditoría de requisitos, arquitectura y decisiones:

- `docs/FASE_0_3_AUDITORIA_REQUISITOS_ARQUITECTURA_DECISIONES_2026-09-27.md`
- HEAD de referencia de la auditoría: `4f2141759483a3f8f3e3610e3b3cad8d1ec2f314`
- Estado: auditoría + diseño, sin cambios funcionales.
- Se documentó la diferencia entre el runtime actual basado en ProviderManager y el objetivo confirmado de conversación de personajes mediante chat web.
- Se documentaron los huecos de Tavern Telegram, estados de mesera, espera por regreso, TCG inventory/deck, rental fallback, MatchHistory, economía, identidad, WebQueue, Chromium, ProviderManager, Ollama, memoria, emociones, timing, almacenamiento externo y TCG Web.
- Las decisiones aún no confirmadas quedan marcadas como `DECISIÓN PENDIENTE DEL USUARIO`.



## Actualización de diseño — Character Engine + WebChat compartido (2026-09-27)

Se incorpora como requisito arquitectónico, todavía no implementado:

- WebChat como recurso compartido para tareas que requieren generación de lenguaje.
- Cola con prioridades conceptuales y cooldown independiente de prioridad.
- Estados técnicos internos separados de cualquier mensaje visible al usuario.
- Interacción controlada de una sola intervención por usuario/personaje cuando se hable directamente con Cari.
- Character Engine como ensamblador de contexto antes de WebChat.
- Separación de roleplay y análisis.
- Estado emocional y actitud proporcionados por BOT-IA.
- Selección de memoria relevante en vez de enviar todo el historial.
- Posibilidad de ambigüedad y contrapregunta natural.
- Salida pública limitada al diálogo del personaje.
- Metadata emocional posterior separada del texto público.

### Conflictos documentados

- src/services/web_queue.py es FIFO + exclusión mutua; no demuestra prioridad global actual.
- src/gui/task_orchestrator.py tiene HIGH/MEDIUM/LOW, pero no es la cola global del runtime Qt normal.
- src/bot_ia/providers/prompt_builder.py implementa roleplay de Tavern, pero no el Character Engine completo.
- No existe todavía estado emocional persistente estructurado.
- No existe todavía actitud operacional persistente.
- No existe selección especializada de memoria para Character Engine.
- No existe flujo grupal “Hablarle a Cari” con la restricción especificada.
- El mecanismo de señal/metadata emocional posterior todavía requiere contrato técnico.

### Política

Esta actualización es documentación de diseño. No autoriza implementación funcional, migración de runtime, cambio de dependencias ni eliminación de legacy.

## FASE 1 — Seguridad y autoridad (implementación)

Implementada una autoridad de acceso pequeña y reutilizable en src/bot_ia/security/authority.py.

- IDs estables de SuperAdmin Telegram/Discord: IMPLEMENTADO.
- TELEGRAM_ADMIN_USER_IDS centralizado: IMPLEMENTADO.
- AUTHORIZED_GROUP_ID / TELEGRAM_OFFICIAL_CHAT_IDS: REUTILIZADOS.
- AUTHORIZED_FORUM_ID: REUTILIZADO.
- DISCORD_AUTHORIZED_GUILD_IDS: IMPLEMENTADO, fail-closed.
- /setup_group y callbacks administrativos Telegram: GUARDADOS POR AUTORIDAD.
- Moderación automatizada Discord: limitada a guild autorizada.
- TCG Discord /drop y claim: limitados a guild autorizada.
- Character Engine, prompts privados y detector de extracción: PENDIENTE.
- GUI local: REUTILIZADA; autenticación OS formal: PENDIENTE.

### Verificación

Se añadió tests/test_security_authority.py con 18 pruebas contractuales para identidad, grupos/topics, guilds, privilegios y exposición de secretos.

En el punto de partida existían errores de sintaxis ajenos a FASE 1 en:
- src/bot/handlers/drop_handler.py
- src/bot/handlers/support_handler.py
- src/discord/bot.py

El error de sintaxis de src/discord/bot.py se corrigió únicamente porque ese archivo debía modificarse para aplicar el guard de guild. Los dos fallos restantes siguen fuera del alcance de FASE 1.

No se añadieron dependencias ni migraciones SQLite.