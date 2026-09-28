# Project Memory — Open Questions

## 1. Separación histórica permanente TCG/TMA

- Estado: [UNKNOWN]
- Pregunta: ¿La separación entre TCG/TMA y BOT-IA moderno fue una decisión histórica permanente y documentada?
- Falta: fuente histórica explícita.

## 2. Scope Lock físico

- Estado: [UNKNOWN]
- Pregunta: ¿Cómo se hará cumplir físicamente el Scope Lock frente a una operación real?
- Conocido: el contrato lógico ya existe.
- Falta: enforcement físico.

## 3. Evidence Store futuro

- Estado: [UNKNOWN]
- Pregunta: ¿Cuál será el formato, persistencia, retención y versionado definitivos?
- Conocido: Observation Core usa JSONL externo al repositorio observado.
- No implica: que JSONL sea la arquitectura final.

## 4. Autorización física de escritura

- Estado: [UNKNOWN]
- Pregunta: ¿Quién y mediante qué mecanismo puede autorizar una escritura real?
- Conocido: ScopeLock representa owner y authorization como contrato.
- Falta: mecanismo físico final.

## 5. Supervisor → TaskEngine

- Estado: [UNKNOWN]
- Pregunta: ¿Qué adapter o interfaz concreta conectará Supervisor con TaskEngine?
- Falta: diseño técnico final.

## 6. Personajes vivos

- Estado: [UNKNOWN]
- Pregunta: ¿Cuál será la especificación técnica final de personajes vivos, estados, memoria y persistencia?
- Falta: implementación y contrato final.

## 7. Percepción diegética

- Estado: [UNKNOWN]
- Pregunta: ¿Cómo se representará técnicamente la percepción de eventos por personajes?
- Falta: especificación técnica final.

## 8. Investigación de mercado

- Estado: [UNKNOWN]
- Pregunta: ¿Dónde debe persistirse la investigación externa y cuál será su política de provenance?
- Conocido: no existe una fuente documental persistente completa identificada.

## 9. Claims persistentes

- Estado: [UNKNOWN]
- Pregunta: ¿Debe ClaimStore obtener persistencia propia en una fase posterior?
- Conocido: actualmente es memoria en proceso y reutiliza EvidenceStore para validar evidencia.
