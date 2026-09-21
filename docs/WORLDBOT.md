# WorldBot — presentador neutral del Mundo de Juego

## Arquitectura

WorldBot is a transport adapter, not a game owner.

```text
GAME WORLD
   ↓
GameWorldEvent
   ↓
WorldRuntime
   ↓
PresenterKind.WORLD_BOT / key=world
   ↓
WorldBot
   ↓
Telegram
```

The event state, economy, encounters, rewards and canonical world state remain in the existing World Core.

## Runtime contract

`app/bots/world.py`:

- requires `BOT_TOKEN_WORLD`;
- authenticates it with `getMe`;
- initializes the shared world catalog;
- starts `WorldPresentationModule` with `PresenterKind.WORLD_BOT` and key `world`;
- stays alive while the durable World Runtime claims and publishes events.

It deliberately does not create a Dispatcher or poll updates. Telegram documents `getMe` as a way to test a bot token, while `sendMessage` is the outbound text transport and returns the sent Message on success. citeturn713348search0turn713348search11

Telegram bots cannot initiate conversations with users, so the neutral presenter is designed for authorized community publication rather than unsolicited private contact. citeturn713348search1

## Security and recovery

The existing `WorldRuntime` checks the community allowlist before presenting. A disallowed destination is cancelled instead of sent.

Lease fencing, heartbeat, stale recovery, `delivery_unknown` and human recovery are inherited from the shared World Core; WorldBot does not duplicate those rules.

## Packaging

The Windows build produces `dist\bots\WorldBot.exe`, verifies its existence and size, includes it in the installer, and includes it in the portable ZIP.

CI does not run a live Telegram login for this bot because production tokens are intentionally absent from CI. The build validates the executable itself and the complete package path.

## Configuration

```env
BOT_TOKEN_WORLD=
BOT_LINK_WORLD=
```

`BOT_TOKEN_WORLD` is a production secret and must remain only in the local `.env` file.