# Visual assets — WaifuMon

El arte final se produce **una carta/avatar por vez**. Una pieza no se marca como completa hasta que su archivo específico queda versionado en `assets/waifus/` y su estado se registra en `art_manifest.json`.

## Regla visual permanente

La biblioteca usa cuatro bandas de presentación visual independientes del balance de combate:

| Tier visual | Encuadre | Dirección |
|---|---|---|
| **R** | ~20% | rostro + una pequeña parte de hombros; expresión y diseño facial son la prioridad |
| **S** | ~40% | cabeza, hombros y torso superior hasta el pecho; pose acorde a personalidad/elemento |
| **SR** | ~60-80% | medio cuerpo amplio hasta cintura/muslos; pose dinámica, accesorios y fondo trabajado |
| **UR** | **100%+** | cuerpo completo; pose icónica, escenario completo, iluminación y acabado premium |

Estas bandas no cambian la rareza D/C/B/A/S/SS/SSS ni el balance R/SR/UR existente del motor. Son una especificación de presentación artística.

## Dirección de estilo

La referencia buscada es una ilustración anime de fantasía/aventura pulida, expresiva y dibujada a mano, con linework orgánico, cel shading controlado, buena profundidad, iluminación narrativa y siluetas claras.

No se copia literalmente el estilo de un autor o una obra concreta. Las referencias externas sirven únicamente para definir el nivel de energía, acabado y lenguaje visual.

## Diferencia entre avatares

Cada personaje debe conservar:

- paleta propia;
- expresión coherente con su identidad;
- pose distinta;
- vestuario/accesorios adecuados;
- composición y escenario diferentes cuando la rareza lo permita;
- un motivo visual reconocible.

La dirección se mantiene en `app/game/art_directions.py`. Cuando un personaje no tenga todavía una dirección individual, se usa explícitamente un fallback y no se declara como dirección terminada.

## Estado actual

La biblioteca de producción contiene **78 cartas jugables** en cola.

Las piezas completadas se registran individualmente en el manifiesto.

El manifiesto y `art_progress.json` contienen el estado unitario actual de cada avatar. Las piezas raster aptas para el runtime deben quedar en `assets/waifus/<character_id>.png`.

## Referencia visual

La imagen generada en `assets/waifus/generated/` es solamente una referencia de layout/progreso de la biblioteca. No se utiliza como arte de una personaje concreta.

## Runtime

El runtime nunca debe asociar una imagen genérica a una personaje. Una carta sin arte aprobado sigue siendo una carta válida con asset explícitamente ausente.
