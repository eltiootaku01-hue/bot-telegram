# Experimentos

Solo se conserva aquí una línea experimental: **local-first**.

## Regla de promoción

Toda funcionalidad que ya tenga contrato claro, pruebas y comportamiento seguro debe vivir en `app/`, ejecutarse desde `main` y validarse en CI. Esta carpeta no debe convertirse en una segunda aplicación.

## Experimento vigente

`experiments/local_first/` estudia la política de escalado de IA local con Ollama antes de proveedores externos.

Cuando una parte del experimento cumpla sus criterios, se promueve a producción y se elimina su prototipo de aquí.

## Prohibiciones

- No importar módulos experimentales desde `app/`.
- No dejar implementaciones duplicadas entre `experiments/` y `app/`.
- No contar prototipos como funciones terminadas.
