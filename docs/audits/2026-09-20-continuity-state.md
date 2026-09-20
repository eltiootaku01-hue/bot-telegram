# Estado persistente de continuidad del proyecto

Fecha de auditoría: 2026-09-20

Este archivo es una memoria técnica del trabajo ya realizado. Antes de volver a tocar un área, revisar este documento para evitar repetir auditorías ya cerradas sin una razón nueva.

## Corregido y validado

### Plataforma y persistencia
- Arquitectura modular de cuatro bots: Cari, Sunna, Cami y Chie.
- SQLite + SQLAlchemy async + aiosqlite.
- WAL, foreign keys, busy timeout y fronteras transaccionales centralizadas.
- Modos SQLite de transacción y sesiones de escritura con `IMMEDIATE`.
- Recuperación race-safe de eventos y jobs mediante fencing de lease.
- TaskSupervisor protegido contra callbacks tardíos de tareas antiguas.

### Seguridad Telegram
- Allowlist explícita de grupos/supergrupos mediante `AUTHORIZED_CHAT_IDS`.
- Privado restringido al administrador configurado.
- Middleware fail-closed antes de MemberSync.
- Callbacks privados autentican al usuario que pulsa, no al autor del mensaje embebido.
- Envíos automáticos de WildWaifu, Trivia, Cami y Tío Otaku comprueban autorización antes de entregar contenido a una comunidad.

### Sunna / WaifuMon
- Encuentro activo único por comunidad.
- Captura condicional `active -> captured`.
- Intentos únicos por usuario/encuentro.
- Recompensas de captura idempotentes.
- Evolución/fusión protegida contra carreras.
- Expiración no puede sobrescribir estados terminales.
- Encuentros vencidos se retiran antes de crear otro.
- Trivia: ronda activa única, rondas vencidas autocurativas y ganador único.
- Aprobaciones de drops raros: una sola decisión válida.
- Puntos: ledger con referencias idempotentes y protección de carreras.

### Cami
- Publicación durable con worker.
- Claim atómico `scheduled -> publishing`.
- Claim atómico de publicaciones de pedidos.
- Reconciliación de `delivery_unknown`.
- Programación convertida de hora de Ciudad Animals a UTC.
- Concurrencia de publicación cubierta por regresión.
- Catálogo local de medios y catálogo local de anime/manga.
- Recuperación manual de entregas ambiguas.

### Ciudad Animals
- Catálogo persistente de lugares, roles, acciones y relaciones confirmadas.
- Observación agregada global, usuario y usuario+chat.
- Curator diario de tendencias.
- Propuestas opcionales con IA separadas del canon.
- El runtime cotidiano sigue siendo determinista y authored-only.

### Personajes e interacciones
- Profiles de Cari, Cami, Sunna y Chie.
- Canon de Cari/Cami/Sunna separado del runtime.
- Repertorio authored-only.
- CharacterDirector determinista y sin generación de texto.
- Matriz de interacciones entre las cuatro identidades.
- Seguimientos multi-personaje y continuidad por uso de relación.
- Sunna no depende de respuestas vacías: existe repertorio de curiosidad, pertenencia, afecto, gratitud y crecimiento.

### Tío Otaku
- Es operador humano, no una quinta IA.
- Captura solo vocativos explícitos.
- Bandeja persistente.
- Contexto de solicitud.
- Respuesta manual exacta.
- Claim de respuesta para evitar doble envío.
- Recuperación si Telegram falla.
- Historial técnico de estados.
- IA no redacta respuestas como Tío Otaku.

### Windows
- Cinco ejecutables: BotManager + Cari + Sunna + Cami + Chie.
- Instalador Inno Setup.
- ZIP portable.
- Smoke test de BotManager.
- Checksums.
- CI Ubuntu y Windows verdes sobre `c13da70731d...`.

## Pendiente real

1. Profundidad autoral: aumentar repertorio y escenas usando únicamente material confirmado; ampliar Chie solo cuando exista material autoral confirmado.
2. Más interacciones en runtime: la matriz está cubierta, pero deben crecer las situaciones realmente ejercitadas por el usuario, no solamente el número de escenas.
3. Superficies: mejorar navegación práctica de Cari/Cami/Chie y reducir comandos que solo muestran texto descriptivo.
4. Tío Otaku: mejorar inbox, navegación histórica y trazabilidad visual sin automatizar su voz.
5. Concurrencia: auditar únicamente rutas que todavía carecen de una regresión específica.
6. Release final: etiquetar versión cuando el siguiente bloque funcional de producto esté cerrado y su CI haya pasado.

## Regla de no repetición

No volver a “auditar desde cero” TaskSupervisor, leases, access middleware, transacciones de MemberSync, RequestService, publicación atómica de Cami, expiración de WildWaifu, trivia stale-state, rare approvals o el paquete Windows salvo que aparezca evidencia nueva, una regresión, una modificación relevante o un requisito nuevo.

## Próximo objetivo

Primero profundizar superficies y continuidad de interacción; después cerrar una tanda funcional suficientemente grande para preparar el release final.
## Snapshot 2026-09-20

Estimación global conservadora del proyecto: 77%. No es una métrica de CI; es una estimación de cobertura funcional frente a la visión completa del proyecto.

| Área | Estado estimado |
| --- | ---: |
| Arquitectura Core | 92% |
| Persistencia / SQLite / transacciones | 97% |
| Telegram / seguridad / runtime | 95% |
| BotManager / Windows / empaquetado | 98% |
| Módulos funcionales | 92% |
| WaifuMon / progresión / trivia | 94% |
| Personajes / canon | 79% |
| Director / repertorio / rutinas | 75% |
| Ciudad Animals / Café Otaku | 70% |
| Interacciones / continuidad | 72% |
| IA secundaria / curación | 40% |
| GUI / experiencia de operador | 45% |

### Avance del checklist solicitado

- Profundidad autoral: EN PROGRESO. Se amplió únicamente material compatible con Cari/Cami/Sunna confirmado; no se creó una biblia nueva para Chie.
- Más interacciones: EN PROGRESO. La matriz ya cubre las 12 parejas dirigidas y ahora las relaciones confirmadas tienen variantes adicionales; el runtime ya usa choose_interaction con continuidad por uso.
- Superficies de usuario: EN PROGRESO. Se añadieron /ayuda por identidad y navegación histórica de Tío Otaku; Cami/Cari/Chie todavía pueden recibir superficies más ricas.
- Tío Otaku: AVANZADO. Captura explícita, inbox, contexto, respuesta humana, fencing y navegación histórica ya existen.
- Concurrencia: AVANZADO. Se cerraron muchas rutas y se sigue tocando solo donde falta regresión específica.
- Release final: PENDIENTE. No etiquetar todavía hasta cerrar el siguiente bloque funcional y obtener CI Ubuntu + Windows verdes sobre el mismo SHA.

### No repetir sin evidencia nueva

No reauditar desde cero los bloques ya marcados como corregidos arriba. Una nueva pasada debe buscar solo regresiones, consumidores nuevos o requisitos nuevos.
