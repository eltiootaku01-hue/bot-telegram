# Auditoría de hardware y ejecución local — 2026-09-10

## Equipo objetivo

- Windows 11 Pro 64-bit, build 22631
- Ryzen 5 5600G — 6C/12T
- 16 GB DDR4-3200 — 2 × 8 GB
- Radeon integrada con memoria gráfica reportada de ~0.5 GB
- SSD de ~466 GB, ~105 GB libres
- HDD de ~932 GB, ~435 GB libres

## Conclusiones

El equipo es adecuado para BOT-IA como aplicación local-first, almacenamiento, SQLite, retrieval determinista y tareas de escritura. También puede ejecutar modelos locales pequeños mediante CPU/RAM, pero no debe tratarse como una máquina con GPU dedicada para inferencia.

Ollama en Windows admite CPU y aceleración AMD en hardware compatible; la documentación actual indica que la memoria requerida aumenta con el contexto y las solicitudes paralelas. Por eso BOT-IA mantiene Ollama desactivado por defecto y, si se habilita, debe comenzar con un único proceso/solicitud y modelos pequeños.

## Almacenamiento

El SSD es la mejor ubicación para el código, bases SQLite activas y proyectos en uso por latencia. El HDD ofrece mucho más espacio para modelos, backups y archivos históricos, pero con tiempos de carga superiores.

No se deben mezclar los modelos descargados por Ollama con la biblioteca/canon de BOT-IA: son dependencias de ejecución, no conocimiento.

## Política de carga

No se recomienda convertir BOT-IA en un sistema que mantenga un LLM pesado residente. El modelo local debe cargarse sólo cuando una ruta autorizada lo necesite y liberarse después cuando sea posible.

## Seguridad funcional

Una limitación de CPU/RAM/GPU no cambia la política epistemológica de BOT-IA. Si el modelo local no puede resolver una tarea con evidencia suficiente, BOT-IA debe escalar o informar de su límite; nunca completar el hueco mediante invención.

## Hallazgo de infraestructura pendiente

La capa HTTP usa `urllib.request.HTTPError` para clasificar respuestas 4xx/5xx. `HTTPError` también es un objeto tipo archivo; conviene cerrarlo explícitamente antes de convertirlo en `ProviderError` para eliminar posibles `ResourceWarning` y dejar el transporte sin recursos pendientes.

Este punto queda separado de la política de hardware porque es una corrección de infraestructura del proveedor, no una limitación del equipo.
