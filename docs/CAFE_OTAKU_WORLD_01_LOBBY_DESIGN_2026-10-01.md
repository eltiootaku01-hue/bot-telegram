# WORLD-01-A — CAFÉ OTAKU INTERACTIVO / LOBBY DESIGN

**Fecha:** 2026-10-01  
**Estado:** READY FOR WORLD-01 DESIGN REVIEW  
**Fase:** Architectural / Discovery + Implementation Spec  
**Repositorio:** `eltiootaku01-hue/bot-telegram`

## 1. Purpose

WORLD-01-A convierte la visión:

> “quiero abrir el Café dentro de Telegram, ver quién está, sentarnos en mesas y empezar a compartir cosas”

en un diseño implementable sobre:

- Telegram como comunidad y fuente de contexto;
- TMA como interfaz visual complementaria;
- SQLite existente como persistencia;
- runtime actual como infraestructura compartida.

La primera implementación queda limitada al Lobby:

`CafeRoom` autorizado → `CafeSession` activa → participantes básicos → personajes disponibles → resumen de actividad.

No implementa todavía el motor social completo.

## 2. Scope

WORLD-01 debe resolver únicamente:

1. resolución de un Café autorizado;
2. entrada y salida del Lobby;
3. una sesión social activa por Café/Room;
4. membresía básica de participantes;
5. representación básica de `last_seen`;
6. disponibilidad de personajes;
7. resumen de actividad actual;
8. navegación TMA mínima;
9. autorización server-side;
10. aislamiento entre Rooms.

## 3. Non-goals

Quedan explícitamente fuera:

- presencia avanzada o heartbeat continuo;
- motor genérico de actividades;
- Social Scheduler runtime;
- eventos sociales autónomos;
- persistencia de mesas como entidad independiente;
- amigos/follows;
- party system;
- trading;
- moderación completa del mundo;
- orquestación compleja de IA;
- WebSocket permanente;
- daemon por feature;
- nueva SQLite;
- Redis/Kafka/microservicios;
- modificación de 2F-8S;
- navegador para representar personajes;
- reemplazo del GENERAL o de Topics;
- migración Alembic en esta fase;
- endpoints runtime;
- implementación del Lobby TMA.

## 4. Repository discovery — main real

El HEAD funcional inspeccionado es:

`main@2c35a2be8fd8d1a118bd1fa57466827b1758c72b`.

La rama documental aprobada de referencia es:

`world-00-r1-social-scheduling@dc4c5f6d795f120eecc339713774d4949bd6fced`.

La rama WORLD-01-A se crea desde el HEAD documental `dc4c5f6d795f120eecc339713774d4949bd6fced`, preservando la genealogía del contrato WORLD-00-R1 y sin modificar `main`.

### 4.1 Superficie verificada

Existe en `main`:

- `src/db/models.py`
- `src/services/drop_service.py`
- `src/services/match_service.py`
- `src/api/main.py`
- `src/api/routers/v1/inventory.py`
- `public/inventory.html`
- `src/bot/main.py`
- `src/bot_ia/runtime.py`
- `src/bot_ia/interfaces/telegram.py`
- `src/bot_ia/interfaces/telegram_room_routing.py`
- `src/bot_ia/interfaces/telegram_event_ledger.py`
- `src/bot_ia/interfaces/telegram_outbox.py`
- `src/bot_ia/interfaces/telegram_security.py`
- `src/bot_ia/security/authority.py`
- `src/bot_ia/core/task_engine.py`
- `src/bot_ia/core/task_scheduler.py`
- `src/bot_ia/core/physical_resource_authority.py`
- `src/bot_ia/core/physical_lifecycle_reconciliation.py`
- `src/bot_ia/core/web_physical_identity.py`
- `src/bot_ia/core/waitress_session_manager.py`
- `src/bot_ia/interfaces/cafe_economy.py`
- `src/bot_ia/persistence/economy.py`
- `src/bot_ia/interfaces/cafe_immersion.py`
- `src/bot_ia/interfaces/cafe_rooms.py`
- `src/gui/waifu_registry.py`
- `src/config/selectors.json`
- `docs/project_memory/CAFE_OTAKU_DESIGN.md`
- `docs/project_memory/CAFE_OTAKU_CONVERSATION_SYSTEM.md`
- `docs/project_memory/CHARACTER_SYSTEM.md`

No se encontraron en `main`:

- `src/api/dependencies.py`
- `src/api/security/telegram_auth.py`
- `docs/CAFE_OTAKU_WORLD_ARCHITECTURE_2026-10-01.md`

La ausencia de los dos módulos de autenticación/API es una dependencia explícita del próximo subproyecto; WORLD-01-A no los crea.

## 5. Current TMA State

### 5.1 `public/inventory.html`

La página actual:

- carga `telegram-web-app.js`;
- obtiene `window.Telegram.WebApp`;
- llama `ready()` y `expand()`;
- obtiene `tg.initData`;
- también lee `tg.initDataUnsafe.user`;
- envía `initData` al backend mediante `Authorization: tma <initData>`;
- llama conceptualmente a `/api/v1/inventory`;
- utiliza una URL placeholder: `https://TU-SERVIDOR.com`;
- no contiene resolución de Room;
- no contiene `chat_id`, `message_thread_id` ni `room_key` autoritativos;
- no contiene flujo de Lobby.

`initDataUnsafe.user` sólo se utiliza actualmente para texto visual del cliente. No debe convertirse en autoridad del servidor.

### 5.2 Backend TMA actual

`src/api/main.py` registra el router de inventario.

`src/api/routers/v1/inventory.py` intenta depender de:

- `api.dependencies.get_current_user`;
- `api.dependencies.get_db`;
- `api.security.telegram_auth.TelegramUserData`.

Esos módulos no existen en el HEAD funcional inspeccionado. Por tanto, el TMA/API actual es una superficie parcial y no puede considerarse una implementación completa de autenticación Telegram.

Además, el router de inventario devuelve objetos planos con campos como:

- `instance_id`;
- `copy_number`;
- `level`;
- `card_id`;
- `name`;
- `rarity`;
- etc.

La plantilla actual de `inventory.html` intenta leer `item.card.rarity`, `item.card.name`, etc. Existe por tanto una discrepancia de contrato frontend/backend que deberá resolverse en una fase específica del TMA, no dentro de WORLD-01-A.

### 5.3 CORS

`src/api/main.py` contiene una allowlist declarativa amplia y también `*`. Esto no constituye una política de Room authorization. WORLD-01 no reutilizará CORS como control de autoridad.

## 6. Current Telegram State

Telegram ya dispone de dos superficies relevantes:

### 6.1 Runtime principal de bot

`src/bot/main.py` utiliza `python-telegram-bot` y registra:

- drops;
- duelos;
- combate;
- selección de mazo.

`run_all.py` separa actualmente FastAPI, Telegram y Discord en procesos de plataforma. WORLD-01 no crea un cuarto proceso social.

### 6.2 BOT-IA Telegram adapter

`src/bot_ia/interfaces/telegram.py` ya contiene:

- parsing de mensajes;
- parsing de callbacks;
- `TelegramOutbound`;
- teclados inline;
- `TelegramRoomRouter`;
- `AuthorityCore`;
- `TelegramEventLedger`;
- `TelegramOutboxStore`;
- mutex de callbacks;
- polling existente;
- resolución de Room para updates Telegram.

`room_key_for_update()` obtiene:

`chat_id + message_thread_id + topic`

y para topics consulta `TelegramRoomRouter`.

Para mensajes sin topic autorizado, la resolución devuelve `general`.

Esto es importante: WORLD-01 no debe crear un segundo router Telegram.

## 7. Reusable Components

### 7.1 TelegramRoomRouter

`TelegramRoomRouter` mantiene un mapa SQLite exacto:

`(chat_id, message_thread_id) → room_key`.

Su tabla actual es:

`telegram_room_routes`.

WORLD-01 debe consumir este mecanismo para resolver la identidad lógica del Room.

### 7.2 Telegram security

`telegram_security.py` ya contiene allowlists para:

- grupos autorizados;
- pares `chat_id:message_thread_id`;
- destinos administrativos.

### 7.3 AuthorityCore

`AuthorityCore` ya centraliza decisiones de identidad/destino/permiso para Telegram y Discord.

WORLD-01 debe añadir una capa de autorización del dominio Café sobre la identidad ya autenticada, no reemplazar AuthorityCore.

### 7.4 TelegramEventLedger

El ledger usa `bot_ia_events.sqlite3` y es una capa de idempotencia de eventos Telegram.

WORLD-01 puede emitir eventos de integración cuando exista una acción Telegram real, pero el ledger NO será el log universal del Social World.

### 7.5 TelegramOutboxStore

El outbox ya persiste entregas y followups de Telegram, incluyendo:

- `update_id`;
- `chat_id`;
- payload;
- chunk;
- estado;
- followups.

WORLD-01 debe reutilizarlo para publicaciones Telegram relacionadas con el Café cuando una fase posterior las requiera.

### 7.6 TaskEngine / TaskScheduler

El runtime actual dispone de:

- `TaskEngine`;
- `TaskScheduler`;
- estados de tarea;
- espera/interrupción/reanudación;
- recursos lógicos;
- recurso físico `WEB_MESA_UNICA`.

WORLD-01 no crea scheduler propio.

### 7.7 2F-8S physical boundary

Existe:

- `PhysicalWebChatResourceAuthority`;
- `PhysicalLifecycleReconciliation`;
- `WebPhysicalIdentity`;
- adaptadores QWeb/Playwright;
- TaskEngine/Scheduler.

WORLD-01 nunca los invoca para mostrar presencia, personajes o actividad.

### 7.8 Café/economy/character surfaces

Existen:

- `CafeWalletStore` sobre SQLite WAL;
- economía Café;
- `WaitressSessionManager`;
- `cafe_immersion`;
- `WaifuRegistry`;
- afinidad de Cari/Sunna/Cami/Chie.

Estas superficies son reutilizables como datos/contexto, pero no se reinterpretan como autoridad de `CafeSession`.

## 8. Proposed User Flow

### 8.1 Entrada

1. Usuario pulsa un botón de Mini App.
2. Telegram abre el TMA.
3. TMA obtiene `initData`.
4. TMA envía `initData` al backend.
5. Backend valida firma y antigüedad.
6. Backend deriva `Actor`.
7. Backend resuelve el contexto confiable de lanzamiento.
8. Backend resuelve `CafeRoom`.
9. Backend comprueba que el actor pertenece al grupo autorizado.
10. Backend permite o rechaza el acceso.
11. TMA muestra Lobby.

### 8.2 Lobby

El Lobby muestra:

- Café Otaku;
- Room;
- mesas;
- participantes;
- personajes disponibles;
- actividad actual.

No muestra una copia del historial de Telegram.

### 8.3 Join

`POST /cafe/session/join` es idempotente.

Si el actor ya pertenece a la sesión activa:

- no crea otra membresía;
- actualiza `last_seen_at`;
- devuelve el mismo estado.

### 8.4 Leave

`POST /cafe/session/leave` marca la membresía como abandonada.

No elimina el historial mínimo necesario para auditoría.

### 8.5 Cierre

Una sesión sin participantes activos puede expirar.

El cierre debe ser determinista y no depender de una IA.

## 9. Telegram Flow

Telegram sigue siendo la autoridad de contexto social externo.

Ejemplo conceptual:

`Telegram topic`
→ `TelegramRoomRouter`
→ `room_key`
→ `CafeRoom`
→ `TMA`

El camino inverso:

`TMA action`
→ backend autorizado
→ dominio Café
→ opcionalmente evento Telegram
→ `TelegramOutboxStore`

No se permite:

`TMA`
→ escribir directamente en Telegram API.

La escritura Telegram queda detrás del runtime existente.

## 10. TMA Flow

El TMA será un cliente fino:

- no decide identidad;
- no decide Room;
- no decide membership;
- no decide participantes visibles;
- no decide actividad;
- no genera autoridad a partir de `initDataUnsafe`.

El cliente puede transportar:

- `initData`;
- intención de acción;
- estado de navegación.

El servidor devuelve el estado autorizado.

## 11. Trusted Launch Context

Telegram ofrece distintos mecanismos de lanzamiento de Mini Apps, incluyendo botones, menu button, Main Mini App y direct links. La implementación actual del repositorio no contiene todavía un flujo WORLD-01 que capture y valide un Room context desde un launcher TMA.

Por ello WORLD-01 debe definir un contrato de contexto:

`trusted launch context`
→ `server-side resolution`
→ `CafeRoom`.

El cliente no podrá enviar simplemente:

`room_key = "room-x"`

y convertirlo en autoridad.

### 11.1 Diseño preferido

El launcher futuro debe asociar el contexto al chat/topic desde Telegram y transportar un identificador verificable o una referencia de contexto que el servidor pueda resolver.

La información de cliente que no esté criptográficamente ligada a Telegram o a una referencia emitida por el servidor se considera una solicitud, no una autoridad.

### 11.2 Direct links / start parameters

Telegram documenta Mini App direct links con parámetros `startapp`. Estos parámetros pueden servir como referencia opaca de contexto, pero el servidor debe resolverlos contra una asignación autorizada. El contenido del parámetro no debe ser tratado como `room_key` confiable por sí mismo.

## 12. Actor Handling

### 12.1 Actor

`Actor` conceptual:

- `actor_key`: identidad estable derivada server-side;
- `telegram_user_id`: identificador Telegram validado;
- `display_name`: dato de presentación;
- `source`: Telegram Mini App.

### 12.2 Identity rule

`initData` validada → Actor.

Nunca:

`initDataUnsafe` → Actor.

### 12.3 No forged actor

El backend no acepta `actor_key` como identidad primaria enviada por el cliente.

## 13. CafeRoom

`CafeRoom` es la representación social autorizada de un Room Telegram.

Campos conceptuales:

- `room_key`;
- `chat_id`;
- `message_thread_id` nullable;
- `name`;
- `authorization_source`;
- `active`.

La resolución debe apoyarse en:

`TelegramRoomRouter + Telegram security + membership verification`.

### 13.1 GENERAL

El GENERAL sigue siendo conversación Telegram.

WORLD-01 no crea un `CafeRoom` que absorba el historial GENERAL.

### 13.2 Topics

Cada topic configurado conserva su función.

Un Café puede estar vinculado a un Room concreto, pero eso no convierte todos los topics en mesas.

## 14. CafeSession Design

### 14.1 Decisión

WORLD-01 usa una `CafeSession` persistente y efímera **por CafeRoom**, no una sesión independiente por participante.

Motivo:

- el Lobby necesita un estado común;
- varios participantes deben compartir la misma sesión;
- una sesión por actor no permite representar correctamente el conjunto de participantes;
- evita introducir una entidad social adicional innecesaria.

Regla:

`UNIQUE active CafeSession per room_ref`.

### 14.2 Campos

Propuesta conceptual:

| Campo | Propósito |
|---|---|
| `session_id` | ID interno estable |
| `room_ref` | referencia al CafeRoom |
| `status` | ACTIVE / EXPIRED / CLOSED |
| `created_at` | inicio |
| `last_activity_at` | última actividad significativa |
| `expires_at` | TTL |
| `closed_at` | cierre |
| `version` | control optimista/idempotencia futura |

### 14.3 Índices

Mínimos:

- unique parcial por `room_ref` cuando `status=ACTIVE`;
- índice `room_ref,status`;
- índice `expires_at`.

### 14.4 TTL

El TTL es de la sesión social, no de cada participante.

La política exacta de duración queda como parámetro de implementación posterior.

No se fija todavía un número definitivo.

### 14.5 Join

Join debe:

1. validar Actor;
2. resolver Room;
3. comprobar membership Telegram;
4. abrir/reutilizar sesión activa;
5. crear/reutilizar membership del participante;
6. actualizar `last_seen_at`;
7. devolver estado del Lobby.

Todo en una transacción.

### 14.6 Leave

Leave debe ser idempotente:

- si está activo → pasa a LEFT;
- si ya salió → devuelve estado estable;
- no afecta a otros participantes.

### 14.7 Expiry

La expiración se evalúa por eventos de acceso/lectura/escritura y por un mecanismo de cleanup existente cuando corresponda.

No se crea un proceso `CafeSession daemon`.

### 14.8 Persistence failure

Si SQLite falla:

- no se crea sesión;
- no se declara join exitoso;
- no se devuelve una lista vacía como si no hubiera participantes;
- se devuelve error controlado.

## 15. CafeParticipant Design

### 15.1 Membership != presence

`CafeParticipant` representa membership en la sesión.

Presence es una observación temporal sobre esa membership.

No se crea todavía un Presence Engine.

### 15.2 Campos

Propuesta:

| Campo | Propósito |
|---|---|
| `participant_id` | ID interno |
| `session_id` | FK a CafeSession |
| `actor_key` | actor validado |
| `role` | USER / MODERATOR futuro |
| `membership_state` | ACTIVE / LEFT / EXPIRED |
| `joined_at` | entrada |
| `last_seen_at` | última interacción TMA válida |
| `left_at` | salida |
| `version` | control de actualización |

### 15.3 Uniqueness

Un actor no puede tener dos memberships ACTIVE en la misma sesión.

No se impone una unicidad global que impida participar en otros Cafés/Rooms.

### 15.4 Basic presence

WORLD-01 no necesita heartbeat periódico.

`last_seen_at` se actualiza en:

- join;
- leave;
- navegación significativa;
- acciones del Lobby.

Una futura presencia en tiempo real pertenece a WORLD-02.

## 16. CafeTable Decision

### 16.1 Decisión

**No persistir `CafeTable` en WORLD-01.**

La mesa es una representación visual derivada del conjunto de participantes de `CafeSession`.

### 16.2 Derivación

Inicialmente:

`CafeSession`
→ participantes activos
→ layout determinista
→ Mesa 1 / Mesa 2 / etc.

La tabla visual no posee:

- ownership independiente;
- lifecycle independiente;
- economía propia;
- locks propios;
- TTL propio;
- identidad externa.

Por tanto no justifica una tabla SQLite.

### 16.3 Ejemplo

`CafeSession(session=42)`

Participantes:

- A;
- B;
- C.

La UI puede renderizar:

`Mesa 1 → A, B, C`.

Si la UX futura necesita varias mesas reales con joins, límites, reservas o lifecycle, esa evidencia puede justificar `CafeTable` en una fase posterior.

## 17. Character Availability

### 17.1 Fuente

Reutilizar las superficies existentes.

Para el Lobby se debe consultar disponibilidad lógica de personajes sin abrir navegador.

### 17.2 Nombres

El registro TCG actual define:

- Cari;
- Sunna;
- Cami;
- Chie.

La infraestructura de `WaitressSessionManager` también contiene perfiles operativos adicionales como Scarlet/Chloe.

WORLD-01 no crea un registry persistente nuevo.

### 17.3 Estado

La API debe diferenciar:

- `available`;
- `busy`;
- `resting`;
- `offline`/unknown cuando corresponda.

No debe convertir disponibilidad en:

`speaking = true`.

### 17.4 Character != physical resource

Una mesera del Café no es:

- un WebChat resource;
- una cuenta de navegador;
- una claim física;
- una sesión Playwright/QWeb.

## 18. Current Activity

WORLD-01 sólo expone un resumen.

Contrato conceptual:

```text
activity: null
```

o:

```text
activity:
  type: DROP | DUEL | FUTURE
  status: ACTIVE | FINISHED
  public_summary: ...
  started_at: ...
```

### 18.1 TCG ownership

`GroupDrop` sigue siendo owner del drop.

`ActiveMatch` sigue siendo owner del duelo.

Café sólo proyecta contexto:

`TCG = owner`
`Cafe = context`.

No se duplican drops/duelos en tablas sociales.

## 19. Telegram Integration Contract

### 19.1 Existing authorities

WORLD-01 reutiliza:

- TelegramRoomRouter;
- Telegram security;
- AuthorityCore;
- TelegramEventLedger;
- TelegramOutboxStore;
- runtime Telegram existente.

### 19.2 TMA → backend

Una acción TMA produce una intención:

`join / leave / view`.

El backend vuelve a autorizarla.

### 19.3 Backend → Telegram

Sólo una fase que necesite publicación Telegram produce un evento/outbox.

WORLD-01 Lobby read path no necesita publicar nada.

## 20. Button UX

### 20.1 Entry

Botón conceptual:

`[☕ Entrar al Café]`.

Debe abrir el TMA desde un contexto Telegram que pueda ser resuelto por el servidor.

### 20.2 Lobby

`[🪑 Ver Mesas]`  
`[👥 Quién está]`  
`[👩‍🍳 Personajes]`  
`[🎮 Actividad]`  
`[🚪 Salir]`

### 20.3 Authorization

Los botones son UX, no autorización.

Cada endpoint debe volver a comprobar:

- Actor;
- Room;
- membership Telegram;
- acción permitida.

### 20.4 Commands

No se eliminan comandos existentes.

Los comandos siguen siendo:

- shortcut;
- admin;
- advanced;
- fallback.

## 21. API Contract

La API conceptual mínima es:

### GET `/api/v1/cafe`

**Auth:** Telegram `initData` validada.

**Input:** no confiar en `room_key` del cliente.

**Output:**

```json
{
  "cafe": "cafe_otaku",
  "room": {
    "room_key": "...",
    "name": "..."
  },
  "session": null
}
```

o estado de sesión autorizado.

**Errors:**

- 401 invalid Telegram auth;
- 403 unauthorized Room;
- 404 trusted context not resolvable;
- 503 persistence unavailable.

### GET `/api/v1/cafe/session`

**Auth:** igual.

**Authorization:** actor + authorized Room + Telegram membership.

**Output:** sesión, participantes básicos, personajes y actividad resumida.

**Idempotency:** lectura naturalmente idempotente.

### POST `/api/v1/cafe/session/join`

**Auth:** validada.

**Input:** ninguna autoridad de identidad/Room; opcionalmente preferencias visuales no autoritativas.

**Authorization:** Actor + Room + Telegram membership.

**Output:** CafeSession + participant + Lobby state.

**Idempotency:** repeated join returns the same active membership.

### POST `/api/v1/cafe/session/leave`

**Auth:** validada.

**Input:** ninguna identidad arbitraria.

**Authorization:** actor must own the membership.

**Output:** membership state + session summary.

**Idempotency:** repeated leave is safe.

### GET `/api/v1/cafe/session/participants`

**Auth:** validada.

**Authorization:** actor must be authorized for the same Room.

**Output:** only participants of the resolved session.

**Cross-room:** deny.

### GET `/api/v1/cafe/activity`

**Auth:** validada.

**Authorization:** actor must be authorized for the same Room.

**Output:** current activity envelope or `null`.

No duplicated TCG state.

## 22. Authentication

The future implementation must validate Telegram Mini App `initData` server-side.

Telegram documents:

- HMAC-SHA-256 validation;
- data-check-string sorted by key;
- secret derived from the bot token using `WebAppData`;
- optional `auth_date` freshness protection.

WORLD-01 must use the future `src/api/security/telegram_auth.py` dependency surface when implemented.

`initDataUnsafe` is never an authority source.

### Authentication result

Validation yields:

`AuthenticatedTelegramActor`.

Only then can authorization begin.

## 23. Authorization

Authorization is layered:

```
validated Telegram identity
        +
trusted Room resolution
        +
Telegram membership
        +
Cafe domain policy
        ↓
ALLOW / DENY
```

### 23.1 Join

Requires all four layers.

### 23.2 Participant visibility

Actor may only read participants belonging to the resolved Room/session.

### 23.3 Leave

Only the actor owning the membership may leave it, except future moderator/admin policy.

### 23.4 No cross-room access

A client cannot select another `room_key` and obtain its participants.

## 24. Database Ownership

### 24.1 No new SQLite

WORLD-01 uses the existing persistence host.

### 24.2 Ownership

A future Social World persistence module should own:

- `CafeSession`;
- `CafeParticipant`;
- future social activity envelope only when justified.

It must not own:

- `GroupDrop`;
- `ActiveMatch`;
- Telegram events;
- Telegram outbox;
- Café wallet;
- Tavern sessions.

### 24.3 Existing SQLite surfaces

Current repository already contains several SQLite stores, including:

- TCG database from `src/db/models.py`;
- `bot_ia_economy.sqlite3`;
- Tavern/memory SQLite;
- `telegram_rooms.sqlite3`;
- `bot_ia_events.sqlite3`.

WORLD-01 must not create a new database file.

### 24.4 Migration

No migration is created in WORLD-01-A.

The next implementation phase must first choose the existing persistence host and define a migration owned by the Social World persistence module.

## 25. Failure Model

### TMA failure

No backend state is mutated merely because the page failed to render.

### Telegram failure

A failed Telegram context resolution means no Room authorization.

### SQLite failure

Fail closed:

- no join;
- no fabricated participants;
- no fabricated activity;
- no empty success response.

### Character data unavailable

Return a controlled availability state such as `unknown` or a structured degraded error.

Do not claim a character is available when the source failed.

### Activity unavailable

Do not return `none` if the owner query failed.

Return a controlled unavailable/degraded state.

### Partial state

Never combine authoritative data from one subsystem with a fabricated default from another subsystem.

## 26. Security Invariants

WORLD-01 implementation must preserve:

1. no forged Actor;
2. no forged Room;
3. no cross-room participant visibility;
4. no unauthorized join;
5. no unauthorized leave;
6. one active CafeSession per Room;
7. one active participant membership per Actor/session;
8. persistence failure never becomes an empty state;
9. TMA buttons never grant authority;
10. `initDataUnsafe` never grants authority;
11. Cafe character identity never maps to a physical WebChat resource;
12. TCG ownership remains outside Social World;
13. Telegram routing remains centralized;
14. 2F-8S physical ownership remains centralized.

## 27. Observability

WORLD-01 should emit domain events:

- `session_join`;
- `session_leave`;
- `session_expired`;
- `participant_seen`.

Minimum event envelope:

```text
event_id
actor_key
room_ref
session_id
timestamp
outcome
reason
correlation_id
```

The event envelope is for Social World observability.

It must not turn `TelegramEventLedger` into a universal event store.

## 28. Testing Plan

Tests should be focused on the first implementation.

### W01 — join

Valid actor + valid Room + membership → active session/member.

### W02 — duplicate join

Same actor joins twice → one membership.

### W03 — leave

Actor leaves → membership no longer active.

### W04 — expired session

Expired session cannot be presented as active.

### W05 — wrong room

Actor with valid Telegram identity but foreign Room context → deny.

### W06 — unauthorized actor

Invalid/unknown actor → deny.

### W07 — participant visibility

Actor sees only the resolved Room's participants.

### W08 — no participants

Lobby with no participants is valid as a state, but it is not evidence that persistence failed.

### W09 — existing participants

Second/third actor sees existing members of the same Room.

### W10 — character availability

Availability is returned without browser startup.

### W11 — current activity summary

DROP/DUEL ownership is projected without duplicate persistence.

### W12 — duplicate button action

Repeated join/leave request is idempotent.

### W13 — invalid TMA auth

Invalid `initData` → 401/deny.

### W14 — invalid Room context

Unresolvable or forged context → deny.

### W15 — persistence failure

SQLite error → controlled failure, never fake empty Lobby.

### Additional critical assertions

- 0 participants;
- 1 participant;
- 2+ participants;
- expired membership;
- two concurrent joins;
- cross-room read;
- invalid callback/action;
- unavailable character source;
- unavailable activity owner.

No full-suite expansion is required in WORLD-01-A.

## 29. Performance

Target:

`idle ≈ practically no work`.

WORLD-01 uses request/event driven state changes.

No:

```
scheduler
→ every minute
→ ask whether somebody is in Café
```

No continuous heartbeat is required for WORLD-01.

`last_seen_at` is updated by meaningful requests.

Future presence engine belongs to WORLD-02.

No IA is required for Lobby operation.

## 30. IA Boundary

WORLD-01 works entirely without AI.

Required capabilities:

- join;
- leave;
- view;
- basic participant listing;
- character availability;
- activity summary.

Character AI is a future feature.

No scheduler→AI loop is permitted.

## 31. Visual Boundary

The first visual implementation only needs to support:

- Café Otaku title;
- Room;
- tables as derived layout;
- participants;
- characters;
- current activity;
- entry/leave actions.

Temporary assets are acceptable.

The logical model must not depend on:

- asset filename;
- rendering engine;
- specific art provider;
- browser automation.

Future visual assets may come from:

- Adobe Express;
- OpenArt;
- Topview.

Replacing art assets must not require domain changes.

## 32. General Chat Boundary

Telegram GENERAL remains:

- human conversation;
- cards;
- trivia;
- debates;
- polls;
- events.

The TMA Lobby is not a second chat.

It does not mirror the full GENERAL history.

## 33. Topics Boundary

Existing topics remain independent:

- Noticias;
- Anime antiguo;
- TCG;
- Pedidos;
- Soporte;
- other configured topics.

WORLD-01 consumes the existing routing authority.

No parallel topic router.

## 34. 2F-8S Boundary

WORLD-01 does not modify:

- `PhysicalWebChatResourceAuthority`;
- `PhysicalLifecycleReconciliation`;
- `WebPhysicalIdentity`;
- QWeb adapter;
- Playwright adapter;
- Supervisor;
- TaskEngine;
- TaskScheduler.

No Social World call is allowed to:

- open a browser;
- claim a physical resource;
- create a WebQueue;
- create a second WebChat;
- create a physical lock.

If a future character action requires WebChat, that action must enter through the existing TaskEngine/Scheduler and physical authority chain in a separate approved phase.

## 35. Implementation Sequence

After this design is approved:

### Phase W01-B — persistence contract

Define exact Social World persistence owner and migration.

No runtime yet until schema review.

### Phase W01-C — Telegram Mini App auth/context

Implement:

- Telegram `initData` validation;
- Actor derivation;
- trusted launch context;
- Room resolution;
- membership authorization.

### Phase W01-D — CafeSession/Participant service

Implement:

- session lifecycle;
- join/leave;
- expiry;
- participant listing;
- transaction boundaries;
- idempotency.

### Phase W01-E — read models

Expose:

- character availability;
- current activity summary.

No AI.

### Phase W01-F — TMA Lobby

Implement the visual client against the approved API.

### Phase W01-G — integration/QA

Run W01 tests plus targeted regression tests around Telegram routing/auth and protected 2F-8S boundaries.

No phase may silently expand into Social Scheduler, WORLD-02 presence, moderation engine, or character AI.

## 36. Open Questions

These remain intentionally unresolved:

1. Which existing SQLite host should own the new Social World tables?
2. Exact `CafeRoom` persistent/derived representation beyond TelegramRoomRouter.
3. Exact Telegram membership verification API path for the Mini App backend.
4. Exact Mini App launcher configuration in BotFather.
5. Exact trusted context token format.
6. Exact session TTL.
7. Exact participant stale/expiry policy.
8. Exact character availability adapter for the current character sources.
9. Exact activity adapter interface for `GroupDrop` and `ActiveMatch`.
10. Exact API response schemas and error codes.
11. Exact TMA public hosting URL.
12. Whether the existing FastAPI process or another existing HTTP host becomes the single API host.

These are design questions, not permissions to implement speculative infrastructure.

## 37. Self-review

### duplicated entity

`CafeTable` was deliberately rejected as persistent in WORLD-01.

### duplicated persistence

No new SQLite and no duplicate TCG/drop/duel persistence.

### TMA authority

TMA is explicitly non-authoritative.

### Telegram replacement

Telegram remains the community/history/topic layer.

### always-on process

No Social World daemon is required.

### AI dependency

Lobby works without AI.

### cross-room leak

Authorization is bound to resolved Room and session.

### cross-user leak

Participant visibility is constrained to the resolved session; membership ownership controls leave.

### 2F-8S bypass

No browser, physical resource, second WebChat, or physical lock is introduced.

### unnecessary dependency

WORLD-01 depends on existing Telegram routing/security and SQLite/runtime surfaces only.

### persistence failure

Failure is closed, never represented as an empty successful Lobby.

## 38. Architectural conclusion

WORLD-01 should be implemented as a thin Social World domain over existing Telegram and SQLite infrastructure:

```
Telegram
   │
   ├── GENERAL
   ├── TOPICS
   └── Café entry/context
          │
          ▼
      TMA Client
          │
          ▼
   Telegram initData validation
          │
          ▼
     Actor + Room
          │
          ▼
   Social World Service
          │
          ├── CafeSession
          ├── CafeParticipant
          ├── Character Availability
          └── Activity Summary
          │
          ├── GroupDrop / ActiveMatch (read context)
          └── existing Telegram runtime (optional publication)
```

This preserves the WORLD-00-R1 principle:

**Telegram is the home; Café is the interactive visual layer.**

## 39. Stop Condition

WORLD-01-A does not authorize implementation.

Do not create yet:

- CafeSession table;
- CafeParticipant table;
- CafeTable table;
- API endpoints;
- TMA Lobby;
- presence runtime;
- scheduler runtime;
- moderation runtime;
- character AI runtime.

## 40. Result

**READY FOR WORLD-01 DESIGN REVIEW**
