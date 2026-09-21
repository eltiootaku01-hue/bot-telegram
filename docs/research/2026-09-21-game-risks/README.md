# Investigación preventiva de sistemas de juego

Esta carpeta guarda referencias públicas usadas para diseñar y revisar Sunna/WaifuMon. Se toman patrones e incidencias como inspiración de ingeniería; no se copia código de terceros.

## Reglas convertidas en invariantes del proyecto

- Gacha: mostrar coste y resultado con trazabilidad, persistir cada tirada, tener protección contra mala suerte y una salida razonable para duplicados.
- Capturas: un click no debe poder generar tres recompensas; el límite se impone en la base de datos, no solo en la interfaz.
- Cooldowns: el estado diario se persiste por usuario + comunidad + fecha en zona horaria del mundo.
- Recompensas: cada acción acreditable debe tener una referencia idempotente.
- Telegram: responder callback queries rápidamente y tratar `retry_after` como una señal de rate limit.
- Juegos públicos: separar la carrera por el recurso lógico de la edición del mensaje de Telegram.
- Reinicios: todos los contadores y rondas importantes deben sobrevivir a un proceso reiniciado.

## Fuentes principales

- Reddit r/gachagaming / r/heartopia / r/Mudae: experiencias públicas sobre pity, duplicados, cooldowns y conflictos de reclamación.
- GitHub wbcapon/discord-gacha: colección de cartas, duplicados y recompensas.
- GitHub Lexa307/DiscordCardBot: drops diarios, cooldown consultable y duplicados.
- GitHub shootingstarsdiscord/starsbot: colección, duplicados y mercado.
- aiogram GitHub discussions/issues: problemas prácticos de rate limiting y cambios de API.
- Telegram Bot API: callback queries, `retry_after` y juegos.

Última revisión: 2026-09-21.
