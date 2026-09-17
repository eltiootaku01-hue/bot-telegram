# Telegram chat access audit — 2026-09-17

## Finding

Telegram bots are public accounts and can be discovered by username or added to groups. Telegram's Privacy Mode limits which group messages a bot receives, but it is not an application authorization boundary. Telegram also provides `/setjoingroups` to disable adding a bot to groups entirely when group operation is not desired. The application must still authorize the chats it is intended to serve. See the official Telegram bot documentation.

## Decision

The platform now uses a fail-closed application-level group allowlist:

- `AUTHORIZED_CHAT_IDS` is a comma-separated list of Telegram group/supergroup IDs.
- An empty or malformed allowlist authorizes no group.
- Private chat is allowed only for `ADMIN_USER_ID` when `ALLOW_ADMIN_PRIVATE_CHAT=true`.
- Other private users, channels, and unauthorized groups are ignored before member synchronization and module routing.
- Points/balance are not used as an access-control mechanism.

## Enforcement point

```text
Telegram Update
    ↓
ChatAccessMiddleware
    ↓ allowed
MemberSyncMiddleware
    ↓
ModuleRegistry / routers / services
    ↓
Persistence / economy / AI / routines
```

This ordering is intentional: an unauthorized update must not create member activity, wake social routines, spend points, create requests, invoke AI, or otherwise mutate application state.

## Configuration

Example:

```dotenv
AUTHORIZED_CHAT_IDS=-1001234567890,-1009876543210
ADMIN_USER_ID=123456789
ALLOW_ADMIN_PRIVATE_CHAT=true
```

The group IDs should be the actual Telegram `chat.id` values returned by updates. Configuration is local and belongs in `.env`; secrets are not committed.

## Tests

`tests/test_access_control.py` covers:

- authorized supergroup reaches the handler;
- unauthorized group is blocked before the handler;
- private access is limited to the configured administrator;
- empty/malformed group allowlists fail closed.

## Telegram platform controls

Telegram documents Privacy Mode as a message-receipt filter for groups; it is enabled by default for bots except bots added as administrators. Telegram also documents `/setjoingroups` for bots that should not be addable to groups. These settings are useful defense-in-depth controls, but the application allowlist remains the authoritative authorization rule for this project.
