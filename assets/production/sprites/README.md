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

La futura Mini App de combate debe:

1. usar las cartas HD solo en selección de equipo e interfaces de inspección;
2. usar exclusivamente sprites 128 × 128 durante la escena de batalla;
3. mostrar la carta HD como *cut-in* temporal durante **1.5 s** al activar una habilidad especial;
4. volver después al canvas 2D de sprites.

El frontend no calcula daño, multiplicadores, precisión ni vida restante. Esos datos llegan del contrato del engine Java.
