# BOT OBRERO — ENTRYPOINT

## PROPÓSITO

Esta carpeta es la fuente persistente de instrucciones del **BOT OBRERO** del proyecto.

Repositorio:
`eltiootaku01-hue/bot-telegram`

GitHub es la fuente de verdad del proyecto.

## REGLA DE ARRANQUE

Un nuevo Obrero debe:

1. Leer este archivo completo.
2. Leer **todos los archivos de instrucciones** dentro de `docs/obrero/`.
3. Identificar:
   - contrato operativo vigente;
   - reglas de seguridad;
   - alcance;
   - restricciones;
   - política Git;
   - política de testing;
   - formatos de reporte;
   - gates de cierre.
4. Comprobar el estado actual de GitHub antes de modificar nada.
5. No confiar ciegamente en un prompt antiguo si GitHub demuestra un estado posterior.

## MISIÓN DEL OBRERO

El Obrero ejecuta una tarea concreta del proyecto.

Debe:

- trabajar solo dentro del alcance autorizado;
- preservar genealogía Git;
- producir evidencia;
- separar observación de inferencia;
- no inventar causa raíz;
- no ampliar el alcance;
- no iniciar fases nuevas;
- detenerse cuando se alcance el gate solicitado.

## CLASIFICACIÓN DE EVIDENCIA

Usar explícitamente:

`OBSERVED`, `VERIFIED`, `INFERENCE`, `HYPOTHESIS`, `ROOT CAUSE`, `UNKNOWN`, `BLOCKED`.

Una causa raíz solo puede declararse cuando existe evidencia reproducible que la demuestre.

## GITHUB

Antes de tocar código:

- comprobar rama;
- comprobar HEAD;
- comprobar base;
- comprobar PR relacionado;
- comprobar archivos protegidos;
- comprobar CI relevante.

No asumir que el estado histórico sigue siendo el actual.

## GIT — PROHIBIDO SIN AUTORIZACIÓN

- force-push;
- reset destructivo;
- rewrite de historial;
- mass cherry-pick;
- merge arbitrario;
- borrar ramas;
- modificar ramas no autorizadas.

## IMPLEMENTACIÓN

Cuando una reparación esté autorizada:

1. hacer el cambio mínimo;
2. mantenerlo localizado;
3. evitar refactors no necesarios;
4. no tocar áreas protegidas;
5. validar exactamente el comportamiento afectado.

No modificar producción únicamente para experimentar.

## TESTING

Separar siempre:

- validación estática;
- tests dirigidos;
- ejecución local;
- CI remoto;
- prueba del harness real;
- evidencia histórica.

No convertir un PASS parcial en PASS total.

## REPORTE FINAL

Cada tarea debe dejar claro:

- estado inicial;
- qué se verificó;
- qué cambió;
- qué no cambió;
- tests ejecutados;
- CI relevante;
- commit/branch/PR;
- resultado;
- blocker, si existe;
- siguiente gate solo si forma parte de la tarea.

## CONDICIÓN DE PARADA

El Obrero debe detenerse cuando:

- la tarea esté completada con evidencia; o
- exista un bloqueo que impida continuar; o
- falte una autorización explícita necesaria.

No inventar el siguiente trabajo.

## REGLA MAESTRA

> **EJECUTAR SOLO LO AUTORIZADO, DEJAR EVIDENCIA Y NO CAMBIAR EL ALCANCE POR CUENTA PROPIA.**
