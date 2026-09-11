# Perfil de recursos de BOT-IA

## Objetivo

BOT-IA debe funcionar bien en equipos modestos sin convertir memoria, búsqueda o mantenimiento en procesos residentes pesados.

Perfil de referencia actual:

- CPU: AMD Ryzen 5 5600G, 6 núcleos / 12 hilos.
- RAM: 16 GB.
- GPU: Radeon integrada, sin asumir VRAM dedicada utilizable.
- Almacenamiento: SSD + HDD.

## Política

1. El almacenamiento y la recuperación básicos son locales y deterministas.
2. SQLite/FTS5 es preferible a una base de datos externa para la primera capa de búsqueda.
3. Embeddings, reranking, grafos y modelos locales son opcionales y deben activarse bajo demanda.
4. No mantener un modelo local residente en segundo plano por defecto.
5. Las tareas de mantenimiento deben ejecutarse bajo demanda o de forma oportunista, nunca como daemon pesado obligatorio.
6. Los índices derivados deben poder reconstruirse desde las fuentes originales.
7. La ausencia de GPU dedicada no debe impedir el funcionamiento del núcleo.

## Evolución prevista

```text
SQLite + retrieval determinista
        ↓
FTS5/BM25 opcional y ligero
        ↓
semántica local bajo demanda
        ↓
reranking/grafo sólo si una necesidad real lo justifica
```

Este documento es una restricción de diseño, no una medición automática del hardware del usuario.
