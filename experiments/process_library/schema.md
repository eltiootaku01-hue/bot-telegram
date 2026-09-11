# Contrato de metadatos

```text
ProcessDefinition
  id: stable string
  name: human-readable string
  category: controlled category
  objective: concise outcome
  conditions: deterministic preconditions
  inputs: required fields
  outputs: produced fields
  allowed_actions: explicit action identifiers
  priority: integer
  cost: local estimate
  requires_ai: boolean
```

## Relevancia

La recuperación debe ponderar intención, categoría, condiciones y prioridad. Los resultados históricos pueden mejorar el ordenamiento, pero nunca deben convertir una operación no permitida en una operación permitida.

## Evaluación IA

Cuando `requires_ai=true` o la intención sea ambigua, el router puede pasar un conjunto pequeño de candidatos al modelo. La salida del modelo debe ser una selección estructurada de candidatos existentes; no debe ser una lista libre de instrucciones ejecutables.

## Rendimiento

- Evitar consultar a Ollama para tareas puramente deterministas.
- Mantener el contexto del modelo pequeño.
- Medir latencia, errores y éxito por proceso.
- Favorecer Ollama local para tareas simples cuando AI esté habilitada.
- Escalar a una API configurada solo cuando exista una razón válida y una credencial disponible.
