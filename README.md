# Community Telegram Bot

Modular Telegram bot built around one rule: **local code first, AI second**.

## Flow

Telegram -> routers -> local handlers/services -> Brain -> LLM only when useful.

The architecture borrows proven patterns from mature bot ecosystems: modular cogs/plugins, routers, middleware, stateful flows, cooldowns, caches, schedulers, repositories and explicit service boundaries.

## API-saving strategy

- Commands such as `/ping` are handled locally.
- Stats and user data come from the database/services.
- Games use deterministic local rules.
- Moderation uses local rules, counters and permissions.
- Repeated data is cached.
- Scheduled work is handled by a scheduler.
- The Brain decides whether a conversational message actually needs an LLM.
- AI jobs such as tagging can be batched and cached.
- Providers stay behind an abstraction so Gemini, Groq, Cerebras or OpenRouter can be changed without rewriting the bot.

## Development order

1. Core + module system.
2. Data layer and repositories.
3. Middleware, permissions, cooldowns and stateful flows.
4. Brain: intent, context, memory, decision policy and tool routing.
5. Community, moderation, requests, images, library, games and scheduler.
6. AI providers, caching, fallback and usage monitoring.

## Run

Copy `.env.example` to `.env`, add the Telegram bot token, install dependencies and run `python -m app.main`.
