# WaifuMon — reglas de producción artística

Fecha: 2026-09-21

## Unidad

Una carta/avatar por vez. Una pieza no se considera terminada hasta que su archivo específico quede versionado y su estado actualizado en el manifiesto.

## Encuadre

- R: ~20% — rostro y una pequeña parte de hombros.
- S: ~40% — cabeza, hombros y torso hasta el pecho.
- SR: ~60–80% — medio cuerpo amplio.
- UR: 100%+ — cuerpo completo y composición abierta.

## Diferenciación

Cada avatar debe tener dirección propia: paleta, expresión, pose, escenario y motivo reconocible. Las cartas consecutivas no deben compartir una composición genérica.

## Estilo

Lenguaje visual general: anime de fantasía/aventura original, acabado pulido, linework orgánico, cel shading controlado, iluminación narrativa y buena profundidad.

Las referencias de obras externas solo sirven para nivel de energía y acabado; no se replica literalmente la firma visual de una obra o artista.

## Variantes

Una variante alternativa se registra como avatar separado con `character_id` propio. La convención `<id>-shiny` es válida para una variante OC diferenciada.

## Estados

- `pending`
- `direction_ready`
- `approved`
- `blocked_editorial`
- `superseded`

## Flujo

Dirección → pieza individual → revisión del tier → versionado → manifiesto → tests → siguiente avatar.
