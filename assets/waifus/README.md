# Visual assets — WaifuMon

Los assets visuales del juego están separados entre **producción** y **cuarentena**.

## Contrato de producción

El único directorio que puede contener arte usado por el runtime es:

`assets/production/cards/`

Todo asset de producción debe ser:

- JPEG/JPG;
- exactamente **1024 × 1536** píxeles;
- legible como JPEG válido;
- entre 50 KiB y 8 MiB;
- validado por `tools/validate_card_assets.py`;
- versionado en Git LFS cuando corresponda.

La convención de nombres usa `<character-id>--normal.jpg`, `<character-id>--shiny.jpg`, `<character-id>--class-<rarity>.jpg` o `<character-id>--stage<1|2|3>.jpg`.

## Cuarentena

`assets/quarantine/` contiene assets heredados, conceptos, SVG y cualquier pieza que no haya sido validada contra el contrato de producción.

Nada de esa carpeta puede ser cargado por el runtime.

## Estado de la biblioteca

El saneamiento P0 dejó la producción sin raster aprobados hasta completar una validación individual de cada pieza. El manifiesto conserva el historial editorial, pero no considera terminada una pieza solamente porque exista un archivo heredado.

## Regla de fail-closed

Si una carta no tiene JPEG de producción validado, el runtime no busca formatos alternativos ni usa un asset genérico. La carta sigue registrada y el asset queda explícitamente ausente.
