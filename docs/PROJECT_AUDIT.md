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
| Repertorio escrito | 42% |
| Router determinista de intenciones | 45% |
| Rutinas y horarios | 20% |
| Interacciones entre personajes | 27% |
| Café Otaku | 20% |
| Ciudad Animals | 29% |
| Estadísticas del mundo | 35% |
| Registro automático de uso de escenas | 10% |
| IA como curadora periódica | 20% |
| Juegos nuevos (misterios, cartas, etc.) | 10% |
| GUI completa de edición | 20% |

## Riesgos activos detectados por auditoría

1. La personalidad está definida pero no toda está conectada al runtime de conversación.
2. El repertorio sigue creciendo, pero todavía está lejos del volumen necesario para que los cuatro personajes tengan una vida de NPC amplia y sostenible.
3. La conversación debe seguir siendo determinista y explícitamente activada; el router usa coincidencias de palabras/frases completas para evitar falsos positivos dentro de otras palabras.
4. El runtime social todavía usa un compositor local pequeño separado del director de personajes; su integración futura debe usar el repertorio sin aumentar en exceso la frecuencia de intervención.
5. Ciudad Animals puede registrar agregados y catálogo, pero el uso de escenas del repertorio todavía no se observa automáticamente desde el runtime. Esto debe resolverse antes de considerar completas las métricas de "más usado / menos usado / nunca usado" para personajes.
6. Café Otaku y las rutinas del mundo siguen siendo diseño parcial, no funcionalidades completas.
7. Se requieren auditorías posteriores para verificar que nuevos juegos o sistemas no desplacen el objetivo principal: personajes y mundo vivos sin dependencia continua de IA.
8. Deben existir pruebas que protejan la voz específica de Sunna, Cami y Chie frente a expansiones futuras del repertorio.

## Criterio de finalización

No marcar 100% hasta comprobar: personajes completos, repertorio amplio, rutinas, interacciones, Café Otaku, mundo, estadísticas, funcionalidades previstas, GUI, pruebas de integración y auditorías repetidas.

## Verificación técnica reciente

La ejecución de GitHub Actions `34936594933` terminó correctamente: compiló los cuatro bots y BotManager, verificó los ejecutables, ejecutó el smoke test de BotManager, generó instalador y portable, y subió ambos artefactos. Los tests nativos de media ejecutados en esa misma construcción fueron 15/15.

La ejecución `34998729697` detectó una regresión del test del repertorio tras el endurecimiento de la integración de personajes: Ruff pasó y 155 pruebas pasaron, pero el test de intervención de Cari esperaba la variante de seguimiento en una posición fija del repertorio. Ese test fue corregido para validar la propiedad importante —que exista una variante de Cari que delegue en Cami— en lugar de depender de un índice concreto.

## Trabajo actual

La capa de personajes está avanzando hacia el runtime: existe un director determinista y un router pequeño de intenciones explícitas que usa exclusivamente el repertorio escrito. El chat de Cari queda limitado a esas señales para no capturar mensajes destinados a otros módulos.

En la ronda actual se endureció la coincidencia del router para que no reconozca palabras clave embebidas dentro de otras palabras y se añadieron pruebas específicas para esos límites. También se amplió el repertorio escrito y se reforzaron las pruebas del director.

La siguiente integración prioritaria es unir las escenas realmente seleccionadas por los personajes con la observación de Ciudad Animals, de modo que el mundo pueda medir qué escenas se usan, cuáles quedan frías y cuáles nunca aparecen, sin almacenar el texto bruto de las conversaciones.
