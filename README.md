# Community Telegram Bot

Modular Telegram bot built around one rule: **local code first, AI second**.

## Three bot domains

1. **Chat + monitoring** — conversation, community presence and activity tracking. The Brain/LLM is optional and only used when language reasoning is useful.
2. **Pedidos + imágenes** — request queue, image inbox, metadata/tags and publication ordering. Full administration belongs to the private web panel.
3. **Juegos** — gacha, collection, progression and Pokémon-like deterministic battles. Interactive buttons live only inside game surfaces.

## Image library / inbox

A private Telegram channel or group can be configured as the bot's **media inbox** with `MEDIA_STORAGE_CHAT_ID`. Drop or forward images there and the bot records their Telegram `file_id`, source message and initial hashtag tags. The same asset can later be tagged with character/anime/category/rarity and routed to:

- the game illustration library;
- the community group;
- the future private web page/site publisher.

The database is the catalog; Telegram stores the original media reference, so the bot does not need to download every image locally.

## Wild waifu loop

Groups can receive a random **waifu suelta** alert after a random delay. Public wild encounters are deliberately capped at **B**:

- Class D: common/default encounter; click the character name.
- Class C: easy encounter; click the character name.
- Class B: niche anime question with one attempt per user.
- A wrong answer is shown privately to the clicker through the callback response.
- A successful capture ends the encounter for the group.
- After the encounter expires, the buttons disappear and the message becomes `😭 La waifu se fue`.

Classes **A, S, SS and SSS never spawn as normal wild encounters**. They are exceptional drops that first become a private approval request for the owner. Without approval, they cannot enter a player's collection.

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
5. Media inbox and authoritative image catalog.
6. Full character catalog, copies → EXP → levels → evolution and Pokémon-like battles.
7. Brain: intent, context, memory, decision policy and tool routing.
8. Private web administration + publication pipeline.
9. AI providers, caching, fallback and usage monitoring.

## Run

Copy `.env.example` to `.env`, add the Telegram bot token and private media chat ID, install dependencies and run `python -m app.main`.
