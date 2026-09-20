# Community Telegram Bot

Modular Telegram bot platform built around one rule: **local code first, AI second**.

## Four cooperating bot identities

The project runs as four separate Telegram bots that share one authoritative database/services layer:

1. **Cari** — community presence, social interaction and explicit administrator moderation.
2. **Sunna** — WaifuMon, encounters, collection, progression, combat and trivia.
3. **Cami** — media catalog, requests, publication, analytics and diagnostics.
4. **Chie** — onboarding, forum setup, welcome/verification, rules, world metrics and coordination.

The bots are intentionally separate Telegram identities, while the local Core remains authoritative for shared state, points, requests, media and configuration.

## Authentication and credential flow

The bot does not implement a user/password login system. Authentication is delegated to Telegram and to the configured LLM providers.

### Telegram bot authentication

Each identity gets its own Bot API token through `BOT_TOKEN_CARI`, `BOT_TOKEN_SUNNA`, `BOT_TOKEN_CAMI` or `BOT_TOKEN_CHIE`. The legacy `BOT_TOKEN` remains a fallback. `Settings.token_for()` selects the identity-specific token first, and `build_dispatcher()` passes it to aiogram's `Bot` client before polling starts.

```text
.env
  ↓ Pydantic Settings
Settings.token_for(identity)
  ↓
build_dispatcher()
  ↓
aiogram Bot(token=...)
  ↓
Telegram Bot API
  ↓
updates → Dispatcher → modules
```

The token is therefore a server-side credential: Telegram authenticates the bot process with it; Telegram users are not given the token and do not exchange a session token with this application.

### LLM authentication

The Brain layer supports Gemini, Groq, Cerebras and OpenRouter. API keys are loaded from environment-backed settings and never need to be committed to the repository. OpenAI-compatible providers receive the key in an `Authorization: Bearer ...` header. Gemini receives its key through the `x-goog-api-key` header rather than putting the secret in the request URL.

Provider selection is deterministic: the preferred configured provider is attempted first, followed by other configured providers as fallback. Custom model/base-URL settings apply only to the preferred provider, preventing a custom endpoint from accidentally changing another provider's request path.

```text
Telegram message
  ↓
BrainChatModule
  ↓
BrainClient.generate()
  ↓
preferred LLM → fallback LLMs
  ↓
provider HTTPS API
  ↓
text response
  ↓
Telegram reply
```

The Brain client truncates recent context and user input before sending it upstream, and provider HTTP errors are reduced to status/network information rather than retaining the response body in application errors.

### Secret storage

Secrets are saved locally in `.env`; runtime data and `.env` are ignored by Git. Do not paste real tokens or API keys into source files, tests, issues or commits. If a credential is exposed, revoke/rotate it at the provider immediately.

## Windows: installer and portable package

The project now has two distinct Windows distribution forms:

- **Installer (`BotTelegram-Setup-<version>.exe`)** — the recommended download for a normal Windows installation. It installs `BotManager.exe` plus the four bot executables, creates Start Menu/Desktop shortcuts, creates writable `data` and `logs` directories, and can launch Bot Manager after installation.
- **Portable ZIP (`bot-telegram-windows-portable.zip`)** — the raw executable bundle for users who prefer to extract and run it without an installer.

The GitHub Actions Windows workflow builds the five executables, verifies every expected file, builds the Inno Setup installer, verifies that the installer exists and is non-trivially sized, and uploads both distribution forms as Actions artifacts. The workflow runs on `main`, can be started manually, and runs for `v*` tags. For a `v*` tag it also creates a GitHub Release containing the installer and portable ZIP, making the installer directly downloadable from the release page.

### First launch after installation

1. Open **Bot Manager**.
2. Enter the Telegram link/username and token for **Cari, Sunna, Cami and Chie**.
3. Add Chie to the target group as an administrator. Even when the group is not yet in `AUTHORIZED_CHAT_IDS`, Chie accepts only the exact `/configurar` bootstrap command from a real group administrator; that one onboarding update does not enter normal member activity. After configuration, keep the group ID in `AUTHORIZED_CHAT_IDS` so normal bot traffic is fail-closed.
4. AI is **optional**. You can leave all AI controls disabled and run the deterministic bot features without an LLM.
5. If AI is enabled, choose Ollama for the local-first path or configure one or more external providers (Gemini, Groq, Cerebras or OpenRouter). Cloud credentials are only needed for the providers you actually enable/configure.
6. Optionally choose the preferred provider and model, then add the admin Telegram ID and media-vault chat ID.
7. Press **Guardar configuración** and then **Comenzar**.
8. BotManager starts the four bot processes and gives each one its own start/stop control.

Dentro de la comunidad, Chie expone `/reglas` para las normas operativas. En privado, `/mundo` consulta las señales agregadas de Ciudad Animals y `/salud` muestra un diagnóstico de solo lectura de comunidades, jobs, eventos, misterios, catálogo y estados de las identidades.
El operador humano de Tío Otaku dispone de `/tio_pendientes` para revisar solicitudes y `/tio_responder ID mensaje` para enviar manualmente una respuesta al grupo. El sistema no genera esa respuesta por IA. Solo se capturan vocativos explícitos de Tío y se ignoran mensajes escritos por otros bots.
En privado, `/borrar_mi_memoria` permite eliminar tus estadísticas de uso identificables de Ciudad Animals; los agregados globales anónimos no se modifican.

Secrets are saved only in the local `.env` file. `.env` and runtime data are ignored by Git.

### Build locally

From Windows with Python 3.12 installed:

```bat
tools\\build_launcher.bat
```

The executable build creates:

```text
dist\\BotManager.exe
dist\\bots\\Cari.exe
dist\\bots\\Sunna.exe
dist\\bots\\Cami.exe
dist\\bots\\Chie.exe
```

The installer definition lives at `installer/bot-telegram.iss` and packages those executables into a normal Windows setup program. GitHub Actions installs Inno Setup, compiles the installer, verifies it, and publishes the resulting artifact/release asset.

## Deterministic character conversations

The four identities share a small local conversation module in addition to their specialized roles. Cari can answer common community greetings directly; Sunna, Cami and Chie require an explicit name/address so one group message does not produce four simultaneous character replies. These replies come only from authored repertoire and never require the AI Brain.

Examples:

```text
Sunna
→ ¿Sí? / Te escucho.

Cami, una pregunta
→ ¿Sí? Decime qué necesitás.

Chie, necesito ayuda
→ Te escucho... p-podemos verlo juntas.
```

## Cari: moderation tools

Cari incluye moderación explícita y determinista. Un administrador del grupo puede responder al mensaje de un integrante con `/advertir`, `/silenciar`, `/desilenciar` o `/expulsar`; no existe clasificación automática por IA en esta ruta. Las acciones sensibles vuelven a comprobar los roles de Telegram y no permiten actuar sobre administradores, el propio moderador ni cuentas de bots. Las acciones se registran en SQLite para auditoría.

## WaifuMon gacha

Sunna's private Gacha is a real persistent game action, not a cosmetic rarity roll. Each tirada costs **10 community points** and is recorded with an idempotent roll ID, so repeating the same Telegram callback cannot grant a second character.

Available characters are selected from the local catalog up to the rolled rarity. Public D/C results are added directly to the player's collection and grant collection XP. A B/A/S/SS/SSS result creates a private owner approval request; the character is not added until the owner approves it. A rejected exceptional drop refunds the 10 points exactly once.

The gacha state, approval state and reward transaction are stored in SQLite, so the workflow survives process restarts.

## Misterio diario del Café Otaku

Sunna incorpora un misterio authored que puede iniciarse en la comunidad con `/misterio`. Cada comunidad tiene como máximo una ronda por día del mundo. El caso se elige de forma determinista según la comunidad y la fecha, incluye cuatro pistas y cuatro opciones, y el primer jugador que acierta obtiene **15 puntos**.

La ronda y los intentos quedan persistidos en SQLite. Cada jugador puede responder una sola vez, el ganador se reclama con una transición atómica y la recompensa usa una referencia idempotente en el ledger de puntos. Si Telegram rechaza la publicación inicial, la ronda queda marcada para poder reintentarse en lugar de bloquear el día.

## Café Otaku

Cari incluye una superficie determinista del Café Otaku:

- `/cafe` o `/menu` muestra los servicios disponibles en Ciudad Animals.
- `/recomendacion` entrega una recomendación diaria estable para esa comunidad/chat.
- La recomendación y el menú usan texto authored-only; no requieren un modelo de IA.
- Las métricas del mundo registran el uso agregado de estas acciones sin guardar el texto completo del usuario.

El catálogo público de Cami se consulta con `/catalogo` y solamente muestra material que ya fue publicado.
El archivo local de anime/manga de Cami se consulta con `/anime`. Solo devuelve fichas almacenadas en SQLite; una ficha marcada como `unverified` no debe tratarse como un dato factual confirmado. El etiquetado de material crea automáticamente una ficha local de la obra con esa marca para facilitar una futura verificación y conserva separadas las fuentes, identificadores, resumen original y notas.

## Shared points

Every successful waifu capture can award community points. Points belong to the player + community and use an auditable transaction ledger. Fan requests and Gacha spend those same points.

## Fan requests: persistent ticket number

Every paid fan request receives a database-generated request number shown to humans as `Pedido #123`. The internal `request_id` remains the authoritative reference.

## Telegram as a storage vault

A private Telegram group or channel can be configured as the media vault/inbox with `MEDIA_STORAGE_CHAT_ID`. Telegram `file_id` values are reused so images do not need unnecessary local copies.

## Wild waifu loop

Public wild encounters are capped at class C. Higher-rarity candidates are routed through the private approval path instead of appearing as normal public encounters.

## Ciudad Animals: small living world

The bots remain independent characters, but the project now has a lightweight **world observation ledger** for the future "Ciudad Animals" layer. The ledger records aggregate usage such as topics, actions and scenes per bot and, when useful, per user. It is intentionally not an LLM memory and does not need to retain raw chat text.

The catalog lets us define things that exist in the world even before anyone uses them. A later review can therefore compare:

```text
most used → what the community is actually enjoying
least used → what exists but is rarely touched
unseen    → what is defined but has never appeared
user      → repeated habits of a particular participant
```

The implementation is designed for a future **AI curator** that runs periodically (for example, a small daily review or a deeper weekly review). That AI would analyze the aggregate report and suggest new scenes, dialogue, topics or world changes. It does **not** replace the four characters' deterministic runtime and does **not** automatically rewrite their personalities in this first stage.

See `docs/CIUDAD_ANIMALS_WORLD.md` for the design and current status.

## API-saving strategy

- Commands, moderation rules, points and game rules remain local.
- User data and stats come from the database/services.
- Games use deterministic local rules.
- AI is an escalation path rather than the default handler.
- Ollama can provide a local-only LLM path when enabled.
- Provider settings are configurable so Gemini, Groq, Cerebras or OpenRouter can be wired behind the Brain layer when credentials are available.
- No cloud model is bundled into the Windows executable.

## Architecture

```text
Telegram
   ↓
Core
   ↓
Events / Modules / Services
   ↓
Ciudad Animals observation layer
   ↓
Brain policy
   ↓
Optional local/cloud LLM provider
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