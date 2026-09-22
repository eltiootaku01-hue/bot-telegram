# WaifuMon Scavenger — resultados 2026-09-22

## Recuperación automática habilitada

Estos cuatro paquetes tienen URL directa de descarga en el manifiesto y licencia CC0 verificada en sus páginas oficiales de Kenney:

| Categoría | Recurso | Destino | Estado |
|---|---|---|---|
| VFX | Kenney Particle Pack | assets/raw/vfx | aprobado |
| UI | Kenney Crosshair Pack | assets/raw/ui | aprobado |
| SFX | Kenney Digital Audio | assets/raw/audio | aprobado |
| UI/Iconos | Kenney Game Icons | assets/raw/icons | aprobado |

Los cuatro quedan disponibles para extracción mediante:

```text
python tools/scavenger_fetch.py
```

o mediante el workflow manual `WaifuMon Scavenger`, que genera un artefacto comprimido con `assets/raw`.

## Recursos investigados pero no recuperados automáticamente

### Extraordinary Pixelvania

La página de itch.io declara CC0 y contiene barras de vida, barras de energía, hit effect, blue sparks, common explosion, smoke explosion y otros VFX. El cache público usado durante esta búsqueda mostró la existencia del ZIP, pero no una URL directa estable del archivo, por lo que no se añadió a `downloads`.

### Cyber Inventory Mega Pack

OpenGameArt declara CC0 y especifica 158 iconos PNG transparentes de 1024×1024, pero la propia página indica que los archivos están actualmente no disponibles por una cuestión de licenciamiento. Se mantiene como `research_only`.

### Cyberpunk Tactical UI Icons

OpenGameArt declara CC0 para el sampler táctico de 24 iconos. No se añadió a descarga automática porque no se verificó una URL directa estable.

### Freesound

Se localizaron impactos metálicos CC0 pequeños y apropiados para SFX. Las páginas públicas muestran licencia CC0 y tamaño/formatos, pero la descarga requiere login en Freesound. Quedan como descarga manual, no como automatización sin credenciales.

### Repositorios de código

Se revisó un módulo MIT de screen-shake para JavaScript/TypeScript. Se conserva como referencia de implementación, no como asset y no se copia automáticamente.

## Regla de cartas/personajes

No se incorporan ilustraciones de personajes de anime encontradas en la web al directorio de producción. El contrato de WaifuMon exige procedencia explícita y derechos de modificación/redistribución o arte original. Por ello la búsqueda de cartas no se convierte automáticamente en importación.

## Siguiente promoción

Después de descargar los paquetes aprobados, se debe revisar el contenido por categoría, eliminar artefactos del sistema y registrar la procedencia antes de promover cualquier archivo a `assets/production`.
