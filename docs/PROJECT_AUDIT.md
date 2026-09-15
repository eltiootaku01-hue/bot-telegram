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
| Rutinas y horarios | 20% |
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
6. La conversación social todavía necesita una política más rica para decidir qué tipo de escena usar según hora, actividad, eventos y estado del personaje.
7. Café Otaku y las rutinas del mundo siguen siendo diseño parcial, no funcionalidades completas.
8. Se requieren auditorías posteriores para verificar que nuevos juegos o sistemas no desplacen el objetivo principal: personajes y mundo vivos sin dependencia continua de IA.
9. Las pruebas deben seguir protegiendo la voz específica de Sunna, Cami y Chie frente a expansiones futuras del repertorio.

## Criterio de finalización

No marcar 100% hasta comprobar: personajes completos, repertorio amplio, rutinas, interacciones, Café Otaku, mundo, estadísticas, funcionalidades previstas, GUI, pruebas de integración y auditorías repetidas.

## Verificación técnica reciente

La ejecución de GitHub Actions `34936594933` terminó correctamente: compiló los cuatro bots y BotManager, verificó los ejecutables, ejecutó el smoke test de BotManager, generó instalador y portable, y subió ambos artefactos. Los tests nativos de media ejecutados en esa misma construcción fueron 15/15.

La ejecución `34998729697` detectó una regresión del test del repertorio y la ejecución `34999446085` detectó una regresión del router. Ambas fueron corregidas y se agregaron pruebas más resistentes a posiciones fijas y falsos positivos.

Los cambios actuales también incorporan una prueba de cobertura mínima del repertorio y verifican que el compositor social local use escenas del mismo director determinista que la conversación normal.

## Trabajo actual

La capa de personajes está conectada de forma más directa al runtime: el chat de Cari usa intenciones explícitas y el director para seleccionar texto escrito, registra la escena utilizada en Ciudad Animals y mantiene seguimiento de usuario/chat sin almacenar texto bruto de la conversación.

El runtime social local también fue alineado con el director: Cari y Sunna usan escenas de silencio, mientras Cami y Chie usan escenas de actividad/ocupación cuando hablan espontáneamente. El objetivo es que un personaje no tenga una voz para el chat y otra distinta para sus intervenciones autónomas.

La siguiente fase prioritaria sigue siendo ampliar el gran repertorio y construir rutinas/escenas de Café Otaku y Ciudad Animals alrededor de horarios, acontecimientos, objetos, relaciones y estadísticas.
