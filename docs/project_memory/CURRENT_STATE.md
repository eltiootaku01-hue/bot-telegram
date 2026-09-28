# Project Memory — Current State

## Epistemic policy

Esta memoria externa conserva únicamente estados con etiqueta epistemológica. Las etiquetas usadas son: [OBSERVED], [TESTED], [DECIDED], [INFERRED], [PROPOSED], [UNKNOWN], [BLOCKED], [USER_PROVIDED].

## Repository

- [OBSERVED] Branch: `feature/supervisor-observation-core`.
- [OBSERVED] HEAD de partida de esta operación: `298748830af133079946f4d1eb8c87dedb8f4ea4`.
- [TESTED] El HEAD de la rama fue verificado antes de escribir y coincidió exactamente con el SHA autorizado.
- [OBSERVED] El HEAD corresponde al commit `test(supervisor): enforce evidence storage isolation`.

## Supervisor

- [TESTED] La FASE 2E definió un contrato de Supervisor por encima de los runtimes existentes.
- [DECIDED] El Supervisor no sustituye Cerebro, Obrero, TaskEngine, TaskScheduler ni WebQueue.
- [DECIDED] El Supervisor observa, valida evidencia, controla transiciones autorizadas y verifica cambios; no debe inventar hechos ni marcar como verificado algo sin evidencia.
- [PROPOSED] Las fases posteriores pueden implementar los componentes restantes del contrato, pero esta memoria no autoriza su implementación.

## Observation Core

- [TESTED] Observation Core existe en la rama como seis archivos nuevos bajo `src/bot_ia/supervisor/` y su prueba correspondiente.
- [TESTED] PR #62 corresponde a la implementación del Observation Core.
- [TESTED] HEAD validado: `298748830af133079946f4d1eb8c87dedb8f4ea4`.
- [TESTED] CI de referencia: `36392137591` y `36392275545`; en la validación previa ambos tuvieron jobs Linux y Windows exitosos.
- [TESTED] La validación FASE 2F-1V confirmó compilación, política de código, superficie de imports y suite de tests en los jobs reportados.
- [DECIDED] El Observation Core mantiene observación de solo lectura sobre el sistema observado y bloquea por defecto la escritura sobre ese sistema.
- [OBSERVED] El almacenamiento de evidencia se diseñó fuera del repositorio observado y existe una prueba que rechaza almacenamiento dentro del repositorio.

## Arquitectura y runtimes protegidos

- [OBSERVED] BOT-IA moderno usa un backend común para consola, Telegram y API web; README documenta biblioteca, evidencia, memoria y EvidenceGate.
- [DECIDED] Durante las fases 2F-1 y 2F-1V no se modificaron los runtimes protegidos ni sus infraestructuras.
- [DECIDED] TaskEngine, TaskScheduler y WebQueue no se reemplazan por un segundo mecanismo equivalente dentro del Observation Core.
- [DECIDED] La integración física del Supervisor con esos componentes permanece fuera de esta fase.

## TCG/TMA

- [OBSERVED] TCG/TMA constituye un dominio funcional diferenciado dentro del repositorio.
- [INFERRED] La separación arquitectónica actual reduce el acoplamiento con el BOT-IA moderno.
- [UNKNOWN] No existe evidencia suficiente en esta memoria para convertir en decisión histórica permanente la separación TCG/TMA.
- [DECIDED] No se realiza fusión TCG/TMA durante esta operación.

## Documentación

- [OBSERVED] Existían documentos de arquitectura, auditoría, roadmap y acciones de ChatGPT antes de esta operación.
- [OBSERVED] No existía previamente el directorio canónico `docs/project_memory/` identificado durante FASE 2F-MEM.
- [DECIDED] Esta operación crea nueve documentos de memoria externa y no altera código, tests, workflows, dependencias, configuración ni DB.

## Fuentes

[OBSERVED] `README.md`; `docs/ARQUITECTURA.md`; `docs/FASE_0_3_AUDITORIA_REQUISITOS_ARQUITECTURA_DECISIONES_2026-09-27.md`; `docs/ROADMAP.md`; `docs/ROADMAP_AUDIT_2026-09.md`; `docs/CHATGPT_ACTIONS.md`; auditorías FASE 2A–2F-MEM; PR #62 y CI indicadas arriba.
