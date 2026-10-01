# WORLD-01-C — Telegram Auth + Trusted Launch Context

## Scope

WORLD-01-C implements only the authorization boundary before Social World runtime.

Implemented surfaces:

- Telegram Mini App initData validation.
- server-derived AuthenticatedTelegramActor.
- Main Mini App direct-link trusted context using startapp/start_param.
- existing TelegramRoomRouter-backed Room resolution.
- Telegram membership verification through python-telegram-bot.
- FastAPI identity and Café authorization dependencies.
- targeted security tests.

Explicitly not implemented:

- CafeSession or CafeParticipant runtime.
- Lobby/TMA UI.
- Presence.
- Scheduler.
- AI.
- persistence migrations.
- new SQLite/database service.
- browser, WebQueue, Supervisor or 2F-8S changes.

## Telegram initData

Only the raw Telegram.WebApp.initData value is authoritative.

The backend accepts exactly:

    Authorization: tma <raw initData>

initDataUnsafe is not used as an authority source.

The validation algorithm is:

    query-string parse
    -> reject malformed or duplicate keys
    -> extract hash
    -> sort decoded key/value pairs except hash
    -> build data-check-string with newline separators
    -> derive secret with HMAC-SHA256:
       key = WebAppData
       message = TELEGRAM_BOT_TOKEN
    -> calculate HMAC-SHA256 over the data-check-string
    -> hmac.compare_digest
    -> auth_date freshness
    -> user JSON validation
    -> server actor derivation

This is the Telegram Mini Apps WebAppData algorithm. It is not the older Telegram Login Widget SHA256(bot-token) derivation.

## Freshness

The configurable defaults are:

    TMA_AUTH_MAX_AGE_SECONDS=3600
    TMA_AUTH_FUTURE_TOLERANCE_SECONDS=30

Expired auth_date is rejected.

Future auth_date values beyond the configured tolerance are rejected.

## Actor

The internal actor contains:

    telegram_user_id
    actor_key = telegram:<telegram_user_id>
    username
    first_name
    last_name
    auth_date
    chat_instance
    chat_type
    start_param

actor_key is constructed only after HMAC verification. No client-supplied actor_key is accepted.

chat_instance is retained as Telegram context information only. It is never interpreted as chat_id and no conversion is assumed.

## Trusted launch context

W01-C selects one launcher:

    Main Mini App direct link

    https://t.me/<bot_username>?startapp=<trusted_context_reference>

Telegram carries the startapp value into Mini App initData as start_param for this flow.

The reference is opaque and HMAC-derived from:

    TMA_CONTEXT_ISSUER
    chat_id
    message_thread_id
    room_key

using:

    TMA_CONTEXT_SECRET

The secret must contain at least 32 characters.

The reference has no semantic room data and is reusable by multiple members of the same Room.

No context table is introduced.

The existing TelegramRoomRouter remains the Room authority:

    (chat_id, message_thread_id) -> room_key

The resolver only accepts references that correspond to currently registered authoritative routes.

Consequences:

- arbitrary room_key values are not accepted;
- a semantic string such as general is not a valid context reference;
- removing a registered route invalidates its derived context;
- rotating TMA_CONTEXT_SECRET invalidates previously derived references;
- the reference is not actor-bound, so multiple authorized Room members may reuse the same launch reference;
- chat_instance is not converted into chat_id.

A context reference does not grant membership by itself. Membership is checked after context resolution.

## Forum topic boundary

A Forum Topic is not a Room just because the client supplies a thread number.

A trusted context can only be issued for a route already present in TelegramRoomRouter:

    chat_id + message_thread_id
        ->
    TelegramRoomRouter
        ->
    room_key

Unknown topic:

    DENY

There is no unknown-topic fallback to general.

## Telegram membership

The implementation calls:

    await Bot.get_chat_member(chat_id, user_id)

through python-telegram-bot.

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

The Bot API requires the bot to be an administrator for guaranteed membership lookup of other users. W01-C does not modify Telegram permissions and does not claim BotFather configuration as completed.

## FastAPI boundary

get_current_user:

    Authorization
        ->
    initData validation
        ->
    AuthenticatedTelegramActor

get_current_cafe_access:

    authenticated actor
        ->
    start_param trusted context
        ->
    TelegramRoomRouter
        ->
    Telegram membership
        ->
    CafeAuthorization

HTTP mapping:

    401 invalid authentication
    403 membership denied
    404 missing or unknown trusted context
    503 authorization dependency/configuration unavailable

Error responses do not include bot token, raw initData, context secret, internal SQLite details or stack traces.

## Configuration

Existing canonical secret:

    TELEGRAM_BOT_TOKEN

New WORLD-01-C configuration:

    TMA_AUTH_MAX_AGE_SECONDS
    TMA_AUTH_FUTURE_TOLERANCE_SECONDS
    TMA_CONTEXT_ISSUER
    TMA_CONTEXT_SECRET

No production value is committed.

## Dependency and API gate

Repository inspection showed Python >= 3.14 and existing FastAPI and python-telegram-bot usage in code, while the main project dependency list did not declare the packages needed by those existing API surfaces.

WORLD-01-C aligns project metadata and CI installation with the implemented boundary:

    fastapi >=0.116,<1
    uvicorn >=0.35,<1
    pydantic >=2.10,<3
    python-telegram-bot >=22.5,<23

The dependency ranges are implementation requirements, not claims about a pre-existing installed environment.

Context7 and official documentation were checked for FastAPI Header/Depends, Pydantic v2 models, Telegram Mini App initData, Telegram direct-link startapp behavior, and python-telegram-bot get_chat_member/lifecycle APIs.

## Launcher operational prerequisite

The selected production launcher requires the Main Mini App to be configured in Telegram/BotFather.

Repository evidence does not prove that BotFather has been configured. That remains an operational UNKNOWN.

No BotFather mutation is performed by W01-C.

## Testing boundary

Targeted tests cover:

- valid initData;
- URL-decoded data;
- missing/invalid hash;
- duplicate keys;
- malformed query;
- missing/invalid user;
- expired/future auth_date;
- wrong bot token;
- unexpected signed fields;
- initDataUnsafe non-authority;
- exact tma header;
- secret material not exposed by validation/API errors;
- opaque reusable trusted context;
- context secret minimum;
- unknown context;
- route-removal invalidation;
- foreign-room context identity;
- semantic Room reference rejection;
- Main Mini App startapp transport;
- creator/administrator/member;
- restricted membership policy;
- left/kicked/banned/unknown;
- returned-user identity mismatch;
- Telegram API and timeout failures;
- FastAPI 401/503 behavior;
- full auth -> context -> membership allow/deny path;
- unexpected actor fields.

Live Telegram membership is intentionally mocked in unit tests and requires a real administrator bot plus Telegram connectivity in deployment.

## Security invariants

    Telegram identity proof
        +
    trusted Room selection proof
        +
    Telegram membership proof
        +
    Café policy
        =
    ALLOW / DENY

Never:

    TMA client room_key
        ->
    ALLOW

W01-C stops at the authorization boundary.

WORLD-01-D is the next explicitly authorized phase for CafeSession/CafeParticipant persistence runtime.
