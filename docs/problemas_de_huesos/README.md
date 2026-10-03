# PROBLEMAS DE HUESOS — REGISTRO DE SALUD ARQUITECTÓNICA

## PROPÓSITO

Esta carpeta contiene el registro persistente de problemas, riesgos, hipótesis y zonas de fragilidad de la arquitectura de BOT-IA.

Nombre operativo:

**PROBLEMAS DE HUESOS / BODY HEALTH**

Objetivo:

> **No avanzar hacia la activación integral del sistema mientras existan riesgos críticos o altos no auditados o no cerrados.**

Esta carpeta NO convierte automáticamente una hipótesis en un bug confirmado.

Cada hallazgo debe clasificarse como:

- OBSERVED
- VERIFIED
- HYPOTHESIS
- RISK
- BLOCKED
- CLOSED

## REGLA DE SALUD

Un agente NO debe interpretar esta carpeta como autorización para modificar todo lo registrado.

Primero debe:

1. identificar el hallazgo;
2. comprobar evidencia actual en GitHub;
3. reproducir o aislar cuando corresponda;
4. decidir si realmente existe;
5. definir reparación mínima;
6. validar;
7. marcar CLOSED solo con evidencia.

## GATE CORPORAL

Antes de pasar a una fase de activación/integración integral:

- todos los hallazgos CRITICAL deben estar CLOSED;
- todos los hallazgos HIGH deben estar CLOSED o tener una excepción explícita y documentada;
- los hallazgos MEDIUM/LOW deben tener diagnóstico y plan, aunque no bloqueen por sí solos una fase no relacionada;
- ninguna hipótesis puede presentarse como causa raíz;
- no debe existir deuda conocida que pueda producir corrupción de estado, procesos huérfanos, duplicación de ejecución o pérdida silenciosa de datos sin un gate explícito.

## PRIORIDAD

CRITICAL
→ puede bloquear cualquier activación.

HIGH
→ normalmente bloquea la integración afectada.

MEDIUM
→ debe diagnosticarse y planificarse.

LOW
→ se mantiene registrada sin bloquear por sí sola.

## RELACIÓN CON CEREBRO Y OBRERO

El Cerebro utiliza esta carpeta como inventario de salud arquitectónica.

El Obrero recibe tareas concretas derivadas de estos hallazgos.

Ningún Obrero debe solucionar varios huesos en una sola tarea salvo autorización explícita.

## REGLA MAESTRA

> **NO TAPAR SÍNTOMAS. PRIMERO DIAGNOSTICAR EL HUESO, DESPUÉS REPARARLO, DESPUÉS PROBAR QUE EL CUERPO SIGUE ENTERO.**
