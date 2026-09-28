# Project Memory — Decisions

## Regla

Solo se registran decisiones respaldadas. Una inferencia histórica no se convierte en decisión por aparecer en este archivo.

### DEC-001 — Supervisor como capa de coordinación y verificación

- Estado: [DECIDED]
- Origen: FASE 2E.
- Decisión: El Supervisor se ubica por encima de los runtimes existentes y coordina observación, evidencia, control, presupuestos y verificación.
- Motivo: Evitar que el Supervisor duplique o sustituya componentes operativos existentes.
- Evidencia: contrato de FASE 2E.
- Impacto: futuras integraciones deben respetar las autoridades existentes.
- No implica: implementación completa del Supervisor.
- Fuentes: FASE 2E.

### DEC-002 — Observation Core con lectura por defecto

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-1.
- Decisión: Observation Core observa y verifica; la escritura sobre el sistema observado está bloqueada por defecto.
- Motivo: separar observación de mutación.
- Evidencia: PR #62, HEAD `298748830af133079946f4d1eb8c87dedb8f4ea4`, CI `36392137591`, `36392275545`.
- Impacto: futuras escrituras requieren autorización explícita.
- No implica: autoridad física final de escritura.
- Fuentes: FASE 2F-1V.

### DEC-003 — Separación del almacenamiento de evidencia

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-1.
- Decisión: EvidenceStore no debe residir dentro del repositorio observado.
- Motivo: evitar que la observación altere el objeto auditado.
- Evidencia: test de aislamiento y HEAD `298748830af133079946f4d1eb8c87dedb8f4ea4`.
- Impacto: evidencia fuera del repositorio observado.
- No implica: formato definitivo futuro.
- Fuentes: FASE 2F-1V.

### DEC-004 — Estados epistemológicos explícitos

- Estado: [DECIDED]
- Origen: FASE 2F-MEM-W2.
- Decisión: conservar [OBSERVED], [TESTED], [DECIDED], [INFERRED], [PROPOSED], [UNKNOWN], [BLOCKED], [USER_PROVIDED] sin elevar estados.
- Motivo: preservar provenance.
- Evidencia: memoria persistida.
- Impacto: Claims y Scope Lock deben conservar separación entre hecho, inferencia y propuesta.
- No implica: que estas etiquetas sean una API runtime.
- Fuentes: FASE 2F-MEM-W2.

### DEC-005 — No fusionar TCG/TMA durante esta etapa

- Estado: [DECIDED]
- Origen: FASE 2B y fases posteriores.
- Decisión: no realizar fusión TCG/TMA con BOT-IA moderno durante esta etapa.
- Motivo: evidencia histórica insuficiente y alcance explícito.
- Evidencia: FASE 2B = D; autorización de fases 2F.
- Impacto: dominios permanecen diferenciados.
- No implica: decisión histórica permanente.
- Fuentes: FASE 2B; FASE 2F.

### DEC-006 — Claims reutiliza EvidenceStore

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-2.
- Decisión: ClaimStore recibe y consulta el EvidenceStore existente; no crea un segundo almacén de evidencia.
- Motivo: mantener una única fuente de evidencia.
- Evidencia: implementación de `ClaimStore` y CI `36432587482`.
- Impacto: los claims dependen de evidence IDs verificables del EvidenceStore.
- No implica: una base de datos nueva ni persistencia independiente de claims.
- Fuentes: FASE 2F-2; PR #63.

### DEC-007 — Scope Lock como default deny contractual

- Estado: [DECIDED] + [TESTED]
- Origen: FASE 2F-2.
- Decisión: ScopeLock deniega por defecto todo path u operación no explícitamente permitidos; las prohibiciones tienen precedencia.
- Motivo: evitar expansión accidental del alcance.
- Evidencia: tests de default deny, forbidden operation, traversal, absolute path y symlink escape; CI `36432587482`.
- Impacto: el contrato permite expresar alcance mínimo antes de futuras escrituras.
- No implica: implementación de la autoridad física final de escritura.
- Fuentes: FASE 2F-2; PR #63.
