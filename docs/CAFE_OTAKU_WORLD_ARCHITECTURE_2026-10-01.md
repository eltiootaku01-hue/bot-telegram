# WORLD-00 — Café Otaku / Social World Architecture Contract

**Estado:** WORLD-00-R1 — ARCHITECTURAL / DESIGN CONTRACT  
**Fecha:** 2026-10-01  
**Repositorio:** eltiootaku01-hue/bot-telegram  
**Base de diseño:** main@2c35a2be8fd8d1a118bd1fa57466827b1758c72b  
**Baseline funcional 2F-8S:** 78d5fa6d0b539991aba1ee700121404678c21e59

---

## Purpose

Definir el contrato técnico del primer mundo social del proyecto: Café Otaku.

El mundo social añade una capa ligera para que personas, Rooms, sesiones temporales, personajes y actividades compartidas tengan un modelo común sin sustituir los subsistemas que ya poseen autoridad de dominio.

Modelo:

    CAFE
      |
      +-- ROOM
            |
            +-- CAFE SESSION
                  |
                  +-- PARTICIPANTS
                  |
                  +-- CAFE ACTIVITY
                        |
                        +-- domain owner
                        |
                        +-- EVENT / REWARD

WORLD-00 es únicamente arquitectura, diseño y auditoría. No autoriza implementación funcional.

## Scope

Incluye Actor, Cafe, CafeRoom, CafeSession, CafeParticipant, Presence, Character, CafeActivity, CafeEvent, límites Telegram/TMA/TCG/economía/IA, ownership de persistencia, autorización, fallos, observabilidad, frontera 2F-8S y fases futuras.

## Non-goals

No incluye tablas, migraciones, endpoints, TMA Lobby, Presence runtime, Party persistente, nueva base SQLite, tercera moneda, microservices, Redis, Kafka, WebSocket permanente, vector DB, segundo WebChat, segunda WebQueue ni rediseño de 2F-8S.

---

# Current Architecture

El árbol real de main@2c35a2be confirma cuatro límites persistentes relevantes:

1. **TCG** en bot_database.db mediante src/db/models.py y servicios TCG.
2. **Economía Café** en config/bot_ia_economy.sqlite3 mediante EconomyDatabase/CafeWalletStore.
3. **Durabilidad Telegram** en config/bot_ia_events.sqlite3 y routing en config/telegram_rooms.sqlite3.
4. **Taberna/meseras** mediante WaitressSessionManager con SQLite suministrado por su caller y schema.sql propio.

Existe además:

- WAITRESS_PROFILES;
- WaitressPresenceManager centrado en meseras;
- WaitressSessionManager para sesiones individuales persona-mesera;
- AuthorityCore;
- TelegramEventLedger;
- TelegramOutboxStore;
- TelegramRoomRouter;
- infraestructura Telegram de Rooms/topics;
- TMA actual de colección TCG;
- infraestructura Discord;
- diseño documentado de Character Engine, conversación y eventos, todavía no equivalente a un runtime social completo.

### Discovery Validation

La verificación contra el árbol actual confirma la necesidad del Social World, pero corrige estos puntos:

- docs/superpowers/specs/ no existe en el HEAD actual; el contrato se ubica en docs/.
- src/api/dependencies.py no existe.
- src/api/security/telegram_auth.py no existe.
- src/api/routers/v1/inventory.py importa ambos módulos inexistentes.
- public/inventory.html usa initDataUnsafe.user para presentación y mantiene una URL de backend placeholder; por tanto no constituye todavía un boundary TMA operativo.
- pyproject.toml no declara FastAPI/Uvicorn ni los runtimes Telegram/Discord usados por run_all.py; esto es una inconsistencia de packaging que queda fuera de WORLD-00.
- src/db/models.py y src/services/drop_service.py no usan idéntico catálogo de rarezas; WORLD no modifica esta discrepancia.

Estas son restricciones del estado actual, no tareas de esta fase.

---

# Three Approaches

## A — Telegram Group First + TMA Companion

### Arquitectura

    Telegram group/topic
            |
         CafeRoom
            |
       CafeSession
            |
     participants
            |
      CafeActivity
            |
    existing domain owners

    TMA
      -> lobby visual
      -> presence
      -> activity view
      -> profile / collection / events
      -> requests server-side

### Coste y complejidad

Coste y complejidad iniciales moderados-bajos porque reutiliza routing de topics, allowlists, ledger, outbox, TCG y economía.

### Ventajas

- Telegram sigue siendo el espacio social real.
- Reutiliza TelegramRoomRouter y AuthorityCore.
- GroupDrop y ActiveMatch ya contienen contexto de grupo/topic.
- TMA puede ser companion sin conexión persistente.
- SQLite/WAL es suficiente para el primer mundo.
- No obliga a tocar 2F-8S.

### Riesgos

- Presence es eventual.
- TMA necesita contexto de Room confiable.
- La autenticación TMA actual está incompleta.

### Impactos

SQLite: se conserva infraestructura actual; no requiere nueva DB.  
Telegram: mantiene papel de autoridad social y de transporte.  
TMA: cliente visual y consumidor de estado server-side.  
2F-8S: sin cambio de ownership.

## B — TMA First

### Arquitectura

    TMA
      |
    CafeRoom
      |
    CafeSession
      |
    participants / activities
      |
    Telegram -> chat / notifications / actions

### Coste y complejidad

Mayor. El backend web pasa a ser punto primario de identidad, contexto de Room, sesión y presencia.

### Ventajas

- UX visual centralizada.
- Mayor libertad futura de interfaz.
- Menos dependencia de la forma del chat.

### Riesgos

- Amplía el perímetro API antes de cerrar autenticación.
- Hace que TMA sea dependencia crítica.
- Puede convertir Telegram en un canal secundario.
- Aumenta sincronización y carga concurrente sobre SQLite.

### Impactos

SQLite: más tráfico concurrente desde API.  
Telegram: de espacio primario a canal auxiliar.  
TMA: front principal.  
2F-8S: puede preservarse, pero aumenta el riesgo de acoplamiento indebido con ejecución física.

## C — Unified Social Runtime

### Arquitectura

                   SOCIAL WORLD
                  /            \
            Telegram            TMA
                  \            /
                   CafeSession
                        |
                   CafeActivity
                        |
              TCG / Economy / Character

### Coste y complejidad

Los más altos para el primer mundo porque resuelve desde el inicio identidad multi-plataforma, sincronización, presencia y conflictos.

### Ventajas

- Modelo general.
- Evolución sencilla hacia varias superficies si se necesita después.

### Riesgos

- Sobrearquitectura para WORLD-01.
- Fuerza una identidad universal demasiado pronto.
- Aumenta invariantes y coordinación entre plataformas.
- Puede inducir nuevas capas que intenten atravesar 2F-8S.

### Impactos

SQLite: mayor coordinación de escrituras.  
Telegram: deja de ser la autoridad social primaria.  
TMA: participante equivalente a Telegram.  
2F-8S: mayor superficie indirecta de riesgo arquitectónico.

---

# Selected Direction

## A — Telegram Group First + TMA Companion

Esta es la dirección contractual para WORLD-01.

La selección se basa en la estructura real del repositorio: Telegram ya posee Rooms/topics, routing exacto, allowlists, ledger y outbox; TCG y economía ya tienen owners; TMA ya tiene una superficie; y 2F-8S ya tiene autoridad física separada.

B y C pueden estudiarse en fases posteriores, pero no son la dependencia primaria de WORLD-01.

---

# Actor Model

Actor identifica un principal externo mediante:

    ActorKey = <platform>:<platform_user_id>

    telegram:123
    discord:123

son actores distintos.

### Campos

    platform
    platform_user_id
    display_name
    authorization_context

Reglas:

- platform_user_id identifica dentro de la plataforma;
- display_name es solo presentación;
- authorization_context se calcula server-side;
- no existe identidad universal automática;
- Telegram y Discord solo se vinculan mediante una operación futura explícita y verificable.

### Relación con db.User

db.User sigue siendo el modelo TCG. En Telegram puede existir la correspondencia operacional Actor(telegram, X) -> User.id=X.

El Social World no debe convertir User.id en identidad multi-plataforma.

El hecho de que el runtime actual de Discord use User(id=discord_id, discord_id=discord_id) no crea una equivalencia automática con un usuario Telegram de igual número.

---

# Cafe Model

WORLD-01 define **un solo Café lógico por despliegue**, anclado al único grupo Telegram autorizado por configuración.

    deployment
       |
    Cafe primary
       |
    authorized Telegram group
       |
    CafeRooms

Decisiones:

- Café no es sinónimo del Telegram group.
- El grupo es el anchor externo autorizado.
- Un Café contiene varias Rooms.
- WORLD-01 no necesita tabla Cafe.
- La identidad lógica inicial del Café es de configuración.
- Multi-tenant queda fuera del primer mundo.

---

# Room Model

CafeRoom representa una sala del Café.

Identidad externa autoritativa:

    (chat_id, message_thread_id)

room_key es un identificador semántico de aplicación proveniente de ROOMS y persistido por TelegramRoomRouter.

Por tanto:

- room_key no es identidad Telegram absoluta;
- (chat_id, message_thread_id) es el binding externo;
- TelegramRoomRouter conserva ownership;
- routing es exacto y fail-closed;
- un topic no registrado no se convierte silenciosamente en general.

---

# CafeSession Model

CafeSession es una **visita social compartida y efímera** dentro de una CafeRoom.

No es una sesión de WebChat, una sesión de mesera, una conexión TMA ni una sesión de polling.

### Invariantes

- una sola sesión social activa por CafeRoom en WORLD-01;
- sesión persistida con TTL;
- creador = primer actor autorizado que hace join sin sesión activa;
- join exige identidad válida, Room autorizada y membership Telegram;
- leave marca la pertenencia como LEFT;
- la sesión termina cuando vence el TTL y no quedan miembros activos;
- una entrada posterior crea una nueva sesión.

Campos conceptuales:

    session_id
    cafe_id
    room_ref
    created_by
    started_at
    last_activity_at
    expires_at
    status

Una Activity social pertenece a una Session y a su Room.

---

# Participant Model

CafeParticipant representa la pertenencia de un principal a una Session.

Campos:

    participant_id
    session_id
    principal_type
    actor_key | character_id
    joined_at
    last_seen
    presence
    role
    status

Principal types:

    ACTOR
    CHARACTER

Rol inicial:

    MEMBER

Membership states:

    JOINED
    LEFT
    EXPIRED

Membership y Presence son dimensiones separadas.

---

# Presence Model

Presence expresa actividad reciente, no pertenencia.

Estados:

    ACTIVE
    IDLE
    AWAY

LEFT y EXPIRED pertenecen a membership.

Señales válidas:

- heartbeat TMA;
- interacción válida con el mundo;
- evento Telegram relevante;
- acción de Activity.

No se requiere WebSocket permanente.

Semántica inicial de lease:

    heartbeat nominal <= 60s
    presence lease = 120s
    ACTIVE  <= 60s
    IDLE    >60s y <=300s
    AWAY    >300s y <=900s
    stale membership >900s sin señal válida

Los tiempos podrán calibrarse por evidencia, pero no se debe romper la separación membership/presence.

Ser miembro del grupo no implica estar actualmente ACTIVE en el Café.

---

# Character Model

Character es una identidad lógica y narrativa.

La superficie existente incluye perfiles para:

    Cari
    Cami
    Sunna
    Chie
    Scarlet
    Chloé

Campos contractuales:

    character_id
    display_name
    profile
    personality_context
    presence_state
    capabilities

WAITRESS_PROFILES puede alimentar la representación inicial.

No se declara todavía un Character Registry persistente.

El schema.sql de WaitressSessionManager contiene otra población de waitresses (cari, luna, scarlet, chloe, mama_mia). La diferencia con WAITRESS_PROFILES requiere un mapping explícito futuro; nunca equivalencia por nombre aproximado.

---

# Character vs Runtime

Prohibido:

    Character == Browser
    Character == WebChatSession
    Character == PhysicalResource

Relación válida:

    Character
       |
    logical interaction
       |
    optional execution layer
       |
    existing physical authority

Cuando se necesite ejecución física, debe pasar por:

    PhysicalWebChatResourceAuthority
    PhysicalLifecycleReconciliation
    WebPhysicalIdentity
    QWeb adapter
    Playwright adapter
    Supervisor
    TaskEngine
    TaskScheduler

No se crea un segundo WebChat ni una segunda WebQueue.

---

# Activity Model

CafeActivity es un envelope de contexto social.

Campos:

    activity_id
    type
    status
    creator
    session_id
    started_at
    finished_at
    result_ref
    external_ref

Estados:

    PROPOSED
    RUNNING
    COMPLETED
    CANCELLED
    EXPIRED
    FAILED

CafeActivity no posee reglas de dominio.

### DROP

    CafeActivity(DROP)
          |
    external_ref -> GroupDrop.id
          |
    drop_service

El motor TCG sigue siendo owner de selección, claim, ownership y mint.

### DUEL

    CafeActivity(DUEL)
          |
    external_ref -> ActiveMatch.id
          |
    match_service

El motor TCG sigue siendo owner de stake, match, cartas y referee.

### GACHA

La Activity aporta contexto social. CafeWalletStore conserva contabilidad, pity y gasto.

### QUIZ

Nueva actividad pequeña solo cuando exista contrato propio.

### CONVERSATION

Puede invocar character/dialogue, pero una salida narrativa nunca modifica directamente wallet, inventario, membership o authorization.

---

# Event Model

CafeEvent sí existe como concepto, pero solo como **world-level container**.

Ejemplo:

    Spring Festival
        |
        +-- DROP
        +-- QUIZ
        +-- GACHA
        +-- REWARD

Campos conceptuales:

    event_id
    name
    status
    starts_at
    ends_at
    rules_ref
    visual_asset_ref

CafeEvent posee temporalidad, descripción, agrupación y referencias.

Los subsistemas concretos poseen resultados, accounting, claims, inventario y duelos.

CafeEvent no sustituye Activity ni los engines de dominio.

---

# Party Decision

No se crea Party en WORLD-01.

    Party = subset of active CafeSession participants

Puede derivarse desde Activity o desde una invitación temporal.

Una tabla Party solo sería justificable con lifecycle independiente, ownership propio, invitaciones durables, permisos propios o matchmaking persistente. No es requisito del primer mundo.

---

# Telegram Boundary

Telegram tiene autoridad sobre:

    group
    topic
    membership externa
    message
    Telegram update
    Telegram identity

Se reutilizan:

- TelegramEventLedger;
- TelegramOutboxStore;
- TelegramRoomRouter;
- AuthorityCore;
- allowlists Telegram.

La membership externa de Telegram no equivale a CafeSession membership.

La entrada al Café es una acción explícita del mundo.

---

# TMA Boundary

TMA es cliente visual:

    Cafe lobby
    presence view
    activity view
    profile
    collection
    events

TMA no posee:

    security authority
    economy authority
    inventory authority
    session ownership
    reward accounting

Todo write relevante debe pasar por server-side authentication y authorization.

---

# TMA Authentication Contract

Flujo obligatorio:

    TMA client
       |
    Telegram.WebApp.initData
       |
    server-side validation
       |
    trusted Actor

Nunca:

    initDataUnsafe
       |
    database authority

La documentación oficial de Telegram indica que initData debe validarse en el servidor y que initDataUnsafe no debe considerarse confiable. La validación utiliza el mecanismo HMAC-SHA-256 derivado del token del bot y debe considerar la antigüedad de auth_date.

Fuente oficial: https://core.telegram.org/bots/webapps

Antes del Lobby deben existir parser/validator server-side, actor derivado de datos validados, rechazo de identidad inválida y control de antigüedad/replay.

El cliente no puede elegir arbitrariamente chat_id o room_key y obtener autoridad por ello. El server resuelve el contexto autorizado y, cuando corresponda, verifica membership.

Telegram documenta getChatMember; para consultar otros usuarios la garantía depende de que el bot sea administrador del chat.

Fuente oficial: https://core.telegram.org/bots/api

---

# Database Ownership

| Dominio | Persistencia actual | Owner | Reusar | Migrar ahora |
|---|---|---|---|---|
| TCG | bot_database.db | src/db/models.py + servicios TCG | Sí | No |
| Cafe economy | config/bot_ia_economy.sqlite3 | EconomyDatabase / CafeWalletStore | Sí | No |
| Telegram room routing | config/telegram_rooms.sqlite3 | TelegramRoomRouter | Sí | No |
| Telegram events | config/bot_ia_events.sqlite3 | TelegramEventLedger | Sí | No |
| Telegram outbox | DB según owner/inyección | TelegramOutboxStore / caller explícito | Sí | No |
| Waitress/Tavern | SQLite suministrado al WaitressSessionManager | WaitressSessionManager | Solo por API existente | No |
| XP auxiliar | config/nakama_xp.sqlite3 | PassiveXPTracker | No como Social World store | No |
| Social World | No existe | owner futuro del dominio social | Reutilizar host existente | No crear DB |

### Target futuro de persistencia social

El host preferido para tablas futuras del Social World es:

    config/bot_ia_events.sqlite3

Esto evita acoplar Social World con TCG, economy o Tavern y reutiliza un archivo SQLite WAL ya dedicado a estado durable de eventos.

Compartir archivo no implica compartir ownership de tablas.

En la futura migración, TelegramEventLedger seguirá siendo dueño semántico de telegram_events y Social World tendrá tablas propias y versionado coordinado.

No se modifica el schema ahora.

### Tablas actualmente confirmadas

    bot_database.db
      users
      cards
      card_instances
      group_drops
      active_matches
      match_history

    bot_ia_economy.sqlite3
      schema_meta
      wallet
      vip
      complaints

    telegram_rooms.sqlite3
      telegram_room_routes

    bot_ia_events.sqlite3
      telegram_events

    WaitressSessionManager DB
      users
      user_inventory
      waitresses
      active_sessions
      supervisor_directives
      telegram_outbox

La coincidencia de nombres de tablas entre bases no autoriza fusión.

---

# Economy Boundary

Existen dos recursos diferentes:

    User.coins
    CafeWalletStore.points

TCG posee coins en bot_database.db.

CafeWalletStore posee points, pity, gacha y economía del Café en bot_ia_economy.sqlite3.

Regla:

    coins != points

No se crea una tercera moneda.

CafeActivity puede producir points del Café o rewards TCG según el subsystem owner.

Una recompensa cross-domain futura debe llevar operation_id/idempotency_key estable. No se promete exactamente-una-vez entre dos bases hasta que el owner de cada efecto lo garantice.

---

# TCG Integration

El flujo social es:

    CafeSession
         |
    CafeActivity
         |
         +-- DROP -> GroupDrop
         |
         +-- DUEL -> ActiveMatch

TCG continúa siendo owner de:

    claim
    match
    stake
    card ownership
    card instance locking
    referee state

Social World no reimplementa esas reglas.

---

# Social Authorization

Capas:

    Actor identity
          +
    Room authorization
          +
    Session membership
          +
    domain authorization
          |
        ALLOW / DENY

| Acción | Actor | Room | Session | Authorization |
|---|---|---|---|---|
| Entrar | Sí | Sí | Puede no existir | identidad válida + Room autorizada + membership Telegram |
| Salir | Sí | Sí | Sí | actor == participant |
| Ver presencia | Sí | Sí | Sí | actor autenticado + Session autorizada |
| Iniciar Activity | Sí | Sí | Sí | participant activo + reglas del tipo |
| Reclamar reward | Sí | Sí | Sí | actor autorizado + owner/idempotencia del dominio |
| Modificar inventario | Sí | Sí | Sí | solo owner TCG/economy; nunca TMA directo |

Invariante:

    VISIBLE != AUTHORIZED

Conocer un participant_id, activity_id o room_key no concede autoridad.

---

# AI Boundary

IA puede usarse para:

    character dialogue
    event narration
    reaction
    world flavor

IA no puede decidir directamente:

    wallet
    inventory
    authorization
    membership
    resource ownership
    reward accounting

Pipeline:

    generated
       |
    validated
       |
    published

Una frase generada acerca de una recompensa no constituye la recompensa real.

---

# Failure Model

## TMA falla

El estado social persiste y Telegram continúa como espacio social principal. El TMA sincroniza al volver.

## Telegram falla

No se aceptan nuevas señales Telegram. El estado durable no se borra ni se interpreta como vacío. Sessions expiran por TTL si corresponde.

## IA falla

Puede fallar la narración sin perder membership, Activity ni accounting.

## SQLite falla

Fail-closed. Nunca devolver saldo cero, inventario vacío o ausencia de usuarios como sustituto de un error de persistencia. No confirmar rewards sin confirmación del owner.

## Character provider / WebChat falla

Character continúa existiendo lógicamente. La capa de ejecución queda fallida/indisponible.

## Activity expires

La Activity termina según su owner; cleanup de recursos queda en el subsystem propietario.

## Participant desaparece

Presence degrada por TTL. La membership termina como EXPIRED, no como LEFT automático.

---

# Offline / Degraded Mode

Con persistencia disponible, el mínimo durable debe conservar:

    identity reference
    session membership
    activity state
    reward result
    Telegram interaction

    TMA unavailable -> world remains consistent
    AI unavailable -> world remains consistent
    WebChat unavailable -> world remains consistent

La IA no es requisito para determinar quién está dentro del Café.

---

# Observability

Eventos conceptuales mínimos:

    session_join
    session_leave
    presence_update
    activity_created
    activity_joined
    activity_completed
    reward_granted
    character_joined
    character_error

Correlación recomendada:

    event_id
    timestamp
    actor_key
    cafe_id
    room_ref
    session_id
    activity_id
    character_id
    outcome
    reason
    correlation_id
    idempotency_key

TelegramEventLedger mantiene ownership de idempotencia de eventos Telegram; no se convierte automáticamente en log general del Social World.

---

# 2F-8S Boundary

WORLD-00 no rediseña 2F-8S.

La Social World layer usa interfaces lógicas y, solo cuando procede, delega a la ejecución física existente.

Queda prohibido:

- invocar un navegador directamente desde el dominio social;
- crear WebChat alternativo;
- crear segunda WebQueue;
- mutar locks físicos desde Social World;
- declarar disponibilidad física por cuenta propia;
- hacer cleanup físico fuera de la autoridad existente;
- bypass de reconciliación o Supervisor.

Componentes protegidos:

    PhysicalWebChatResourceAuthority
    PhysicalLifecycleReconciliation
    WebPhysicalIdentity
    QWeb adapter
    Playwright adapter
    Supervisor
    TaskEngine
    TaskScheduler

Relación:

    Social World
        |
    logical character/activity interface
        |
    existing runtime authority
        |
    optional physical execution

2F-8S conserva ownership de estados físicos y lifecycle físico.

---

# Security Invariants

1. initDataUnsafe nunca es fuente de autoridad.
2. display_name nunca es identidad.
3. telegram:X y discord:X son actores distintos salvo linkage explícito.
4. Room se resuelve antes de operar sobre Session.
5. Session membership se verifica para acciones de Session.
6. Cross-user action requiere permiso de dominio explícito.
7. Rewards requieren idempotencia en el owner.
8. Activity no escribe directamente tablas de TCG/economía.
9. TMA no es fuente de verdad de Session.
10. Telegram group membership no equivale a Session membership.
11. Character no es recurso físico.
12. Social Activity no puede saltarse AuthorityCore cuando una autorización existente sea aplicable.
13. Cross-room references deben rechazarse aunque el ID exista.
14. Error de persistencia no puede degradarse a estado vacío.
15. La identidad entre plataformas no se infiere por coincidencia numérica.

---

# WORLD-00-R1 — Social World Ambient + Scheduling Contract

## Revision purpose

WORLD-00-R1 refines WORLD-00 without changing the selected direction:

    Telegram Group First + TMA Companion

Telegram remains the community's primary social home. Normal chat, General, existing topics, message history and ordinary community activity remain authoritative social surfaces. The Café Otaku Interactive / Café Tables are a complementary visual and contextual social layer.

The intended world behavior is:

    social
    selective
    light
    contextual
    interactive

and explicitly not:

    noisy
    spammy
    permanently active
    dependent on artificial 24/7 bot chatter

This revision is architecture/design only.

## General Chat and Topics remain independent

GENERAL remains a normal Telegram chat surface. It may continue to contain:

    human conversation
    cards
    drops
    trivia
    debates
    polls
    elections
    mini-games
    events
    character interactions

Existing topics remain independent Telegram spaces, including news, older anime, TCG, orders, support and other configured topics.

The TMA does not replace Telegram chat, topics or message history.

The Café is a layer over the community:

    Telegram = community + conversation + history
    TMA = visual interactive companion

The Café must not silently move all community activity into the TMA.

## Café Interactive surface

The Café may expose:

    Lobby
    Tables
    Participants
    Characters
    Activities
    Events
    Collection
    Profile

These are views and interaction surfaces of the Social World. They do not acquire authority over Telegram, TCG, economy, authorization or physical execution merely by being displayed in TMA.

## CafeTable contract

CafeTable is introduced as a logical concept, not as a required persistent table.

A table represents:

    small participant group
    + context
    + optional activity
    + optional characters

Example:

    Table 1
      Jonh
      Pedro
      Ana
      Cari

      Activity: Quiz

WORLD-00-R1 requires a design decision before persistence: determine whether a table is a derived view of a CafeSession or requires an independent lifecycle. A persistent CafeTable is not authorized by this contract.

A table requires its own persistence only if future evidence demonstrates independent lifecycle, durable identity, independent permissions, durable invitations, matchmaking or another ownership boundary that cannot be represented by CafeSession.

## Telegram <-> Café relationship

The Social World is not isolated from Telegram.

    Telegram
        ↕
    Cafe World

A Café activity may produce a result that is surfaced through the appropriate Telegram chat/topic. Conversely, a relevant Telegram message or event may become an input trigger for a Café interaction.

The direction of causality must still respect domain ownership and authorization. A Telegram event does not bypass Room, Session or domain gates; a Café result does not acquire permission to publish merely because it originated in the TMA.

# SocialScheduler Contract

SocialScheduler is a conceptual domain service that decides when a social action is worth attempting.

It is not a perpetual publisher and not one daemon per feature.

The scheduler consumes contextual signals and evaluates:

    SHOULD_ACT_NOW?

The result is exactly one of:

    YES
    NO
    DEFER

NO ACTION is a valid successful outcome.

The preferred scheduling model is next-action based:

    current time
        ↓
    next_action_at
        ↓
       sleep
        ↓
       wake
        ↓
    evaluate

The scheduler should prefer next_action_at over continuous polling. When no work is scheduled, the runtime sleeps. Future implementation should reuse the existing scheduler/runtime infrastructure rather than create one process per feature.

## Social conditions

Before publishing or starting an activity, the conceptual evaluation context includes:

    current time
    day
    date
    timezone
    active participants
    recent activity
    cooldown state
    content budget
    target topic
    activity type

These inputs form policy context; they do not themselves grant permission to publish.

## Participation Gate

Interactive activities must pass a ParticipationGate.

Conceptually:

    required_players = 2
    participants = 0 -> DEFER
    participants = 1 -> DEFER
    participants = 4 -> MAY START

The exact minimum is owned by the activity contract.

An activity that requires players must not repeatedly publish invitations when the participation minimum cannot be met.

Presence rules remain distinct from Telegram group membership.

## Presence Gate

Presence affects whether an activity should start:

    0 participants
        -> no interactive event

    1 participant
        -> individual interaction may be allowed

    2+ participants
        -> social activity may be allowed

    N participants
        -> group activity may be allowed

This does not authorize artificial participants. Character availability is not equivalent to human participation.

## Quiet Periods

The scheduler recognizes conceptual activity modes:

    QUIET
    NORMAL
    PEAK
    SPECIAL_EVENT

Quiet periods may include quiet hours, low-activity periods and maintenance windows.

During a quiet period, the scheduler suppresses unnecessary:

    trivia
    event spam
    card posts
    character chatter

A special date does not override quiet, safety or budget rules automatically.

## Calendar Gate

Special dates may be represented as:

    special date
    special day
    scheduled event
    anniversary
    season
    festival

A special date is an input, not an automatic publication command.

The conceptual decision is:

    special date
        +
    activity
        +
    budget
        +
    rules
        ↓
    SHOULD_ACT_NOW?

No assumption is made that every special date deserves automated content.

## ContentBudget

ContentBudget is a conceptual policy boundary.

Budgets may be scoped by:

    topic
    activity type
    day

The contract supports:

    daily limits
    cooldowns
    remaining budget
    exhausted budget

Definitive numeric limits are deliberately deferred.

Examples of separately budgetable categories include:

    news
    cards
    trivia
    character interactions
    events

When a budget is exhausted, the correct result is:

    NO PUBLICATION

not substitution with another automated post.

## Anti-spam contract

Any automatic publication candidate should be evaluated against conceptual state:

    last_post_at
    cooldown
    daily_count
    daily_limit
    reason

An optional content_signature may prevent materially duplicate content.

A failed gate produces:

    NO PUBLICAR

The system must not retry immediately merely because an action was suppressed. A future next_action_at must be calculated according to policy.

## Character Triggering

Characters do not speak continuously.

A character interaction requires a meaningful character_trigger, such as:

    user enters
    special event
    activity starts
    activity ends
    contextual response

Character output is also subject to character_cooldown.

character availability and character speaking are separate states:

    available != actively speaking

A waitress/character may be visibly available in the Café without sending messages.

The Social World must not simulate users or have characters converse indefinitely with one another.

## AI Cost Gate

AI execution is event-driven:

    on demand
    or
    meaningful social trigger

Valid triggers may include:

    conversation
    activity
    event
    character interaction

The scheduler must never be defined as:

    every minute
        ↓
    call AI

AI failure may suppress narration while preserving social state.

## Normal Telegram interactions and Action Buttons

Common social actions should be discoverable visually without requiring users to learn commands.

Conceptual actions include:

    [☕ Entrar al Café]
    [🪑 Ver Mesas]
    [🎮 Jugar]
    [🎴 Cartas]
    [✨ Eventos]
    [👩‍🍳 Personajes]

Activity actions may include:

    [Participar]
    [Ver resultado]
    [Salir]

TCG actions may include:

    [Ver carta]
    [Mi colección]
    [Jugar duelo]

Commands remain valid as:

    shortcut
    admin tool
    advanced-user path
    fallback

Buttons do not erase existing command support.

## Contextual Action Contract

Buttons are contextual and should expose only currently useful actions.

Examples:

    no session
        -> Entrar

    active session
        -> Ver Mesa / Salir

    active activity
        -> Participar / Estado

    completed activity
        -> Resultado

The UI should not present actions that are impossible in the current state.

The same authorization gates apply whether an action arrives through a button or a command.

## ContentSafetyGate

ContentSafetyGate is a conceptual boundary for incoming messages/media and future social publishing flows.

Pipeline:

    incoming message/media
        ↓
    classification
        ↓
    topic policy
        ↓
    ALLOW / REVIEW / QUARANTINE / REJECT

The gate does not replace Telegram's platform rules or existing authorization.

## Adult / NSFW topic boundary

An adult topic requires explicit:

    policy
    rules
    moderation level
    report path

The architecture must never infer:

    NSFW topic == everything allowed

Decisions must respect:

    platform rules
    server/community policy
    topic rules

Relevant decisions should preserve enough evidence for audit without retaining content unnecessarily.

## Quarantine

Potentially problematic content may enter:

    QUARANTINED

instead of being published immediately when policy requires review.

Conceptual decision evidence:

    message/media reference
    classification
    reason
    timestamp
    actor
    topic
    decision

Data minimization applies. The contract does not authorize indefinite retention of message/media content.

## Report and moderation actions

Where the actor has permission, visual actions may include:

    [🚩 Reportar]
    [🔇 Silenciar]
    [🚫 Bloquear]

Normal users must not receive administrative controls.

The system is designed to reduce risk, detect content, apply rules and retain relevant decision evidence. It does not guarantee that an external platform will never take moderation or account action.

# Social World + Normal Chat

The intended boundary is:

    TELEGRAM
        |
        +-- GENERAL
        |     +-- conversation
        |     +-- trivia
        |     +-- cards
        |     +-- debates
        |
        +-- TOPICS
        |     +-- news
        |     +-- anime
        |     +-- TCG
        |     +-- orders
        |     +-- support
        |     +-- other configured topics
        |
        +-- CAFÉ
              +-- lobby
              +-- tables
              +-- characters
              +-- activities

        |
     BACKEND
        |
    Social World

The Café does not replace the other Telegram spaces.

## Ambient-presence principle

The world should feel alive without behaving like an always-on fake conversation.

Explicitly prohibited by this contract:

    bot permanently conversing
    bot simulating users
    characters speaking to each other indefinitely
    AI executing continuously
    scheduler firing without participants
    per-feature autonomous daemons

The desired property is:

    alive when relevant
    quiet when irrelevant

## Runtime reuse

Future scheduling, social activity and moderation work should reuse:

    existing Telegram poller/webhook runtime
    existing TaskScheduler
    existing persistence
    existing event infrastructure

No independent process is introduced for:

    news
    cards
    trivia
    characters
    events
    Café
    moderation

unless future evidence demonstrates a necessary ownership/runtime boundary.

# WORLD-00-R1 Observability Additions

The conceptual Social World event vocabulary is extended with:

    scheduler_evaluated
    scheduler_deferred
    scheduler_skipped
    content_budget_exhausted
    activity_deferred
    presence_gate_failed
    character_triggered
    character_suppressed
    content_quarantined
    content_rejected
    moderation_reported

Recommended correlation fields remain:

    event_id
    timestamp
    actor_key
    cafe_id
    room_ref
    session_id
    activity_id
    character_id
    outcome
    reason
    correlation_id
    idempotency_key

# WORLD-00-R1 Testing Contract

Future implementation must be able to demonstrate:

    no spam
    quiet hours
    daily budget
    cooldown
    participation gate
    presence gate
    date/time gate
    special date handling
    button actions
    contextual actions
    duplicate action protection
    moderation decision
    quarantine
    cross-room isolation

Critical cases:

    0 participants
    1 participant
    2 participants
    high activity
    low activity
    special date
    quiet hour
    daily limit reached
    duplicate trigger

Testing is a future implementation gate. WORLD-00-R1 does not authorize test-code changes in this phase.

# WORLD-00-R1 Performance Contract

The first Social World remains designed for:

    few processes
    SQLite
    event-driven work
    sleep when idle
    no continuous AI generation
    no per-feature daemon

The architecture does not introduce:

    Redis
    Kafka
    microservices
    heavy scheduler cluster

without future evidence establishing a concrete need.

# WORLD-00-R1 Self-review

The refinement was checked conceptually against:

    chat replacement
    TMA replacement
    scheduler over-polling
    continuous AI
    artificial character chatter
    duplicate feature daemons
    moderation bypass
    authority confusion
    cross-room leakage
    2F-8S bypass

Required outcomes:

- Telegram remains the primary community/social home.
- TMA remains a companion visual interface.
- CafeTable remains non-persistent until independent lifecycle is proven.
- SocialScheduler is event/next-action driven and may return NO ACTION.
- Participation and presence gates prevent activity without sufficient human context.
- Quiet periods, budgets and cooldowns suppress unnecessary content.
- Character availability is distinct from character speech.
- AI is trigger-driven rather than time-driven.
- Buttons complement rather than replace commands.
- ContentSafetyGate precedes applicable publication/review decisions.
- Adult-topic policy does not bypass platform/community rules.
- No new runtime process or persistence database is authorized.
- No 2F-8S ownership is changed.


---

# Implementation Phasing

## WORLD-01 — Café / Lobby

Futuro objetivo:

    validated Actor
       |
    authorized CafeRoom
       |
    CafeSession
       |
    participants
       |
    character availability
       |
    current activity summary

## WORLD-02 — Presence

Implementar heartbeat, leases, TTL y reconciliación.

## WORLD-03 — Activity adapters

Conectar CafeActivity(DROP) con GroupDrop, CafeActivity(DUEL) con ActiveMatch y nuevas actividades pequeñas cuando tengan contrato.

## WORLD-04 — Economy / TCG effects

Solo cuando los owners demuestren idempotencia de efectos.

## WORLD-05 — Character participation

Añadir Character como principal social y conectar narración bajo límites físicos existentes.

## WORLD-06 — CafeEvent

Añadir festivales/campañas como contenedores de Activities.

Ninguna fase futura debe reabrir las decisiones básicas sin evidencia nueva.

---

# Open Questions

1. Cómo transportar contexto autorizado de Room al TMA cuando el launch no nace directamente de un topic.
2. Mapping explícito Character <-> WaitressSessionManager.
3. Idempotencia con operation_id para recompensas de CafeWalletStore.
4. Detalle de versionado cuando se agreguen tablas Social World a bot_ia_events.sqlite3.
5. Reconciliación de las dos poblaciones de Character/Waitress existentes.
6. Fase específica para completar TMA auth/API y resolver la inconsistencia de packaging.

Estas preguntas no bloquean el contrato conceptual.

---

# Files Changed

WORLD-00-R1 modifica únicamente:

    docs/CAFE_OTAKU_WORLD_ARCHITECTURE_2026-10-01.md

# Files Not Changed

No se modifican:

    src/**
    public/**
    .github/**
    pyproject.toml
    tests/**
    migrations/**
    docs/project_memory/**

No se modifica ninguna pieza de 2F-8S.

# Commit

Commit de revisión:

    docs: refine Cafe Otaku social ambient scheduling contract

Se realizará únicamente sobre la rama documental derivada de main@2c35a2be8fd8d1a118bd1fa57466827b1758c72b.

No se fusionará a main dentro de WORLD-00.

---

# Evidence

## Repository state

HEAD auditado:

    2c35a2be8fd8d1a118bd1fa57466827b1758c72b

Parent:

    1763974f4dc27fb5ea5f66452c0f9b57297aaa76

Functional 2F-8S baseline:

    78d5fa6d0b539991aba1ee700121404678c21e59

Remote branches visibles durante la auditoría:

    main
    diagnostic/2f-8t-qwebengine
    diagnostic/2f-8t-qwebengine-clean

No se observó una rama social remota antes de crear esta rama documental.

## Source evidence

    src/db/models.py
      8d2ed566a76c7e1996678920ae1f01507d8b4aaa

    src/services/drop_service.py
      cdc47ef705930561faca655bf7fa3036ef9ca1ab

    src/services/match_service.py
      9fa2252c2ce0e7bf73e7d82df036e50e855c5baf

    src/bot_ia/interfaces/cafe_economy.py
      aaa76975c9907585ab33b321fa2f06a04110b0fb

    src/bot_ia/persistence/economy.py
      72b12222abf1cfa2442501e8c3957be3d526741d

    src/bot_ia/interfaces/cafe_immersion.py
      d33fd01f549f929a554f27a7f8c3121eee4418bf

    src/bot_ia/core/waitress_session_manager.py
      bf0a73b823e2a2cc7c7ae27b2ec9a5fd6411518c

    src/bot_ia/interfaces/telegram_room_routing.py
      39bceed8981adfd6203a36b4484e20b26d9cddda

    src/bot_ia/interfaces/telegram_security.py
      c626a99c1aa6a39a0d068cc25755e6b405036344

    src/bot_ia/security/authority.py
      dcf960ad92d361848ffffdc848f6806ad6e338d8

    src/bot_ia/interfaces/telegram.py
      06444c1a6e1096b3c6653b09788c03de6bc75e53

    src/bot_ia/interfaces/telegram_event_ledger.py
      a3e4597e7e9ab10e3d2a506afa81b4e710e4d1

    src/bot_ia/interfaces/telegram_outbox.py
      9b8155797ab4486b74db049959123cd5f186f3a5

    src/bot_ia/memory/schema.sql
      7b9d91cdc54e17e27d26032b73c918813d26a25b

    src/api/main.py
      9ae905e83ea57959f71cd941fad3e6849a537c46

    src/api/routers/v1/inventory.py
      01839ffe651656beed0464eea97d5f29cdc4c45

    public/inventory.html
      0ff842c9bbdc3fb8b2e4cca0fd2b4f4228fe2876

    pyproject.toml
      b6540fdf58dd23573e3c2b7689e982159b93941d

## External evidence

Telegram Mini Apps:
    https://core.telegram.org/bots/webapps

Telegram Bot API:
    https://core.telegram.org/bots/api

---

# Unknown

No se infiere:

- path concreto suministrado a cada WaitressSessionManager;
- estado real de producción del FastAPI actual;
- método exacto de lanzamiento del TMA en producción;
- si el bot tiene actualmente privilegios suficientes para verificar otros miembros del group target;
- idempotencia futura de los owners de reward;
- estado de trabajo local no publicado fuera de las ramas remotas visibles.

---

# Self-review

## Placeholder scan

No se detectaron placeholders de implementación sin resolver ni marcadores temporales requeridos para el contrato.

## Contradictions

Se resolvieron explícitamente estas separaciones:

- Cafe != Telegram group.
- Room identity != room_key.
- membership != presence.
- Actor != User universal.
- Character != Browser/WebChat/PhysicalResource.
- Activity != domain engine.
- Event != superentity.
- Party != persistent table.
- TMA != authority.
- Telegram membership != Session membership.
- narrative result != accounting result.

## Ownership

Cada base y cada subsystem owner tiene responsabilidad explícita. Compartir SQLite no implica compartir ownership.

## Dependency scan

El contrato no introduce dependencias runtime y no requiere Redis, Kafka, WebSocket permanente ni vector DB.

## 2F-8S scan

No se asigna ninguna responsabilidad física nueva a 2F-8S y se prohíbe bypass de sus authorities y lifecycle fences.

---

# Result Classification

    WORLD-00-R1 — READY FOR ARCHITECTURE REVIEW

El contrato deja explícitos:

- límites de dominio;
- ownership;
- seguridad;
- fronteras Telegram/TMA;
- persistencia;
- economía/TCG;
- frontera 2F-8S;
- fases de implementación.

WORLD-00-R1 termina aquí.

No se autoriza WORLD-01, CafeSession table, CafeTable table, scheduler runtime, moderation runtime, TMA Lobby, endpoints ni refactors hasta aprobación explícita de este contrato.
