# WaifuMon Scavenger Protocol

## Objetivo

Recolectar recursos pequeños para HUD, VFX y SFX de WaifuMon con una separación estricta entre:

1. **downloads**: URL directa comprobable + licencia verificada.
2. **research_only**: recurso interesante, pero sin una URL directa estable verificada o con alguna otra razón para impedir la descarga automática.
3. **production**: solo assets que superaron el contrato de procedencia y validación.

## Ejecución

Desde la raíz del repositorio:

```text
python tools/scavenger_fetch.py --dry-run
python tools/scavenger_fetch.py
```

El descargador:

- usa timeout;
- descarga en archivo temporal;
- limita el tamaño máximo;
- valida el ZIP;
- bloquea rutas absolutas y `..`;
- bloquea symlinks dentro del ZIP;
- extrae solo dentro del directorio objetivo;
- elimina el ZIP temporal;
- falla el proceso si alguna entrada autorizada no puede recuperarse.

## Fuentes actualmente habilitadas

- Kenney Particle Pack → `assets/raw/vfx`
- Kenney Crosshair Pack → `assets/raw/ui`
- Kenney Digital Audio → `assets/raw/audio`
- Kenney Game Icons → `assets/raw/icons`

Los cuatro aparecen en el manifiesto con CC0 verificado.

## Investigación adicional

Durante la búsqueda también se detectaron:

- Extraordinary Pixelvania — CC0, con barras de vida, hit effects, sparks, explosiones y VFX.
- Cyber Inventory Mega Pack — CC0 declarado, pero OpenGameArt indica que los archivos están actualmente no disponibles por cuestiones de licencia.
- Cyberpunk Tactical UI Icons — CC0 declarado, pero sin URL directa estable verificada en esta búsqueda.
- SFX de impacto metálico en Freesound bajo CC0; el acceso público a la descarga requiere login.

Estos recursos quedan en `research_only` y no se descargan automáticamente.

## Regla para cartas/personajes

No se incorporan ilustraciones de personajes de anime a `assets/production/cards/` por el simple hecho de encontrar una descarga gratuita. El contrato de producción exige derechos explícitos de modificación y redistribución o arte original.
