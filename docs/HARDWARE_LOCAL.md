# Perfil de hardware local de BOT-IA

Perfil de referencia para el equipo objetivo actual de BOT-IA:

- Windows 11 Pro 64-bit
- AMD Ryzen 5 5600G, 6 núcleos / 12 hilos
- 16 GB DDR4-3200 (2 × 8 GB)
- Radeon integrada del 5600G, con VRAM reportada muy limitada y memoria compartida
- SSD de ~465 GB y HDD de ~1 TB

## Política de recursos

BOT-IA debe seguir siendo **local-first y ligero** en este equipo.

1. No mantener un modelo local grande residente por defecto.
2. Ollama debe permanecer desactivado hasta que el usuario lo habilite explícitamente.
3. Si se habilita Ollama, empezar con modelos pequeños (aprox. 1B–4B cuantizados) y una sola solicitud paralela.
4. Evitar modelos 7B/8B o superiores como requisito base: pueden funcionar en CPU/RAM, pero aumentan la presión de memoria y reducen la respuesta interactiva.
5. No asumir que la Radeon integrada aporta VRAM dedicada suficiente para inferencia. La memoria gráfica es compartida con la RAM del sistema.
6. No introducir Docker, Redis, una vector DB o un proceso residente adicional sólo para habilitar una función que BOT-IA pueda realizar de forma local y bajo demanda.
7. Las tareas pesadas (reindexación, backup, recuperación o investigación externa) deben ejecutarse bajo demanda y no como procesos permanentes.

## Ollama

La configuración de Ollama del proyecto queda preparada pero desactivada por defecto. Si se habilita, el perfil inicial debe favorecer bajo consumo:

- `keep_alive = 0` para no mantener el modelo cargado después de una petición.
- una sola petición paralela;
- contexto moderado;
- límite de salida pequeño para tareas auxiliares;
- fallback externo sólo cuando el usuario lo autorice explícitamente.

Ollama documenta que la memoria requerida crece con el número de solicitudes paralelas y el tamaño de contexto. En este equipo no conviene elevar esos valores sin una medición concreta.

## Principio de seguridad

La limitación de hardware nunca debe convertirse en una razón para inventar una respuesta. Si el modelo local no puede completar una tarea con seguridad:

> No tengo evidencia suficiente en la biblioteca para responder con seguridad.

BOT-IA debe escalar o pedir autorización según sus reglas de ruta, no rellenar el hueco con una conjetura.

## Espacio de disco

Los modelos locales pueden ocupar varios GB o más. Si se habilita Ollama, conviene colocar `OLLAMA_MODELS` en una unidad con espacio suficiente y mantener la biblioteca/canon de BOT-IA separada de la caché de modelos.

La biblioteca y los proyectos siguen siendo datos de BOT-IA; los modelos son una dependencia de ejecución y no forman parte del conocimiento/canon.
