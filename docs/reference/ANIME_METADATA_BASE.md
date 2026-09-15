# Base de metadatos de anime y manga

Fecha de referencia: 2026-09-15

Esta base está pensada para el conocimiento local de Ciudad Animals. Los resúmenes narrativos deben redactarse de forma original y breve; no se copian párrafos de Wikipedia, wikis de fans u otras fuentes. Los datos estructurados pueden apoyarse en fuentes abiertas y APIs públicas, dejando registrada la procedencia.

## Propósito

Permitir que los bots puedan responder sobre anime/manga con información delimitada sin recurrir continuamente a una IA ni navegar la web durante una conversación.

## Esquema por obra

| Campo | Uso |
| --- | --- |
| `id` | identificador estable local |
| `title` | título principal |
| `titles` | títulos alternativos relevantes |
| `type` | TV, película, OVA, ONA, especial, manga, etc. |
| `status` | emisión/publicación terminada, en curso u otro estado localmente verificado |
| `year_start` | año de inicio |
| `year_end` | año final cuando corresponda |
| `episodes` | cantidad conocida de episodios, si aplica |
| `genres` | géneros normalizados |
| `themes` | temas o etiquetas útiles |
| `studio` | estudio principal cuando esté identificado |
| `source_ids` | identificadores externos, por ejemplo Wikidata o MAL |
| `source_urls` | enlaces de referencia |
| `summary_short` | resumen original de pocas líneas |
| `notes` | notas internas, advertencias o límites |
| `last_verified` | fecha de última verificación |

## Qué información conviene guardar

### Identidad de la obra

Título, títulos alternativos, tipo de producción, fechas y estado.

### Ficha básica

Géneros, temas, estudio, duración o cantidad de episodios cuando el dato sea fiable.

### Personajes

Solo personajes que queramos usar en la conversación local. Cada entrada debe identificar la obra de origen y evitar mezclar versiones o adaptaciones sin indicarlo.

### Resumen

Una descripción breve y original centrada en la premisa. No se almacena texto copiado de una wiki como si fuera contenido propio del proyecto.

### Procedencia

La procedencia es parte del dato. Wikidata ofrece datos estructurados reutilizables bajo CC0; puede servir para identificadores y relaciones entre entidades. citeturn164196search15turn164196search16

Jikan es una API comunitaria no oficial que obtiene datos públicos de MyAnimeList; su documentación muestra endpoints para obra principal, búsqueda, personajes/equipo, episodios, estadísticas y otros recursos. Debe tratarse como fuente auxiliar y sus datos deben cachearse si se usa durante una fase de importación. citeturn164196search1turn164196search2turn164196search7turn164196search8turn164196search11

## Regla de importación

La importación externa no debe convertirse en dependencia de ejecución.

Flujo recomendado:

`fuente externa → importador → validación → archivo local → revisión → uso por los bots`

Así, una vez incorporados los metadatos, Cari/Cami/Sunna/Chie pueden consultarlos localmente.

## Ejemplo de ficha local

```yaml
id: anime.ejemplo.001
title: Ejemplo Anime
titles: []
type: tv
status: finished
year_start: 2020
year_end: 2020
episodes: 12
genres:
  - action
themes:
  - adventure
studio: Example Studio
source_ids:
  wikidata: Q000000
  mal: 00000
source_urls:
  - https://www.wikidata.org/
summary_short: >-
  Resumen original y breve escrito para la base local.
notes: []
last_verified: 2026-09-15
```

## Política de calidad

- No presentar como canon un dato que solo aparezca en una fuente secundaria dudosa.
- No copiar sin licencia párrafos extensos de wikis.
- Separar hechos estructurados, resumen original y notas del proyecto.
- Conservar la fecha de verificación.
- Cuando existan varias adaptaciones, indicar cuál está documentada.
- Si un dato es desconocido, dejarlo vacío o marcado como no verificado en lugar de inventarlo.

## Integración futura con el Café Otaku

Cami puede encargarse del archivo y procedencia; Cari puede usar la ficha para conversaciones y recomendaciones; Sunna puede usar etiquetas para juegos y colecciones; Chie puede consultar la ficha para organizar actividades del café. Tío Otaku puede consultar la misma base desde la interfaz de operador y luego responder manualmente con la información que él mismo haya verificado.
