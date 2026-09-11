# Biblioteca experimental de procesos

Esta carpeta contiene la primera especificación reversible de la biblioteca de procesos del Manager.

## Principios

- Un proceso es una capacidad declarativa y comprobable; no es un prompt libre.
- El núcleo determinista decide qué acciones están permitidas antes de involucrar a la IA.
- Cada proceso tiene identificador estable, objetivo, condiciones, entradas, salidas, coste aproximado y si requiere IA.
- La recuperación debe devolver solo candidatos relevantes; nunca cargar toda la biblioteca en el contexto del modelo.
- La IA puede evaluar candidatos cuando el lenguaje o la ambigüedad lo requieren, pero no puede inventar una acción fuera del contrato del proceso.
- Los procesos peligrosos o con efectos externos requieren comprobaciones explícitas y no se habilitan por defecto.
- Esta implementación permanece experimental hasta tener pruebas unitarias, integración con el router y criterios de promoción.

## Esquema inicial

Cada proceso debe poder describirse con:

- `id`: identificador único y estable.
- `name`: nombre humano.
- `category`: telegram, moderation, chat, users, groups, media, database, scheduling, security, diagnostics, ai, fallback, performance o experiments.
- `objective`: resultado que busca.
- `conditions`: condiciones previas verificables.
- `inputs`: datos requeridos.
- `outputs`: datos producidos.
- `allowed_actions`: operaciones que puede ejecutar.
- `priority`: prioridad relativa.
- `cost`: estimación de coste/latencia.
- `requires_ai`: si necesita interpretación de lenguaje o decisión semántica.

## Flujo objetivo

`evento/mensaje -> recuperar candidatos -> filtrar condiciones -> evaluar 2-3 mejores -> ejecutar -> registrar resultado`

Para consultas más difíciles se podrá ampliar el embudo (`100 -> 10 -> 3 -> 1`) sin enviar los 100 procesos al modelo.

## Criterios de promoción

Un proceso pasa a producción solo después de:

1. pruebas deterministas;
2. prueba de entradas inválidas;
3. prueba de condiciones y permisos;
4. medición de latencia;
5. prueba de fallo y recuperación;
6. comprobación de que AI OFF no realiza llamadas al LLM;
7. revisión de que la IA no pueda ejecutar operaciones fuera de `allowed_actions`.

Las piezas aprobadas se promocionarán posteriormente a `app/`; esta carpeta no debe ser importada por el núcleo de producción mientras siga experimental.
