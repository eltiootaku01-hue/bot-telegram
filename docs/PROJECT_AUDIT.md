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
| Repertorio escrito | 44% |
| Router determinista de intenciones | 50% |
| Rutinas y horarios | 38% |
| Interacciones entre personajes | 27% |
| Café Otaku | 20% |
| Ciudad Animals | 32% |
| Estadísticas del mundo | 38% |
| Registro automático de uso de escenas | 35% |
| IA como curadora periódica | 20% |
| Juegos nuevos (misterios, cartas, etc.) | 10% |
| GUI completa de edición | 20% |

## Riesgos activos detectados por auditoría

1. La personalidad está definida pero no toda está conectada al runtime de conversación.
2. El repertorio sigue creciendo, pero todavía está lejos del volumen necesario para que los cuatro personajes tengan una vida de NPC amplia y sostenible.
3. La conversación debe seguir siendo determinista y explícitamente activada. El router usa coincidencias de palabras/frases completas y contempla variantes habituales con acentos.
4. El runtime social ya usa el director y el repertorio para sus respuestas locales, pero todavía necesita más categorías y escenas específicas para que las intervenciones espontáneas tengan mayor variedad.
5. Ciudad Animals ya puede registrar escenas usadas, intención y ámbito de usuario/chat desde la conversación de Cari. Falta extender el mismo registro a otros flujos de personajes y a más acontecimientos del mundo.
6. Ya existe una primera política de rutinas por horario para las intervenciones locales, pero todavía debe incorporar zona horaria configurable, actividad del café, eventos, relaciones y estado del personaje antes de considerarse completa.
7. Café Otaku y las rutinas del mundo siguen siendo funcionalidad parcial: las franjas horarias ya están modeladas y consumidas por el runtime social, pero todavía faltan objetos, servicios, economía y eventos conectados a esas rutinas.
8. Se requieren auditorías posteriores para verificar que nuevos juegos o sistemas no desplacen el objetivo principal: personajes y mundo vivos sin dependencia continua de IA.
9. Las pruebas deben seguir protegiendo la voz específica de Sunna, Cami y Chie frente a expansiones futuras del repertorio.

## Criterio de finalización

No marcar 100% hasta comprobar: personajes completos, repertorio amplio, rutinas, interacciones, Café Otaku, mundo, estadísticas, funcionalidades previstas, GUI, pruebas de integración y auditorías repetidas.

## Verificación técnica reciente

La ejecución de GitHub Actions `34936594933` terminó correctamente: compiló los cuatro bots y BotManager, verificó los ejecutables, ejecutó el smoke test de BotManager, generó instalador y portable, y subió ambos artefactos. Los tests nativos de media ejecutados en esa misma construcción fueron 15/15.

Las ejecuciones `34998729697` y `34999446085` detectaron regresiones durante el endurecimiento del repertorio/router. Ambas fueron corregidas y se agregaron pruebas más resistentes a posiciones fijas y falsos positivos.

La ejecución `35000051242` terminó correctamente sobre el commit `e9219bd8`: validó el trabajo de runtime social y su uso del repertorio de personajes.

Los cambios actuales incorporan además una prueba de cobertura mínima del repertorio, pruebas del compositor social y una nueva suite para el director de rutinas horarias.

## Trabajo actual

La capa de personajes está conectada de forma más directa al runtime: el chat de Cari usa intenciones explícitas y el director para seleccionar texto escrito, registra la escena utilizada en Ciudad Animals y mantiene seguimiento de usuario/chat sin almacenar texto bruto de la conversación.

El runtime social local también fue alineado con el director: Cari y Sunna usan escenas de silencio fuera de una franja específica, mientras Cami y Chie usan escenas de actividad/ocupación. Ahora el compositor puede consultar una rutina horaria y seleccionar el intent correspondiente del repertorio escrito, sin generar texto nuevo.

Se añadió `app/characters/routines.py` con 12 ventanas deterministas para los cuatro personajes y `tests/test_character_routines.py` para comprobar cobertura, rangos horarios, determinismo y rechazo de valores inválidos. `app/core/social_runtime.py` consume esas rutinas antes de usar el fallback local genérico.

La siguiente fase prioritaria sigue siendo ampliar el gran repertorio y construir el comportamiento de Café Otaku y Ciudad Animals alrededor de horarios, acontecimientos, objetos, relaciones y estadísticas, manteniendo la IA como componente opcional y no como cerebro permanente.
