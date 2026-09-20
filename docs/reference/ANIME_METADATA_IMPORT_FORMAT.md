# Formato de importación del catálogo local de anime/manga

El importador local acepta un documento JSON UTF-8 con esta estructura:

```json
{
  "works": [
    {
      "id": "obra.local.001",
      "title": "Título principal",
      "titles": ["Título alternativo"],
      "type": "tv",
      "status": "verified",
      "year_start": 2020,
      "year_end": 2020,
      "episodes": 12,
      "genres": ["action"],
      "themes": ["adventure"],
      "studio": "Estudio",
      "source_ids": {
        "wikidata": "Q000000",
        "mal": "00000"
      },
      "source_urls": ["https://www.wikidata.org/"],
      "summary_short": "Resumen breve y original escrito para el catálogo local.",
      "notes": ["Nota de verificación"],
      "last_verified": "2026-09-19T12:00:00",
      "characters": [
        {
          "id": "obra.local.001:personaje",
          "name": "Personaje",
          "aliases": ["Alias"],
          "source_ids": {"wikidata": "Q000001"},
          "source_urls": ["https://www.wikidata.org/"],
          "notes": "Nota local",
          "last_verified": "2026-09-19T12:00:00"
        }
      ]
    }
  ]
}
```

## Contratos

- `id` y `title` son obligatorios.
- Los años son enteros o `null`; `year_end` no puede ser anterior a `year_start`.
- `episodes` es entero o `null` y no puede ser negativo.
- Listas (`titles`, `genres`, `themes`, `source_urls`, `notes`, `aliases`) contienen únicamente strings.
- `source_ids` es un objeto de strings.
- `summary_short` debe ser contenido original del proyecto, no un bloque copiado de una wiki.
- `status: verified` solo debe utilizarse cuando el operador ya haya comprobado el dato.
- El importador no realiza llamadas web y no cambia automáticamente un dato no verificado a verificado.
- Los registros se guardan dentro de la misma transacción de SQLite que controla el comando de importación.

## Importación

Desde la raíz del repositorio:

```text
python tools/import_anime_catalog.py ruta/al/catalogo.json
```

El proceso crea el esquema que falte, importa/actualiza obras y personajes y confirma todo al terminar correctamente. Ante un error de validación o de persistencia, la transacción del importador se revierte.

## Flujo recomendado

`fuente externa → revisión humana → JSON local → importador → SQLite → /anime`

La conversación normal de los bots no depende de internet para consultar estas fichas.