# Auditoría incremental — 2026-09-16

## Alcance

Revisión del runtime social, personajes authored-only y observación de Ciudad Animals sobre `main`.

## Hallazgo crítico

`app/core/social_runtime.py` podía reemplazar la salida producida por `LocalSocialComposer` con una generación libre del Brain cuando `Settings.ai_for(identity)` estaba activo.

Esto era una desviación de la arquitectura **código local primero, IA después**: el runtime social proactivo debía conservar el comportamiento authored-only aunque existiera una configuración de IA.

## Corrección aplicada

El runtime social proactivo ya no invoca el Brain para sustituir el mensaje.

El flujo queda:

```text
wake
  ↓
observe
  ↓
decide
  ↓
turn
  ↓
RoutineDirector / CharacterDirector
  ↓
authored repertoire
  ↓
Telegram
```

La IA permanece disponible para funcionalidades explícitas y para la futura curaduría, pero no controla silenciosamente la personalidad cotidiana de los bots.

## Revisión de personajes

`CharacterProfile` contiene drivers canónicos para Cari, Cami y Sunna. Chie conserva vacíos los campos opcionales de motivación, miedo y arco porque no existe todavía una Biblia equivalente.

El repertorio de Sunna fue ampliado con crecimiento emocional y curiosidad discreta sin convertirla en un personaje extrovertido. También existen follow-ups authored para interacciones Cami/Sunna y Sunna/Chie.

Las pruebas actuales protegen:

- drivers canónicos;
- claves únicas;
- selección determinista;
- variantes authored;
- brevedad/voz de Sunna;
- follow-ups entre personajes.

## Ciudad Animals

`WorldService` y sus modelos ya permiten registrar catálogo y estadísticas agregadas. La documentación del mundo todavía identifica como pendiente conectar las acciones reales de los bots a `WorldService.observe()`.

Por tanto, no se considera todavía un mundo vivo plenamente integrado.

## CI

No se declara CI verde para estos cambios. La ejecución posterior completa todavía debe observarse y terminar satisfactoriamente antes de afirmar que la cadena conjunta está validada.

## Próximos puntos de auditoría

1. Ejecutar/observar CI posterior a los cambios.
2. Verificar integración real de `WorldService.observe()` en acciones de los cuatro bots.
3. Ampliar interacciones sin convertirlas en frases aisladas sin contexto.
4. Convertir documentación de anime/maid en datos de dominio consultables.
5. Mantener la GUI detrás del avance del dominio.
