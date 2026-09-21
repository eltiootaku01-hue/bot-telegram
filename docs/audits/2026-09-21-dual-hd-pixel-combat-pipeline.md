# REPORTE ATÓMICO — WAIFUMON DUAL HD / PIXEL ART COMBAT PIPELINE

Fecha: 2026-09-21

## 1. Especificación aplicada

Se formalizó en `docs/game-design/WAIFUMON_RULES.md` el esquema dual:

- Carta HD de colección/perfil: `assets/production/cards/<id>--normal.jpg`, JPEG 1024×1536.
- Sprite de batalla: `assets/production/sprites/<id>_idle.png`, `<id>_attack.png`, `<id>_hit.png`, PNG transparente 128×128.

La especificación detallada queda en `docs/game-design/WAIFUMON_COMBAT_VISUAL_PIPELINE.md`.

## 2. Estructura de assets

Se añadió `assets/production/sprites/README.md` con el contrato de producción.

Se añadió `assets/waifus/combat_visual_manifest.json`, que enlaza las 78 cartas del catálogo con los tres slots de sprite de combate. Los slots pueden quedar en estado `pending` hasta disponer de arte real; eso no marca sprites inexistentes como aprobados.

## 3. Contrato de presentación

Se añadió `app/game/combat_visuals.py` con:

- nombres canónicos de sprite;
- contrato 128×128;
- detección técnica de PNG;
- requisito de canal alpha;
- mapeo presentation-only de resultados del engine a intención de animación;
- duración del cut-in: 1500 ms.

Se añadieron regresiones en `tests/test_combat_visuals.py`.

## 4. Mini App

Flujo documentado:

1. Selección: cartas HD para formar equipo de 3 WaifuMons.
2. Batalla: canvas HTML5 2D usando exclusivamente sprites Pixel Art/Chibi.
3. Habilidad especial: cut-in temporal de la carta HD durante 1.5 segundos.
4. Retorno automático al canvas de sprites.

El frontend no calcula daño, precisión, multiplicadores, crítico ni HP restante.

## 5. Autoridad del engine Java

`engine/waifumon/src/main/java/com/eltiootaku01/waifumon/WaifuMonRuleEngine.java` permanece como autoridad exclusiva de cálculo.

`combat.resolve` devuelve, entre otros:

- `action`;
- `damage`;
- `critical`;
- `defender_hp`.

Los DTOs llegan al frontend para presentación. No se duplican las fórmulas en JavaScript/HTML.

## 6. Validación

CI incorporó `python tools/validate_combat_sprites.py`.

Windows Build incorporó la misma validación.

El validador acepta el estado pre-producción: declara los slots esperados y cuenta los PNG realmente presentes, pero falla si un sprite existente viola PNG, 128×128 o alpha.

## 7. Evidencia previa del empaquetado

Windows Build #1872 sobre `aaf8df4a6277d381da52aafb061b6a34a2e9b867` terminó `SUCCESS` y publicó:

- `bot-telegram-windows-installer`;
- `bot-telegram-windows-portable`.

## 8. Estado del bloque

Código/documentación: aplicado en GitHub.

Contrato de assets: aplicado en GitHub.

Validación CI: debe considerarse cerrada solamente cuando el run del SHA final termine en `SUCCESS`.

Validación Windows: debe considerarse cerrada solamente cuando el run del SHA final termine en `SUCCESS`.

No se declara ningún sprite de combate como asset producido o visualmente aprobado mientras el archivo real y sus verificaciones no existan.
