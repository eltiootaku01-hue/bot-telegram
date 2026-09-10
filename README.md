# Community Telegram Bot

Modular Telegram bot built around one rule: **local code first, AI second**.

## Three bot domains

1. **Chat + monitoring** — conversation, community presence and activity tracking. The Brain/LLM is optional and only used when language reasoning is useful.
2. **Pedidos + imágenes** — request queue, image inbox, metadata/tags and publication ordering. Full administration belongs to the private web panel.
3. **Juegos** — gacha, collection, progression and Pokémon-like deterministic battles. Interactive buttons live only inside game surfaces.

## Telegram as a storage vault

A private Telegram group or channel can be configured as the bot's **media vault/inbox** with `MEDIA_STORAGE_CHAT_ID`. The intended workflow is:

```text
Telegram vault
   ↓
file_id + message_id + metadata
   ↓
local database catalog
   ↓
web approval/tagging
   ├─ game art
   ├─ community publication
   └─ future website
```

Images do not need to be downloaded to the bot's disk just to reuse them. Telegram `file_id` values are designed to be persistent, so the bot can reference the original Telegram media later. This avoids adding an external object-storage service just for the game library.

The vault should be a **dedicated private group/channel**, not the normal community group. The bot can be made administrator there so it receives the full stream of messages needed for the inbox. Telegram documents that bots that are administrators in groups receive all group messages (except messages from other bots). citeturn0search0turn0search1

The normal community chat remains the community chat: Telegram itself keeps the conversation and media there. Our database stores the structured information the bot needs (members, activity counters, game state, media catalog, etc.) instead of duplicating every Telegram message unnecessarily.

## Wild waifu loop

Groups can receive a random **waifu suelta** alert after a random delay. Public wild encounters are deliberately capped at **C**:

- Class D: common/default encounter; click the character name.
- Class C: easy encounter; click the character name.
- B/A/S/SS/SSS: **never appear as normal public wild encounters**.
- A B+ candidate is routed to a private owner approval request. Most can simply be rejected.
- A successful capture ends the encounter for the group.
- After the encounter expires, the buttons disappear and the message becomes `😭 La waifu se fue`.

## Character combat identity

Characters do not use generic attacks only. Each character gets attacks/defenses/specials based on recognizable anime traits, jokes or niche references. Example: Taiga Aisaka has `Golpe de katana de madera`, `¿No sabría hacerse bolita?` and `Golpe de tigre`.

## Data architecture

Telegram identity/activity is persisted independently from AI. Game profiles, collections, timed encounters, one-shot attempts, rare-drop approvals and media assets are durable database records so the future web panel can consume the same authoritative state.

## API-saving strategy

- Commands such as `/ping` are handled locally.
- User data and stats come from the database/services.
- Games use deterministic local rules.
- The Brain decides whether a conversational message actually needs an LLM.
- Repeated/expensive AI work will be cached and batched.
- Providers stay behind an abstraction so Gemini, Groq, Cerebras or OpenRouter can be changed without rewriting the bot.

## Development order

1. Core + module lifecycle.
2. Data layer and member persistence.
3. Three Telegram domains.
4. Wild waifu encounters + collection safety.
5. Media vault and authoritative image catalog.
6. Full character catalog, copies → EXP → levels → evolution and Pokémon-like battles.
7. Brain: intent, context, memory, decision policy and tool routing.
8. Private web administration + publication pipeline.
9. AI providers, caching, fallback and usage monitoring.

## Run

Copy `.env.example` to `.env`, add the Telegram bot token and private media vault chat ID, install dependencies and run `python -m app.main`.
