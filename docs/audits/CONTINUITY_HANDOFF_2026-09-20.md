# Handoff de continuidad — 2026-09-20

Este archivo complementa CONTINUITY_WORKLOG.md y registra el último bloque para no repetirlo.

## Bloque: matriz authored de amistades

- Se añadieron 12 escenas a app/characters/repertoire.py.
- Cada una de las 12 parejas dirigidas entre Cari, Cami, Sunna y Chie tiene ahora al menos dos variantes authored seleccionables.
- El contenido solo usa rasgos ya presentes en los perfiles/canon: apoyo, pertenencia, calma, agradecimiento, coordinación y confianza.
- No se añadieron hechos narrativos nuevos.
- CharacterDirector sigue siendo el selector determinista y no se introdujo generación LLM.
- Se añadió una regresión que exige cobertura de las 12 parejas y al menos dos variantes por pareja.
- Commit de código/test: 32c09a43819c9d8c0c7785d772e732d931582306.

## No repetir

No rehacer el sistema de relaciones, la continuidad por user_chat ni WorldService.usage_count(). Para más variedad, ampliar el repertorio existente y sus pruebas.

## Validación pendiente

Consultar CI y Windows asociados al SHA más reciente antes de marcar este bloque como validado.

## Referencia permanente

El estado global vigente sigue siendo 82%. La deuda principal continúa siendo profundidad de producto y contenido autoral confirmado, no el esqueleto técnico.
