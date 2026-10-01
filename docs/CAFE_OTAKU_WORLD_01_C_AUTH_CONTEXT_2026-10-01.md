# WORLD-01-C — Telegram Auth + Trusted Launch Context

## Scope

WORLD-01-C implements only the authorization boundary before Social World runtime.

Implemented surfaces:

- Telegram Mini App `initData` validation.
- server-derived `AuthenticatedTelegramActor`.
- Main Mini App direct-link trusted context via `startapp/start_param`.
- existing `TelegramRoomRouter`-backed Room resolution.
- Telegram membership verification through the repository's `aiogram` Bot API.
- FastAPI identity and Café authorization dependencies.
- targeted security tests.

Explicitly not implemented:

- `CafeSession` or `CafeParticipant` runtime;
- Lobby/TMA UI;
- Presence;
- Scheduler;
- AI;
- persistence migrations;
- new SQLite/database service;
- browser, WebQueue, Supervisor or 2F-8S changes.

## Telegram initData

Only raw `Telegram.WebApp.initData` is authoritative.

The backend accepts exactly:

```
Authorization: tma <raw initData>
```

`initDataUnsafe` is presentation-only data and never an identity authority.

Validation follows the Telegram Mini Apps WebAppData algorithm:

```
query-string parse
    ->
reject malformed or duplicate keys
    ->
extract hash
    ->
sort decoded key=value pairs except hash
    ->
build data-check-string
    ->
secret = HMAC-SHA256(key="WebAppData", message=TELEGRAM_BOT_TOKEN)
    ->
calculated hash = HMAC-SHA256(secret, data-check-string)
    ->
hmac.compare_digest
    ->
auth_date freshness
    ->
user JSON validation
    ->
server actor derivation
```

The older Telegram Login Widget `SHA256(bot_token)` derivation is not used.

## Freshness

Configuration:

```
TMA_AUTH_MAX_AGE_SECONDS=3600
TMA_AUTH_FUTURE_TOLERANCE_SECONDS=30
```

`auth_date` must be no older than the configured maximum age and may not be in the future beyond the configured tolerance.

## Actor

The validated actor contains:

```
telegram_user_id
actor_key = telegram:<telegram_user_id>
username
first_name
last_name
auth_date
chat_instance
chat_type
start_param
```

`actor_key` is constructed only after HMAC verification.

`chat_instance` is retained as Telegram-provided context information. It is never treated as `chat_id`.

## Trusted launch context

W01-C selects one launcher:

```
https://t.me/<bot_username>?startapp=<opaque_context_reference>
```

For this Main Mini App direct-link flow, Telegram transports the `startapp` value into Mini App `start_param`.

The reference is **server-generated, random, opaque, persisted and server-resolvable**. The stored `issuer` identifies the configured W01-C deployment/issuer for the context registry.

Each reference is registered as one server-side JSON record:

```
config/tma_trusted_contexts/<reference>.json
```

The record binds:

```
issuer
chat_id
message_thread_id
room_key
issued_at
expires_at
revoked_at
reusable
```

The reference contains no Room data and is not derived from a client-selected `room_key`.

It is 256 bits of random token material encoded with URL-safe base64 and prefixed with `tctx_`, for a 48-character value.

References are reusable by multiple authorized members of the same Room. They are not actor-bound.

Context freshness is explicit:

```
TMA_CONTEXT_MAX_AGE_SECONDS=3600
```

A reference may also be explicitly revoked.

No context table and no new SQLite database are introduced.

## Forum Topic boundary

A Forum Topic is not a Room merely because the client supplies a thread number.

A trusted context can only be issued after the existing routing authority resolves:

```
(chat_id, message_thread_id)
        ->
TelegramRoomRouter
        ->
room_key
```

The resolver checks the authoritative route again when the reference is consumed.

Therefore:

- unknown topic -> DENY;
- removed route -> DENY;
- remapped route -> DENY;
- no fallback from unknown topic to `general`.

## Telegram membership

The implementation uses:

```
await Bot.get_chat_member(chat_id, user_id)
```

through the repository's `aiogram` dependency.

Policy:

| Telegram status | Café authorization |
|---|---|
| creator | ALLOW |
| administrator | ALLOW |
| member | ALLOW |
| restricted + is_member=True | ALLOW |
| restricted + is_member=False | DENY |
| left | DENY |
| kicked/banned | DENY |
| unknown | DENY |
| Telegram API/transport/timeout failure | 503 |

The Bot API requires the bot to be an administrator for guaranteed membership lookup of other users.

W01-C does not modify Telegram permissions and does not claim BotFather configuration as completed.

## FastAPI boundary

`get_current_user`:

```
Authorization
    ->
tma header parsing
    ->
initData validation
    ->
AuthenticatedTelegramActor
```

`get_current_cafe_access`:

```
authenticated actor
    ->
start_param trusted reference
    ->
TrustedContextRegistry
    ->
TelegramRoomRouter
    ->
Telegram membership
    ->
CafeAuthorization
```

HTTP mapping:

```
401 invalid Telegram authentication
403 authenticated but unauthorized membership
404 missing / unknown / expired / revoked context
503 authorization dependency unavailable
```

Errors do not expose bot token, raw initData, context secrets, internal SQLite details or stack traces.

The existing API inventory dependency also now exposes the repository's existing SQLAlchemy `DATABASE_URL` through a short-lived `get_db`; no new database or model is created.

## Configuration

Existing canonical secret:

```
TELEGRAM_BOT_TOKEN
```

WORLD-01-C configuration:

```
TMA_AUTH_MAX_AGE_SECONDS
TMA_AUTH_FUTURE_TOLERANCE_SECONDS
TMA_CONTEXT_MAX_AGE_SECONDS
TMA_CONTEXT_ISSUER
```

No context secret is stored or committed.

Runtime context records are ignored by Git:

```
config/tma_trusted_contexts/
```

## Dependency and API verification

Repository evidence shows that the effective Telegram framework is `aiogram` (the tracked package metadata requires `aiogram>=3.28,<4`); `python-telegram-bot` is not a project dependency. W01-C therefore uses aiogram's Bot API.

The authorized branch declares:

```
Python >= 3.14
fastapi>=0.116,<1
uvicorn>=0.35,<1
pydantic>=2.10,<3
aiogram>=3.28,<4
```

Context7 and official documentation were checked for:

- FastAPI `Depends`, `Header` and `HTTPException`;
- Pydantic v2 models and `extra="forbid"`;
- Telegram Mini Apps `initData` and direct-link `startapp`;
- `aiogram` `Bot.get_chat_member`, concrete `ChatMember` types and async Bot lifecycle.

These checks verify API shape, not the presence of a matching local installed environment.

## Launcher prerequisite

The selected launcher is the Main Mini App direct link.

Repository evidence does not prove that the Main Mini App is configured in BotFather. This remains **UNKNOWN**.

No BotFather mutation is performed by W01-C.

## Targeted testing

The W01-C test suite covers:

- valid initData;
- URL-decoding;
- missing/invalid hash;
- duplicate keys;
- malformed query;
- missing/invalid user;
- expired/future `auth_date`;
- wrong bot token;
- signed unexpected fields;
- exact `tma` header;
- no secret/raw initData leakage;
- random opaque reusable context;
- expiry;
- revocation;
- route removal/remap invalidation;
- semantic/unknown reference rejection;
- Main Mini App `startapp` transport;
- existing `TelegramRoomRouter`;
- creator/administrator/member;
- restricted policy;
- left/kicked/banned/unknown;
- returned-user mismatch;
- Telegram API/timeout failure;
- FastAPI 401/503 behavior;
- full auth -> context -> membership allow/deny path.

Live Telegram membership remains mocked in unit tests and requires a real administrator bot plus Telegram connectivity in deployment.

## Security invariants

```
Telegram identity proof
        +
trusted Room selection proof
        +
Telegram membership proof
        +
Cafe policy
        =
ALLOW / DENY
```

Never:

```
TMA client room_key
    ->
ALLOW
```

Never:

```
TMA client actor_key
    ->
identity authority
```

A context reference alone never grants access; membership is evaluated for the authenticated Telegram actor.

## W01-B / W01-D boundary

W01-C does not implement:

- `CafeSession`;
- `CafeParticipant`;
- JOIN / LEAVE;
- persistence expiry runtime;
- Social World Alembic migrations;
- Lobby UI;
- Presence;
- Scheduler;
- AI.

WORLD-01-D is the next phase for the persistence runtime after explicit acceptance of W01-C.

## Out-of-scope issue

The existing `public/inventory.html` / inventory semantic mismatch remains outside W01-C.

No inventory semantics or Lobby UI are changed here.

## 2F-8S boundary

No changes were made to:

- QWeb;
- Playwright;
- WebQueue;
- PhysicalWebChatResourceAuthority;
- PhysicalLifecycleReconciliation;
- TaskEngine;
- TaskScheduler;
- Supervisor;
- browser data;
- physical browser locks.

W01-C has no physical browser dependency.

## Result

The implemented authorization boundary is:

```
Telegram initData
    ->
AuthenticatedTelegramActor
    ->
trusted context
    ->
TelegramRoomRouter
    ->
CafeRoom projection
    ->
Telegram membership
    ->
Cafe policy
    ->
ALLOW / DENY
```

The implementation is ready for W01-D review; W01-D must remain separately authorized.

**READY FOR WORLD-01-D**

**STOP — no CafeSession/CafeParticipant runtime, migration, Lobby, presence, scheduler or AI is implemented by W01-C.**
