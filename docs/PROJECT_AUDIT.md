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
| Rutinas y horarios | 46% |
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
6. Las rutinas horarias ahora convierten UTC a una zona del mundo explícita (`BOT_WORLD_TIMEZONE`, con `America/Argentina/Buenos_Aires` como valor por defecto); todavía falta centralizar esta configuración en `Settings`/GUI y ampliar la lógica con actividad del café, eventos, relaciones y estado del personaje.
7. Café Otaku y las rutinas del mundo siguen siendo funcionalidad parcial: las franjas horarias ya están modeladas y consumidas por el runtime social, pero todavía faltan objetos, servicios, economía y eventos conectados a esas rutinas.
8. Se requieren auditorías posteriores para verificar que nuevos juegos o sistemas no desplacen el objetivo principal: personajes y mundo vivos sin dependencia continua de IA.
9. Las pruebas deben seguir protegiendo la voz específica de Sunna, Cami y Chie frente a expansiones futuras del repertorio.
10. El último fallo de CI conocido fue un error de aserción en `test_chat_world_attribution.py`; el test ya fue corregido en el commit `cad996c85a184042027f6cdb43db606c561f4e28`. No se marca CI verde hasta observar una ejecución posterior que pase realmente.

## Criterio de finalización

No marcar 100% hasta comprobar: personajes completos, repertorio amplio, rutinas, interacciones, Café Otaku, mundo, estadísticas, funcionalidades previstas, GUI, pruebas de integración y auditorías repetidas.

## Verificación técnica reciente

La ejecución de GitHub Actions `34936594933` terminó correctamente: compiló los cuatro bots y BotManager, verificó los ejecutables, ejecutó el smoke test de BotManager, generó instalador y portable, y subió ambos artefactos. Los tests nativos de media ejecutados en esa misma construcción fueron 15/15.

Las ejecuciones `34998729697` y `34999446085` detectaron regresiones durante el endurecimiento del repertorio/router. Ambas fueron corregidas y se agregaron pruebas más resistentes a posiciones fijas y falsos positivos.

La ejecución `35000051242` terminó correctamente sobre el commit `e9219bd8`: validó el trabajo de runtime social y su uso del repertorio de personajes.

Después se añadieron rutinas horarias, escenas de silencio faltantes para Cami/Chie y protección de atribución de escenas de seguimiento. La ejecución `35007258984` detectó un fallo de pytest porque la prueba comparaba un campo SQLAlchemy de tipo `str` usando `is` contra `BotIdentity.CARI`. La comparación quedó corregida en el commit `cad996c85a184042027f6cdb43db606c561f4e28`.

El build de Windows `35007258794` terminó correctamente sobre el commit `640ef25...`, por lo que la vía de empaquetado sigue validada de forma independiente. Todavía falta una ejecución CI posterior que confirme el estado conjunto tras las correcciones recientes.

## Trabajo actual

La capa de personajes está conectada de forma más directa al runtime: el chat de Cari usa intenciones explícitas y el director para seleccionar texto escrito, registra la escena utilizada en Ciudad Animals y mantiene seguimiento de usuario/chat sin almacenar texto bruto de la conversación. Las escenas de seguimiento quedan registradas bajo el personaje que realmente emitió el texto.

El runtime social local usa el mismo director determinista y consulta una rutina horaria antes del fallback local. La regla sigue siendo texto authored-only: la rutina selecciona un intent y el director selecciona una escena escrita; no se genera texto nuevo por esa vía.

Se añadió `app/characters/routines.py` con 12 ventanas deterministas para los cuatro personajes y `tests/test_character_routines.py` con cobertura de identidades, intents escritos, rangos horarios, determinismo y validación de reloj. También se añadieron escenas QUIET para Cami y Chie, necesarias para cubrir sus franjas de cierre.

Se añadió `localize_utc()` y `world_now()` en `app/core/time.py`, y el runtime social usa `BOT_WORLD_TIMEZONE` para que las rutinas se evalúen con la hora del mundo en vez de la hora UTC. `tests/test_time.py` protege la conversión para Buenos Aires y la validación de zona vacía.

La siguiente fase prioritaria sigue siendo ampliar el gran repertorio y construir el comportamiento de Café Otaku y Ciudad Animals alrededor de horarios, acontecimientos, objetos, relaciones y estadísticas, manteniendo la IA como componente opcional y no como cerebro permanente.
