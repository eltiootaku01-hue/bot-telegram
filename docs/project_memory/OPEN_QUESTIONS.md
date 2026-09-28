# Project Memory — Open Questions

## 1. Separación histórica permanente TCG/TMA

- Estado: [UNKNOWN]
- Pregunta: ¿La separación entre TCG/TMA y BOT-IA moderno fue una decisión histórica permanente y documentada, o solo una condición arquitectónica de una etapa?
- Evidencia disponible: auditorías FASE 2B–2D.
- Falta: fuente histórica explícita que cierre la intención permanente.
- No asumir: [UNKNOWN] no significa que exista integración.

## 2. Scope Lock físico

- Estado: [UNKNOWN]
- Pregunta: ¿Cuál será el mecanismo físico definitivo para representar y hacer cumplir Scope Lock?
- Conocido: FASE 2E definió alcance autorizado, archivos prohibidos, operaciones y change budget como contrato lógico.
- Falta: implementación física autorizada.

## 3. Evidence Store futuro

- Estado: [UNKNOWN]
- Pregunta: ¿Cuál será el formato, persistencia, retención y versionado definitivos del Evidence Store?
- Conocido: Observation Core usa persistencia JSONL y mantiene el almacenamiento fuera del repositorio observado.
- No implica: que JSONL sea la arquitectura final.

## 4. Autorización física de escritura

- Estado: [UNKNOWN]
- Pregunta: ¿Qué mecanismo concreto autorizará una escritura del Supervisor y cómo se auditará?
- Conocido: el contrato exige autorización previa y control de alcance.
- Falta: mecanismo físico.

## 5. Supervisor → TaskEngine

- Estado: [UNKNOWN]
- Pregunta: ¿Qué adapter o interfaz concreta conectará el Supervisor con TaskEngine?
- Conocido: FASE 2E conserva TaskEngine como autoridad de lifecycle operativo.
- Falta: diseño técnico final.

## 6. Personajes vivos

- Estado: [UNKNOWN]
- Pregunta: ¿Cuál será la especificación técnica final de personajes vivos, estados, memoria y persistencia?
- Conocido: existe un modelo conceptual separado en CHARACTER_SYSTEM.md.
- Falta: implementación y contrato final.

## 7. Percepción diegética

- Estado: [UNKNOWN]
- Pregunta: ¿Cómo se representará técnicamente la percepción de eventos por los personajes?
- Falta: especificación técnica final.

## 8. Investigación de mercado

- Estado: [UNKNOWN]
- Pregunta: ¿Dónde debe persistirse la investigación externa y cuál será su política de provenance?
- Conocido: las fases previas usaron investigación externa; no se identificó una fuente documental persistente completa en el repositorio.
