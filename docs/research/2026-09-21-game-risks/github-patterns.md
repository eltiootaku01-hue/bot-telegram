# GitHub — patrones reutilizables

## wbcapon/discord-gacha

Referencia: https://github.com/wbcapon/discord-gacha

Patrones útiles:
- colección de cartas por rareza;
- moneda separada del inventario;
- compensación de duplicados;
- sets coleccionables;
- recompensas diarias.

Qué tomamos:
- separar identidad de carta, rareza, inventario y economía.

## Lexa307/DiscordCardBot

Referencia: https://github.com/Lexa307/DiscordCardBot/

Patrones útiles:
- drop diario;
- contador de cooldown;
- consulta del tiempo restante;
- inventario de duplicados;
- controles administrativos para resetear drops.

Qué tomamos:
- contador diario durable;
- respuestas explícitas de cooldown;
- pruebas de límites diarios.

## shootingstarsdiscord/starsbot

Referencia: https://github.com/shootingstarsdiscord/starsbot/

Patrones útiles:
- colección paginada;
- vista de duplicados;
- mercado/trade;
- identificadores estables de cartas.

Qué tomamos:
- IDs estables;
- inventario visible y navegable;
- separar carta de su cantidad.

## Regla de ingeniería

Estas referencias no se copian literalmente. Solo sirven para comparar decisiones y prevenir errores de diseño.
