# GATE — CUERPO SANO

## OBJETIVO

Esta es la puerta de salud arquitectónica previa a la activación integral del sistema.

No significa "cero tickets".

Significa que los fallos capaces de romper el cuerpo completo están diagnosticados y controlados.

## NO AVANZAR A

- activación integral del ecosistema;
- ejecución simultánea de todos los subsistemas;
- expansión funcional que aumente la superficie de concurrencia;
- nueva migración WebChat;
- eliminación de legacy;
- multi-proceso no auditado.

mientras existan HUESOS CRITICAL/HIGH sin diagnóstico y sin gate explícito.

## CONDICIONES

### CRITICAL

Debe estar:

`CLOSED`

### HIGH

Debe estar:

`CLOSED`

o existir una excepción técnica explícita con:

- motivo;
- alcance;
- riesgo residual;
- mitigación;
- responsable;
- gate de revalidación.

### MEDIUM

Debe existir:

- diagnóstico;
- evidencia;
- plan.

### LOW

Puede permanecer abierto si no afecta el gate actual.

## MUY IMPORTANTE

Una hipótesis no es un fallo confirmado.

Una documentación antigua no es automáticamente una regla actual.

Un PASS parcial no es un PASS integral.

Un test unitario no demuestra lifecycle físico.

Un proceso que "parece cerrar" no demuestra que haya liberado todos sus recursos.

## CHECKLIST DE CUERPO

[ ] GUI lifecycle

[ ] Qt ↔ asyncio boundary

[ ] Telegram worker lifecycle

[ ] SQLite concurrency

[ ] Outbox atomicity

[ ] Task cancellation propagation

[ ] WebChat physical authority

[ ] QWebEngine lifecycle

[ ] Playwright lifecycle

[ ] dual startup ownership

[ ] PyInstaller packaging model

[ ] provider workload isolation

[ ] context/memory growth

[ ] shutdown completo

## CIERRE DEL GATE

El gate solo puede declararse:

**CUERPO SANO / ACTIVACIÓN AUTORIZADA**

cuando exista evidencia suficiente para cada punto relevante.

Hasta entonces:

**BODY HEALTH = BLOCKED**

y el trabajo permitido es diagnóstico, reparación localizada y validación.

