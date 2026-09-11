# Community Telegram Bot

Modular Telegram bot platform built around one rule: **local code first, AI second**.

## Four cooperating bot identities

The project runs as four separate Telegram bots that share one authoritative database/services layer:

1. **Cari** — community presence, social interaction and moderation.
2. **Sunna** — WaifuMon, encounters, collection, progression, combat and trivia.
3. **Cami** — media catalog, requests, publication, analytics and diagnostics.
4. **Chie** — onboarding, forum setup, welcome/verification, rules and coordination.

The bots are intentionally separate Telegram identities, while the local Core remains authoritative for shared state, points, requests, media and configuration.

## Windows: the simple way

The recommended entry point is **BotManager.exe**. It opens a small desktop setup screen before the bots are started.

1. Enter the Telegram link/username and token for **Cari, Sunna, Cami and Chie**.
2. Enter at least one external AI API key (Gemini, Groq, Cerebras or OpenRouter). This is required by the desktop setup so Cari/Cami are not started with an incomplete AI configuration.
3. Optionally choose the preferred provider and model, then add the admin Telegram ID and media-vault chat ID.
4. Press **Guardar configuración** and then **Comenzar**.
5. BotManager starts the four bot processes and gives each one its own start/stop control.

Secrets are saved only in the local `.env` file. `.env` and runtime data are ignored by Git.

### Build the Windows package

From Windows with Python 3.12 installed:

```bat
tools\build_launcher.bat
```

The build creates:

```text
dist\BotManager.exe
dist\bots\Cari.exe
dist\bots\Sunna.exe
dist\bots\Cami.exe
dist\bots\Chie.exe
```

GitHub Actions also contains a Windows packaging workflow that can be run manually or from a `v*` tag and publishes the same package as a build artifact.

## Shared points

Every successful waifu capture can award community points. Points belong to the player + community and use an auditable transaction ledger. Fan requests spend those same points.

## Fan requests: persistent ticket number

Every paid fan request receives a database-generated request number shown to humans as `Pedido #123`. The internal `request_id` remains the authoritative reference.

## Telegram as a storage vault

A private Telegram group or channel can be configured as the media vault/inbox with `MEDIA_STORAGE_CHAT_ID`. Telegram `file_id` values are reused so images do not need unnecessary local copies.

## Wild waifu loop

Public wild encounters are capped at class C. Higher-rarity candidates are routed through the private approval path instead of appearing as normal public encounters.

## API-saving strategy

- Commands, moderation rules, points and game rules remain local.
- User data and stats come from the database/services.
- Games use deterministic local rules.
- AI is an escalation path rather than the default handler.
- Provider settings are configurable so Gemini, Groq, Cerebras or OpenRouter can be wired behind the Brain layer.

## Architecture

```text
Telegram
   ↓
Core
   ↓
Events / Modules / Services
   ↓
Brain policy
   ↓
Optional LLM provider
   ↓
SQLite WAL
```

The social subsystem follows:

```text
wake → observe → decide → acquire turn → act or wait → reschedule
```

A wake is only an opportunity to inspect the chat. Human activity, bot cooldowns, event cooldowns and presence/fatigue can all result in silence.

## Run from source

Copy `.env.example` to `.env`, configure the tokens and settings, install dependencies and run:

```bat
python -m app.launcher
```

For a single identity without the desktop manager, use its module, for example:

```bat
python -m app.bots.cari
```
