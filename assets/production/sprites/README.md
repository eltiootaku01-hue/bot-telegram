# WaifuMon — sprites de combate

Este directorio contiene exclusivamente los assets ligeros de batalla.

## Contrato

Cada WaifuMon que participe en combate puede tener hasta tres PNG transparentes:

- `<id>_idle.png` — pose estática de combate.
- `<id>_attack.png` — frame o pose de ataque.
- `<id>_hit.png` — reacción de daño.

Dimensiones obligatorias:

- **128 × 128 px**
- **PNG**
- **fondo transparente**

Los sprites son material de presentación. No contienen ni sustituyen reglas de gameplay.

La ilustración HD de perfil/colección permanece separada en:

`assets/production/cards/<id>--normal.jpg`

con contrato **JPEG 1024 × 1536**.

La Mini App de combate usa además un sistema de efectos Canvas generado por código en
`webapp/js/effects.js`. No necesita sprites de partículas externos y mantiene un
límite duro de 96 partículas.

El frontend no calcula daño, multiplicadores, precisión ni vida restante. Esos datos
llegan del contrato del engine Java/Python backend.

## Provenance

Un sprite externo solo puede entrar aquí cuando su licencia permite modificarlo y
redistribuir el resultado. Un asset que permita uso comercial pero prohíba
redistribución permanece fuera de producción.

Para PNGs heredados con fondo magenta, el proyecto incluye:

`tools/prepare_magenta_png.py`

Instala el extra de herramientas antes de usarlo:

```text
python -m pip install -e ".[assets]"
python tools/prepare_magenta_png.py INPUT.png OUTPUT.png
```

El procesador solo convierte `#FF00FF` a transparencia; no modifica la licencia del
archivo de entrada.

Para aplicar además el tratamiento visual bōsōzoku (tinte violeta, contraste y saturación)
usa `tools/process_bosozoku_sprite.py`. Requiere declarar `original` o `licensed` y,
para material licenciado, exige URL y licencia. El tratamiento no elimina firmas, marcas
de agua ni restricciones de redistribución.
