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
| Repertorio escrito | 38% |
| Router determinista de intenciones | 35% |
| Rutinas y horarios | 20% |
| Interacciones entre personajes | 27% |
| Café Otaku | 20% |
| Ciudad Animals | 29% |
| Estadísticas del mundo | 35% |
| IA como curadora periódica | 20% |
| Juegos nuevos (misterios, cartas, etc.) | 10% |
| GUI completa de edición | 20% |

## Riesgos activos detectados por auditoría

1. La personalidad está definida pero no toda está conectada al runtime de conversación.
2. El repertorio actual es amplio para una primera etapa, pero todavía pequeño frente al objetivo de un NPC con gran variedad y escenas recurrentes.
3. La conversación debe seguir siendo determinista y opt-in; un handler global de texto puede interferir con otros módulos y debe mantenerse filtrado.
4. El runtime social todavía usa un compositor local pequeño separado del director de personajes; la próxima integración debe llevarlo al repertorio sin hacer que los bots hablen demasiado.
5. Café Otaku y las rutinas del mundo todavía son diseño parcial, no funcionalidades completas.
6. Se requieren auditorías posteriores para verificar que nuevos juegos o sistemas no desplacen el objetivo principal: personajes y mundo vivos sin dependencia continua de IA.

## Criterio de finalización

No marcar 100% hasta comprobar: personajes completos, repertorio amplio, rutinas, interacciones, Café Otaku, mundo, estadísticas, funcionalidades previstas, GUI, pruebas de integración y auditorías repetidas.

## Verificación técnica reciente

La ejecución de GitHub Actions `34936594933` terminó correctamente: compiló los cuatro bots y BotManager, verificó los ejecutables, ejecutó el smoke test de BotManager, generó instalador y portable, y subió ambos artefactos. Los tests nativos de media ejecutados en esa misma construcción fueron 15/15.

## Trabajo actual

La capa de personajes está avanzando hacia el runtime: existe un director determinista y ahora un router pequeño de intenciones explícitas que usa exclusivamente el repertorio escrito. El chat de Cari queda limitado a esas señales para no capturar mensajes destinados a otros módulos.
