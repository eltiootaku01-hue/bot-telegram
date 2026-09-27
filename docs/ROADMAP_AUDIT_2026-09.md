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

