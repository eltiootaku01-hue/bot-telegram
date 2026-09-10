# BOT-IA Desktop

BOT-IA now has a graphical Windows interface that uses the same application runtime as the console, Telegram and HTTP API.

## What it provides

- Chat-style conversation window.
- Buttons similar to the Telegram main menu.
- Active novel indicator.
- Library, continuity, ideas, investigation, scene-helper, API status and progress actions.
- Progress bars for documented library state, connected universes and enabled providers.
- `Autorizar API sólo para esta consulta`, disabled by default.
- `Iniciar en Telegram`, which starts Telegram in a separate process so the desktop window remains usable.

## Important safety behavior

The GUI does not create a second brain or a second knowledge base. It calls `BotApplication`, so the same evidence, routing, memory and provider rules remain in force.

The API authorization checkbox is deliberately per-request. Leaving it unchecked keeps the request local according to the normal routing rules. If external API research is authorized, its result remains an external proposal and is not silently promoted to project canon.

The percentages shown in the dashboard are **local documentation/configuration indicators**, not provider quota balances and not a percentage of story quality. BOT-IA does not invent a provider's real remaining quota.

## Windows executable

The source entrypoint is `desktop.py`. The PowerShell packaging script is `build_desktop.ps1` and creates `release\\bot.exe`.

GitHub Actions can also build the Windows package with `.github/workflows/build-windows.yml`; the resulting `BOT-IA-Windows` artifact contains the executable plus runtime configuration files.

Keep the real `.env` outside Git. The release directory should contain your local `.env` only on your own machine.
