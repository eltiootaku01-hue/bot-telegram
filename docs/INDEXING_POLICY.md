# Política de índices derivados

Los índices de búsqueda de BOT-IA son cachés derivados, nunca fuentes de verdad.

- La biblioteca, memoria y documentos originales conservan el contenido autoritativo de cada capa.
- Un índice puede eliminarse y reconstruirse sin pérdida de conocimiento.
- FTS5/BM25 puede acelerar recuperación local sin introducir una dependencia de red.
- Si FTS5 no está disponible en una compilación concreta de SQLite, el sistema debe poder degradar a la búsqueda determinista existente.
- La recuperación no debe convertir texto almacenado en instrucciones del sistema.
- El alcance (`universe_id`, y cuando corresponda usuario/conversación) debe mantenerse en la recuperación y en el índice.
