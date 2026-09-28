# Project Memory — Decisions

## Regla

Solo se registran decisiones respaldadas. Una inferencia histórica no se convierte en decisión por aparecer en este archivo.

### DEC-001 — Supervisor como capa de coordinación y verificación

- Estado: [DECIDED]
- Origen: FASE 2E.
- Decisión: El Supervisor se ubica por encima de los runtimes existentes y coordina observación, evidencia, control, presupuestos y verificación.
- Motivo: Evitar que el Supervisor duplique o sustituya componentes operativos existentes.
- Evidencia: contrato de FASE 2E y auditoría FASE 2E.
- Impacto: Las futuras integraciones deben respetar las autoridades existentes de TaskEngine, TaskScheduler y WebQueue.
- No implica: implementación completa del Supervisor.
- Fuentes: FASE 2E; `docs/ARQUITECTURA.md`.

### DEC-002 — Observation Core con lectura por defecto

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-1.
- Decisión: Observation Core observa y verifica; la escritura sobre el sistema observado está bloqueada por defecto.
- Motivo: mantener separación entre observación y mutación.
- Evidencia: PR #62, HEAD `298748830af133079946f4d1eb8c87dedb8f4ea4`, tests del Observation Core y CI `36392137591`, `36392275545`.
- Impacto: futuras capacidades de escritura requieren autorización explícita y control de alcance.
- No implica: que el Supervisor futuro no pueda autorizar escrituras; solo que esa capacidad no forma parte del Observation Core actual.
- Fuentes: PR #62; FASE 2F-1V.

### DEC-003 — Separación del almacenamiento de evidencia

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-1.
- Decisión: el Evidence Store del Observation Core no debe residir dentro del repositorio observado.
- Motivo: evitar que la observación altere el objeto que está auditando.
- Evidencia: test de aislamiento de almacenamiento y HEAD `298748830af133079946f4d1eb8c87dedb8f4ea4`.
- Impacto: la evidencia debe mantenerse en almacenamiento separado.
- No implica: formato definitivo del Evidence Store futuro.
- Fuentes: PR #62; FASE 2F-1V.

### DEC-004 — Estados epistemológicos explícitos

- Estado: [DECIDED]
- Origen: FASE 2F-MEM y autorización de persistencia documental.
- Decisión: la memoria externa conserva etiquetas [OBSERVED], [TESTED], [DECIDED], [INFERRED], [PROPOSED], [UNKNOWN], [BLOCKED], [USER_PROVIDED] sin elevar estados.
- Motivo: impedir que una inferencia o propuesta se convierta accidentalmente en hecho o decisión.
- Evidencia: contrato de FASE 2F-MEM-W2.
- Impacto: los documentos de esta carpeta deben conservar la trazabilidad epistemológica.
- No implica: que las etiquetas sean una especificación técnica del runtime.
- Fuentes: FASE 2F-MEM-W2; auditorías FASE 2A–2F.

### DEC-005 — No fusionar TCG/TMA durante esta etapa

- Estado: [DECIDED]
- Origen: FASE 2B y fases posteriores de auditoría.
- Decisión: no realizar fusión TCG/TMA con el BOT-IA moderno durante esta operación.
- Motivo: evidencia arquitectónica insuficiente para cerrar la decisión histórica y alcance explícito de la fase.
- Evidencia: FASE 2B = D — evidencia insuficiente; FASE 2E; autorización FASE 2F-MEM-W2.
- Impacto: TCG/TMA permanece documentado como dominio separado.
- No implica: decisión permanente sobre su arquitectura futura.
- Fuentes: FASE 2B; FASE 2E; FASE 2F-MEM-W2.
