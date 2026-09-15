# Auditoría viva del proyecto

Fecha de referencia: 2026-09-15

Este documento separa el estado técnico comprobable del avance hacia la visión completa de Ciudad Animals. Los porcentajes son estimaciones de alcance, no métricas automáticas de cobertura.

## Estado de la plataforma

| Área | Estado |
| --- | ---: |
| Arquitectura Core | 86% |
| Cuatro identidades independientes | 92% |
| Persistencia / SQLite / transacciones | 88% |
| Módulos y composición | 88% |
| Eventos, jobs, turnos y presencia | 84% |
| WaifuMon / progresión | 82% |
| Trivia | 80% |
| Media / archivo / publicaciones | 80% |
| Solicitudes / puntos | 82% |
| BotManager / empaquetado Windows | 90% |

## Estado de personajes y mundo

| Área | Estado |
| --- | ---: |
| Perfiles de Cari, Sunna, Cami y Chie | 60% |
| Director determinista | 60% |
| Repertorio escrito | 47% |
| Router determinista de intenciones | 50% |
| Rutinas y horarios | 52% |
| Interacciones entre personajes | 27% |
| Café Otaku | 20% |
| Ciudad Animals | 32% |
| Estadísticas del mundo | 38% |
| Registro automático de uso de escenas | 42% |
| IA como curadora periódica | 20% |
| Juegos nuevos (misterios, cartas, etc.) | 10% |
| GUI completa de edición | 20% |

## Riesgos activos detectados por auditoría

1. La personalidad está definida pero no toda está conectada al runtime de conversación.
2. El repertorio sigue creciendo, pero todavía está lejos del volumen necesario para que los cuatro personajes tengan una vida de NPC amplia y sostenible.
3. La conversación debe seguir siendo determinista y explícitamente activada. El router usa coincidencias de palabras/frases completas y contempla variantes habituales con acentos.
4. El runtime social ya usa el director, el repertorio y las rutinas horarias, pero todavía necesita más categorías y escenas específicas para que las intervenciones espontáneas tengan mayor variedad.
5. Ciudad Animals ya puede registrar escenas usadas, intención y ámbitos de usuario/chat. La atribución de escenas de seguimiento ahora se hace sobre el personaje que realmente habla, y existe una prueba específica que protege esa regla.
6. Las rutinas horarias ahora usan `Settings.bot_world_timezone` y convierten UTC a una zona IANA explícita (`America/Argentina/Buenos_Aires` por defecto). Esto evita depender de la hora UTC para el comportamiento del mundo.
7. La distribución Windows necesita conservar datos IANA disponibles de forma reproducible: Python documenta que algunos sistemas, especialmente Windows, pueden no traer una base IANA y recomienda `tzdata` como fuente de datos de primera parte. El proyecto ahora declara `tzdata` explícitamente.
8. Café Otaku y las rutinas del mundo siguen siendo funcionalidad parcial: las franjas horarias ya están modeladas y consumidas por el runtime social, pero todavía faltan objetos, servicios, economía y eventos conectados a esas rutinas.
9. Se requieren auditorías posteriores para verificar que nuevos juegos o sistemas no desplacen el objetivo principal: personajes y mundo vivos sin dependencia continua de IA.
10. Las pruebas deben seguir protegiendo la voz específica de Sunna, Cami y Chie frente a expansiones futuras del repertorio.
11. El último fallo de CI conocido fue un error de aserción en `test_chat_world_attribution.py`; el test fue corregido en `cad996c85a184042027f6cdb43db606c561f4e28`. No se marca CI verde hasta observar una ejecución posterior que pase realmente.

## Evidencia externa utilizada

### Telegram / aiogram

La documentación actual de aiogram mantiene el enfoque de `Router`, middlewares, filtros y dependencia de contexto, que encaja con la composición modular existente del proyecto. La propia documentación describe la inyección de dependencias como mecanismo para desacoplar creación y uso de servicios. La API oficial de Telegram expone actualizaciones específicas como `chat_member`, `chat_join_request` y otras que requieren permisos o `allowed_updates` explícitos; cualquier futura ampliación de moderación/coordination debe verificar esos requisitos contra la documentación oficial, no asumir que todos los eventos llegan automáticamente.

### Persistencia / concurrencia

La documentación actual de SQLAlchemy 2.0 confirma que `AsyncSession` es mutable y no debe compartirse entre tareas concurrentes; el modelo correcto es una sesión por tarea concurrente. También documenta el comportamiento de `aiosqlite` para SQLite y que las bases en memoria tienen particularidades de concurrencia. Esto respalda la estrategia del proyecto de abrir sesiones separadas por operación y de tratar cada transacción como unidad aislada.

### Tiempo del mundo

Python `zoneinfo` implementa las zonas IANA y puede tomar datos del sistema o del paquete `tzdata`. La documentación recomienda declarar `tzdata` cuando se necesita compatibilidad multiplataforma y el sistema, especialmente Windows, puede no tener la base horaria disponible. El proyecto ya adoptó esa defensa.

### IA opcional

Ollama documenta actualmente `/api/chat`, salidas estructuradas mediante JSON Schema y tool calling. Esto hace viable una futura IA curadora que entregue propuestas estructuradas y validables. No justifica convertir la IA en el cerebro del bot: para este proyecto debe permanecer detrás de una compuerta explícita y trabajar sobre datos agregados, inventario y reglas del mundo.

### CI

La documentación de GitHub recomienda ejecutar en CI los mismos comandos que se usan localmente, y muestra pytest, cobertura y Ruff como patrones de validación para proyectos Python. La auditoría, por tanto, debe seguir tratando cada fallo de CI como evidencia de un problema real hasta que una ejecución posterior lo cierre.

## Comparación de proyectos

Se revisaron varios proyectos públicos de aiogram para contrastar arquitectura y prácticas, entre ellos el repositorio oficial de aiogram, plantillas modulares con routers y configuración, y esqueletos que usan Unit of Work/servicios para separar lógica de handlers.

El hallazgo útil para Bot-IA no es copiar una plantilla: es confirmar que la separación `handlers / services / persistence / middleware`, el uso de routers y la validación de configuración son patrones recurrentes en proyectos maduros. La arquitectura actual de Bot-IA ya cubre buena parte de esa separación y su diferencia principal es deliberada: la lógica de personaje, mundo y repertorio authored-only es una capa de dominio que las plantillas genéricas no suelen proporcionar.

## Verificación técnica reciente

La ejecución de GitHub Actions `34936594933` terminó correctamente: compiló los cuatro bots y BotManager, verificó los ejecutables, ejecutó el smoke test de BotManager, generó instalador y portable, y subió ambos artefactos. Los tests nativos de media ejecutados en esa misma construcción fueron 15/15.

Las ejecuciones `34998729697` y `34999446085` detectaron regresiones durante el endurecimiento del repertorio/router. Ambas fueron corregidas y se agregaron pruebas más resistentes a posiciones fijas y falsos positivos.

La ejecución `35000051242` terminó correctamente sobre el commit `e9219bd8`: validó el trabajo de runtime social y su uso del repertorio de personajes.

La ejecución `35007258984` detectó un fallo de pytest porque la prueba comparaba un campo SQLAlchemy de tipo `str` usando `is` contra `BotIdentity.CARI`. La comparación quedó corregida en `cad996c85a184042027f6cdb43db606c561f4e28`.

El build de Windows `35007258794` terminó correctamente sobre el commit `640ef25...`, por lo que la vía de empaquetado sigue validada de forma independiente.

La ejecución `35008731690` fue disparada posteriormente por la actualización de auditoría y el endurecimiento de zona horaria. Al momento de esta revisión, su job de `test` seguía en ejecución; no se marca éxito hasta disponer de una conclusión positiva real.

## Trabajo actual

La capa de personajes está conectada de forma más directa al runtime: el chat de Cari usa intenciones explícitas y el director para seleccionar texto escrito, registra la escena utilizada en Ciudad Animals y mantiene seguimiento de usuario/chat sin almacenar texto bruto de la conversación. Las escenas de seguimiento quedan registradas bajo el personaje que realmente emitió el texto.

El runtime social local usa el mismo director determinista y consulta una rutina horaria antes del fallback local. La regla sigue siendo texto authored-only: la rutina selecciona un intent y el director selecciona una escena escrita; no se genera texto nuevo por esa vía.

Se añadió `app/characters/routines.py` con 12 ventanas deterministas para los cuatro personajes y `tests/test_character_routines.py` con cobertura de identidades, intents escritos, rangos horarios, determinismo y validación de reloj. También se añadieron escenas QUIET para Cami y Chie, necesarias para cubrir sus franjas de cierre.

Se añadió `localize_utc()` y `world_now()` en `app/core/time.py`. El runtime social usa la zona definida por `Settings.bot_world_timezone`, y `.env.example` documenta `BOT_WORLD_TIMEZONE=America/Argentina/Buenos_Aires`. `tzdata` queda declarado como dependencia para que el comportamiento sea reproducible en Windows y otros entornos sin base horaria del sistema.

La siguiente fase prioritaria sigue siendo ampliar el gran repertorio y construir el comportamiento de Café Otaku y Ciudad Animals alrededor de horarios, acontecimientos, objetos, relaciones y estadísticas, manteniendo la IA como componente opcional y no como cerebro permanente.
