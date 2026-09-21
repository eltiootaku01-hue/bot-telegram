# WorldBot — auditoría y cierre de implementación — 2026-09-21

## Objetivo

Agregar un presentador neutral y opcional del Mundo de Juego como proceso Telegram independiente, sin convertirlo en una quinta identidad de personaje ni mover reglas del mundo al transporte.

## Auditoría previa

El repositorio ya tenía `PresenterKind.WORLD_BOT` y el `World Core` persistía eventos con `WorldPresenterRef`. Sin embargo, no existía un proceso `app.bots.world`, no había configuración `BOT_TOKEN_WORLD` y el empaquetado Windows no incluía un ejecutable neutral.

También se verificó que ningún módulo actual, fuera del propio sistema de recuperación, estaba creando `GameWorldEvent` mediante `WorldEventService`. Por eso no se inventó un productor de eventos nuevo solo para justificar WorldBot.

## Decisión arquitectónica

WorldBot es un adaptador de transporte.

```text
GAME WORLD
    ↓
GameWorldEvent
    ↓
WorldRuntime
    ↓
PresenterKind.WORLD_BOT
    ↓
WorldBot
    ↓
Telegram
```

`BotIdentity` continúa conteniendo solamente Cari, Sunna, Cami y Chie.

WorldBot no ejecuta reglas de juego, no decide recompensas, no administra puntos, no modifica canon y no usa personalidad de personaje.

## Implementación

- `app/bots/world.py`: runner autónomo y outbound-only.
- `WORLD_BOT_PRESENTER`: referencia tipada `world_bot:world`.
- `Settings`: `BOT_TOKEN_WORLD` y `BOT_LINK_WORLD` opcionales.
- `tests/test_world_bot.py`: contrato del presenter neutral y builder.
- `tests/test_world_runtime.py`: evento autorizado dirigido a `world_bot:world` se reclama y publica correctamente.
- `tools/build_launcher.bat`: genera `WorldBot.exe`.
- `installer/bot-telegram.iss`: incluye `WorldBot.exe`.
- `.github/workflows/windows-build.yml`: verifica el sexto ejecutable y mantiene la cadena de packaging.
- `docs/WORLDBOT.md`: responsabilidad, seguridad, ejecución y configuración.

## Seguridad

El runner valida que exista `BOT_TOKEN_WORLD`, autentica el token con `getMe`, y no crea un `Dispatcher` ni inicia polling. El World Runtime conserva el control de allowlist y fencing de eventos. Telegram se utiliza únicamente como transporte de publicación.

El proceso cierra `Bot`, base de datos y módulos incluso cuando la creación del esquema falla.

## Investigación aplicada

Se verificó en documentación oficial de Telegram y aiogram que `getMe` es apropiado para comprobar un token y que `sendMessage` es el mecanismo de publicación; además, los bots no pueden iniciar conversaciones privadas con usuarios.

Estas propiedades justifican el diseño outbound-only del WorldBot.

## Evidencia de código

- `8054818b60946e86effea6c6e3ba987910acca34` — runner WorldBot.
- `b2dd95520af9929152c05cac6a767ebe3513b0c7` — configuración y packaging.
- `7a8e242061bfab408a39df5ed0eadd37e78cacb1` — cierre de recursos ante fallo de schema.
- `03bc9e2aa1185b72e925c78f83d1ddae38d918d5` — regresión end-to-end del routing neutral.

## Validación funcional

SHA certificado: `03bc9e2aa1185b72e925c78f83d1ddae38d918d5`.

- CI #2001: SUCCESS.
- Ruff: SUCCESS.
- Pytest: **650 passed, 58 warnings**.
- Windows Build #1604: SUCCESS.
- Se verificaron los seis ejecutables, smoke test de BotManager, instalador, ZIP portable, checksums y subida de artefactos.

Artefactos de Windows Build #1604:

- `bot-telegram-windows-installer` — 120,782,520 bytes — SHA-256 `24eff24fd8f64aa09824a3c2b3acda26a250ab851e937fce7f92006e2b647270`.
- `bot-telegram-windows-portable` — 118,880,824 bytes — SHA-256 `b99d4d2d0c048d4d9b9e3ced5ef077b396125d9220a13bddd26f8b2eff2743e6`.

El build no publicó un Release porque el push fue sobre `main` y no sobre un tag `v*`; los artefactos de Actions sí fueron publicados.

## Estado

Bloque cerrado como funcional, validado y empaquetado.

## No repetir

No volver a crear otro runner de WorldBot ni duplicar WorldRuntime/WorldPresenter. El siguiente trabajo debe concentrarse en un productor auténtico de `GameWorldEvent` o en herramientas de selección de presentador, no en otro transporte paralelo.

## Siguiente auditoría

Localizar la primera fuente real de eventos del World Core que pueda elegir entre `existing_bot:<identity>` y `world_bot:world`, y comprobar que el cambio sea configurable, persistente, idempotente y cubierto por regresión.