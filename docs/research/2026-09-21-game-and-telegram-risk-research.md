# Investigación preventiva de juegos y Telegram — 2026-09-21

Objetivo: convertir quejas recurrentes de juegos y bots de Telegram en invariantes de diseño para este proyecto.

## Sunna — WaifuMon, gacha y colección

Hallazgo: comunidades de gacha reportan frustración por largas rachas sin recompensa útil, ausencia de pity, duplicados y compensación pobre. También aparecen sistemas de tickets, recompensas diarias, intercambios y otras válvulas de salida del duplicado.

Respuesta aplicada:
- protección suave de mala suerte: después de seis resultados D consecutivos, el siguiente D se convierte en C;
- estado de racha persistente en GameProfile;
- pity_triggered persistido en GameGachaRoll para auditoría y replay determinista;
- selección anti-duplicado para D/C cuando existe otro personaje del mismo máximo de rareza que el jugador aún no posee;
- referencias de gacha y recompensas siguen siendo idempotentes.

Fuentes públicas:
- Reddit r/gachagaming: https://www.reddit.com/r/gachagaming/
- Reddit r/heartopia: https://www.reddit.com/r/heartopia/
- Reddit r/ProjectSekai: https://www.reddit.com/r/ProjectSekai/
- Telegram Waifu Catcher: https://t.me/s/WaifuGacha

## Cami — misterio y deducción

Hallazgo: los juegos de deducción funcionan mejor cuando existe una solución demostrable, las pistas permiten una progresión lógica y el jugador no tiene que adivinar.

Respuesta aplicada:
- los misterios del proyecto son cotidianos y no violentos;
- cada caso debe contener opciones válidas, índice de respuesta válido y pistas explícitas;
- solo un jugador puede ganar la ronda mediante transición condicional;
- las recompensas usan una referencia idempotente.

Referencia pública comparativa:
- Reddit Developers — Griductive: https://developers.reddit.com/apps/griductive
- Reddit Developers — Deducto: https://developers.reddit.com/apps/deducto-puzzle
- Reddit Developers — CluesWord: https://developers.reddit.com/apps/cluesword

## Cari — trivia, Café y eventos

Riesgos preventivos:
- una ronda pública no debe quedar bloqueada por una ronda vencida;
- respuestas tardías deben ser rechazadas por el estado persistido y el vencimiento;
- las trivias son una actividad breve, no una obligación de grind;
- la telemetría del mundo nunca debe hacer fallar la recompensa o la respuesta.

## Chie — onboarding, permisos y moderación

Hallazgo: comunidades de Telegram reportan una tensión entre CAPTCHAs demasiado molestos y aprobación manual demasiado pesada. También se observan falsos positivos de moderación.

Respuesta aplicada:
- verificación explícitamente asociada a user_id;
- decisión de verificación de un solo uso;
- vencimiento persistido;
- restauración de permisos guardados;
- controles administrativos separados del runtime de los juegos;
- no se usa IA para aplicar automáticamente sanciones.

Fuentes públicas:
- Reddit / TelegramBots sobre CAPTCHA y aprobación manual: https://www.reddit.com/r/TelegramBots/
- GitHub ejemplo de CAPTCHA/flood-guard para Telegram: https://github.com/NikitaUshakov/telegram-antispam-bot

## Transporte Telegram

Hallazgo: aiogram expone TelegramRetryAfter y las aplicaciones deben decidir cómo manejar retry/rate limit. El Bot API entrega retry_after para indicar cuánto esperar ante flood control.

Respuesta aplicada:
- helper with_retry_after para tareas en segundo plano;
- solo reintenta TelegramRetryAfter;
- respeta exactamente retry_after;
- no reintenta errores de red ciegamente, porque una petición puede haber sido aceptada antes de fallar el transporte;
- publicaciones Cami vuelven a estado reintentable cuando el rate limit agota sus reintentos;
- el runtime social y los juegos periódicos también usan la misma política.

Fuentes:
- aiogram issue #1875: https://github.com/aiogram/aiogram/issues/1875
- aiogram migration/exception docs: https://docs.aiogram.dev/en/v3.31.0/migration_2_to_3.html
- Telegram Bot API: https://core.telegram.org/bots/api

## Límites de la investigación

Se revisaron fuentes públicas/indexadas de Reddit, GitHub y Telegram. No se presentan como consultadas comunidades privadas o cerradas de Discord/Telegram porque no están accesibles mediante búsqueda pública en este entorno.

## Regla resultante para el proyecto

Cada juego debe tener cuatro capas: estado persistente, transición atómica, respuesta corta y recuperación ante Telegram. La narrativa debe añadir sentido a la mecánica, no convertir cada personaje en un simple texto alrededor de una moneda.