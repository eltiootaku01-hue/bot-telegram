# Community Telegram Bot

Modular Telegram bot built around one rule: **local code first, AI second**.

## Three bot domains

1. **Chat + monitoring** — conversation, community presence and activity tracking. The Brain/LLM is optional and only used when language reasoning is useful.
2. **Pedidos + imágenes** — request queue, image metadata/storage and publication ordering. Full administration belongs to the private web panel.
3. **Juegos** — gacha, collection, progression and Pokémon-like deterministic battles. Interactive buttons live only inside game surfaces.

## Wild waifu loop

Groups can receive a random **waifu suelta** alert after a random delay. The current prototype intentionally caps wild encounters at class **B**:

- Class C: capture button immediately.
- Class B: niche anime question with one attempt per user.
- A wrong answer is shown privately to the clicker through the callback response.
- A successful capture ends the encounter for the group.
- After the random 1–10 minute lifetime, the buttons disappear and the message becomes `😭 La waifu se fue 😭`.

The encounter answer is stored server-side; callback data never contains the answer.

## Character combat identity

Characters do not use generic attacks only. Each character gets attacks/defenses/specials based on recognizable anime traits, jokes or niche references. Example: Taiga Aisaka has `Golpe de katana de madera`, `¿No sabría hacerse bolita?` and `Golpe de tigre`.

## Data architecture

Telegram identity/activity is persisted independently from AI. Game profiles, collections, timed encounters and one-shot attempts are durable database records so the web panel can later consume the same authoritative state.

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
5. Full character catalog, gacha progression and Pokémon-like battles.
6. Brain: intent, context, memory, decision policy and tool routing.
7. Requests/images/library + private web administration.
8. AI providers, caching, fallback and usage monitoring.

## Run

Copy `.env.example` to `.env`, add the Telegram bot token, install dependencies and run `python -m app.main`.
