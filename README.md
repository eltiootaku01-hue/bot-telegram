# Community Telegram Bot

Modular Telegram bot platform built around one rule: **local code first, AI second**.

## Four cooperating bot identities

The project is designed to run as **four separate Telegram bots** that share one authoritative database/services layer. Each bot has its own identity, personality, commands, permissions and operational responsibility while the data stays unified.

1. **Cari** — community presence, social interaction and moderation.
2. **Sunna** — WaifuMon, encounters, collection, progression, combat and trivia.
3. **Cami** — media catalog, requests, publication, analytics and diagnostics.
4. **Chie** — onboarding, forum setup, welcome/verification, rules and coordination.

They should **not** communicate by sending messages to one another for every operation. Instead:

```text
                         SHARED CORE / DATA / SERVICES
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
          Telegram                  BRAIN                  Database
              │                       │                       │
       ┌──────┼────────┬──────────────┘                       │
       ▼      ▼        ▼                                      │
     Cari   Sunna    Cami                                    Chie
   social   game    media/requests                       setup/community
       └──────┴────────┴──────────────────────────────────────┘
```

The four bots are intentionally separate Telegram identities, but the local Core remains authoritative. This avoids unnecessary Telegram-to-Telegram traffic and keeps points, requests, media and configuration consistent.

## Shared points

Every successful waifu capture can award **community points** to the player. Points are attached to the player + community and have an auditable transaction ledger. Fan requests spend those same points.

Example flow:

```text
waifu capture
    ↓
Sunna
    ↓ +points
shared point ledger
    ↓
Chie → request intake
    ↓
request queue
    ↓
Cami → image fulfillment
```

The point ledger deliberately lives below the individual bot so a player does not have four independent wallets.

## Fan requests: persistent ticket number

Every paid fan request receives a database-generated **request number**, shown to humans as `Pedido #123`. The number is the visible ticket identifier; the internal `request_id` is the authoritative database reference.

A request keeps the user's Telegram ID, current username/name, community chat, description, optional character/details, points cost and status. The Telegram username is only display information and is **not** used as the primary identity because users can change it.

Example admin notification:

```text
😰 ¡Chie tiene un pedido nuevo!

🧾 Pedido #123
👤 Johan (@johan)
🏠 Comunidad
💰 Canje: 50 puntos
🎨 Personaje: asuna
📝 Pedido: Asuna con traje de conejita
```

When Cami receives the finished image, she associates it with `Pedido #123` and publishes it to `#pedidos` with the same number and a Telegram mention of the requester. This is intentionally similar to a restaurant ticket: the number connects the order, the requester and the delivered result without relying on a username.

## Telegram as a storage vault

A private Telegram group or channel can be configured as the bot's **media vault/inbox** with `MEDIA_STORAGE_CHAT_ID`. The intended workflow is:

```text
Telegram vault
   ↓
file_id + message_id + metadata
   ↓
local database catalog
   ↓
Cami
   ├─ game art
   ├─ community publication
   └─ fan-request fulfillment
```

Images do not need to be downloaded to the bot's disk just to reuse them. Telegram `file_id` values can be reused by the bot when sending the same media later. This avoids adding external object storage merely for the game library.

The vault should be a **dedicated private group/channel**, not the normal community group. The normal community chat remains the social history; our database stores structured information the system actually needs instead of duplicating every Telegram message unnecessarily.

## Media/requests behavior

Cami classifies each incoming asset/request into one of three paths:

```text
"esto es para el juego de waifus"
        → game library

"esto es para la página, publicalo en 3 horas"
        → scheduled publication

"esta imagen corresponde al Pedido #123"
        → request fulfillment
```

For fan requests, the bot recognizes that a player is spending earned points, preserves the requested character and optional details, and leaves incomplete/ambiguous requests pending for the admin rather than guessing.

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

Characters do not use generic attacks only. Each character gets attacks/defenses/specials based on recognizable anime traits, jokes or niche references.

## Data architecture

Telegram identity/activity is persisted independently from AI. Game profiles, collections, timed encounters, one-shot attempts, point transactions, rare-drop approvals, media assets, fan requests, durable events/jobs and art-stage mappings are durable database records so all four bots and the future web panel can consume the same authoritative state.

## API-saving strategy

- Commands, moderation rules, points and game rules are local code.
- User data and stats come from the database/services.
- Games use deterministic local rules.
- Cami should use AI only when classification/reasoning is actually useful.
- Cari's Brain decides whether a conversational message needs an LLM.
- Repeated/expensive AI work will be cached and batched.
- Providers stay behind an abstraction so Gemini, Groq, Cerebras or OpenRouter can be changed without rewriting the bots.

## Development order

1. Core + module lifecycle.
2. Data layer and member persistence.
3. Four bot domains and shared services.
4. Wild waifu encounters + collection safety + points.
5. Media vault + persistent `Pedido #N` request queue + authoritative image catalog.
6. Full character catalog, copies → EXP → levels → evolution → art stages and Pokémon-like battles.
7. Brain: intent, context, memory, decision policy and tool routing.
8. Private administration + publication pipeline.
9. AI providers, caching, fallback and usage monitoring.

## Run

Copy `.env.example` to `.env`, add the Telegram bot tokens and private media vault chat ID, install dependencies and run `python -m app.main`.
