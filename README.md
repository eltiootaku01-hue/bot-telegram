# Community Telegram Bot

Modular Telegram bot platform built around one rule: **local code first, AI second**.

## Three cooperating bot identities

The project is designed to be able to run as **three separate Telegram bots** that share one authoritative database/services layer. This is preferable to pretending that one bot has three personalities: each bot can have its own name, avatar, commands, permissions and operational responsibility while the data stays unified.

1. **Community bot** — normal Telegram behavior: greetings, chat, useful replies, moderation, monitoring and community presence. It watches the normal group but does not need to store a copy of every message.
2. **Media/requests bot** — receives the media vault stream, classifies images, applies tags/metadata, understands requests, schedules publication and leaves ambiguous requests in the admin queue. Its administration belongs in the private web panel.
3. **Game bot** — owns waifu encounters, collection, progression, battles and the point economy. Game buttons live here. It can publish/share approved game assets through Telegram without downloading them.

They should **not** communicate by sending messages to one another for every operation. Instead:

```text
                    SHARED DATA / SERVICES
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Community Bot     Media Bot        Game Bot
          │                │                │
   chat/moderation     images/requests   game/points
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                    PostgreSQL/SQLite
```

That makes the "sisters" cheap: the game bot can write a player's points once, and the other bots can read the same balance instead of passing the score through Telegram messages/API calls.

## Shared points

Every successful waifu capture can award **community points** to the player. Points are attached to the player + community and have an auditable transaction ledger. A future requests bot can spend those same points on fan requests.

Example flow:

```text
waifu capture
    ↓
Game Bot
    ↓ +points
shared point ledger
    ↓
Media/Requests Bot
    ↓
"Quiero una imagen de Asuna"
    ↓
points checked/spent
    ↓
request queue
```

The point ledger deliberately lives below the individual bot so a player does not have three independent wallets.

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

Images do not need to be downloaded to the bot's disk just to reuse them. Telegram `file_id` values can be reused by the bot when sending the same media later. This avoids adding external object storage merely for the game library.

The vault should be a **dedicated private group/channel**, not the normal community group. The normal community chat remains the social history; our database stores structured information the system actually needs (members, activity counters, game state, points, requests and media catalog) instead of duplicating every Telegram message unnecessarily.

## Media/requests behavior

The media bot is intended to classify each incoming asset/request into one of three paths:

```text
"esto es para el juego de waifus"
        → game library

"esto es para la página, publicalo en 3 horas"
        → scheduled publication

"¿esto para qué es? mejor le pregunto"
        → admin queue
```

For fan requests, the bot can recognize that a player is spending earned points, extract the requested character (for example Asuna), preserve optional details (for example bunny suit), and leave incomplete/ambiguous requests pending for the admin rather than guessing.

Once an image is approved and tagged, the same asset can be assigned to the game, the website, the community group, or several destinations. Game art additionally maps to character evolution stages.

## Wild waifu loop

Groups can receive a random **waifu suelta** alert after a random delay. Public wild encounters are deliberately capped at **C**:

- Class D: common/default encounter; click the character name.
- Class C: easy encounter; click the character name.
- B/A/S/SS/SSS: **never appear as normal public wild encounters**.
- A B+ candidate is routed to a private owner approval request. Most can simply be rejected.
- A successful capture ends the encounter for the group and awards points.
- After the encounter expires, the buttons disappear and the message becomes `😭 La waifu se fue`.

## Character combat identity

Characters do not use generic attacks only. Each character gets attacks/defenses/specials based on recognizable anime traits, jokes or niche references. Example: Taiga Aisaka has `Golpe de katana de madera`, `¿No sabría hacerse bolita?` and `Golpe de tigre`.

## Data architecture

Telegram identity/activity is persisted independently from AI. Game profiles, collections, timed encounters, one-shot attempts, point transactions, rare-drop approvals, media assets and art-stage mappings are durable database records so all three bots and the future web panel can consume the same authoritative state.

## API-saving strategy

- Commands, moderation rules, points and game rules are local code.
- User data and stats come from the database/services.
- Games use deterministic local rules.
- The media bot should use AI only when classification/reasoning is actually useful.
- The community bot's Brain decides whether a conversational message needs an LLM.
- Repeated/expensive AI work will be cached and batched.
- Providers stay behind an abstraction so Gemini, Groq, Cerebras or OpenRouter can be changed without rewriting the bots.

## Development order

1. Core + module lifecycle.
2. Data layer and member persistence.
3. Three bot domains and shared services.
4. Wild waifu encounters + collection safety + points.
5. Media vault + request queue + authoritative image catalog.
6. Full character catalog, copies → EXP → levels → evolution → art stages and Pokémon-like battles.
7. Brain: intent, context, memory, decision policy and tool routing.
8. Private web administration + publication pipeline.
9. AI providers, caching, fallback and usage monitoring.

## Run

Copy `.env.example` to `.env`, add the Telegram bot token and private media vault chat ID, install dependencies and run `python -m app.main`.
