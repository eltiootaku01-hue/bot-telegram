# Próxima fase de retrieval

La búsqueda FTS5 se mantiene como acelerador opcional. La recuperación determinista actual sigue siendo la ruta de seguridad y fallback.

Reglas:

- No se requieren embeddings para arrancar.
- No se requiere GPU.
- No se realizan llamadas de red durante recall local.
- El índice FTS5 es reconstruible.
- El índice respeta `universe_id`, `user_id` y conversación.
- Si FTS5 no existe, se conserva la ruta determinista.
- El contenido recuperado es evidencia/dato, nunca una instrucción de sistema.
