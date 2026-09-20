# Telegram chat access audit — 2026-09-17

## Finding

Telegram bots are public accounts and can be discovered by username or added to groups. Telegram Privacy Mode limits which group messages a bot receives, but it is not an application authorization boundary. The application still needs an explicit authorization policy for the communities it serves.

## Current decision

The platform uses a fail-closed application-level group allowlist:

- `AUTHORIZED_CHAT_IDS` is a comma-separated list of Telegram group/supergroup IDs.
- An empty or malformed allowlist authorizes no group.
- Group/supergroup traffic is ignored before member synchronization when the chat is not allowlisted.
- Private access is split by purpose:
  - `ALLOW_USER_PRIVATE_CHAT=true` permits normal user-facing private features such as Sunna's games, inventory, points and Chie onboarding.
  - `ALLOW_ADMIN_PRIVATE_CHAT=true` permits the configured owner to use administrative/private operator surfaces.
- Other private users are not given administrative privileges merely because private chat is enabled.
- Channel posts are accepted only from the explicitly configured `MEDIA_STORAGE_CHAT_ID`.
- Points/balance are never used as the access-control mechanism.

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

This ordering is intentional: unauthorized normal updates must not create member activity, wake social routines, spend points, create requests, invoke AI, or otherwise mutate application state.

The only intentional onboarding exception is Chie's exact `/configurar` command in a group/supergroup from a real Telegram administrator. This permits initial setup before the group ID is known to the allowlist. The bootstrap path is narrow, does not enable general group traffic, and verifies the sender's Telegram admin status directly.

## Configuration

Example:

```dotenv
AUTHORIZED_CHAT_IDS=-1001234567890,-1009876543210
ADMIN_USER_ID=123456789
ALLOW_USER_PRIVATE_CHAT=true
ALLOW_ADMIN_PRIVATE_CHAT=true
MEDIA_STORAGE_CHAT_ID=-1005555555555
```

The group IDs should be the actual Telegram `chat.id` values returned by updates. Configuration is local and belongs in `.env`; secrets are not committed.

## Callback identity

For callback queries, authorization uses `callback_query.from_user`, i.e. the person who actually pressed the button. It never trusts the `from_user` stored on the bot-authored message containing the inline keyboard. This prevents forwarded/stale keyboards from being evaluated against the wrong identity.

## Background senders

Durable/background senders such as WildWaifu, Trivia and Cami Publisher re-check the current community allowlist before sending. A chat removed from `AUTHORIZED_CHAT_IDS` therefore cannot continue receiving new automated messages merely because a task was already queued.

## Tests

`tests/test_access_control.py` covers:

- authorized supergroup reaches the handler;
- unauthorized group is blocked before the handler;
- normal-user private access can be enabled;
- owner private access can be restricted independently;
- all-private access can be disabled;
- malformed group allowlists fail closed;
- callback queries authenticate the clicking user;
- Chie's exact bootstrap command is the only onboarding exception;
- authorized media-vault channel posts are accepted;
- unauthorized channel posts are blocked.

## Telegram platform controls

Telegram documents Privacy Mode as a message-receipt filter for groups; it is enabled by default for bots except bots added as administrators. Telegram also documents `/setjoingroups` for bots that should not be addable to groups. These settings are defense-in-depth controls; the application's explicit allowlist remains the authoritative community authorization rule for this project.
