# Auditoría incremental — 2026-09-16

## Alcance

Revisión del runtime social, personajes authored-only, persistencia y base de mundo sobre `main`, complementada con documentación oficial de aiogram, SQLAlchemy y GitHub Actions y una comparación arquitectónica externa.

## Hallazgo crítico: IA en el runtime social

`app/core/social_runtime.py` podía reemplazar la salida producida por `LocalSocialComposer` con una generación libre del Brain cuando la configuración de IA estaba activa.

Esto era una desviación de la arquitectura **código local primero, IA después**: el runtime social proactivo debe conservar el comportamiento authored-only aunque exista una configuración de IA.

## Corrección aplicada

El runtime social proactivo ya no importa ni invoca el Brain para sustituir el mensaje.

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

Además, se añadió una prueba de regresión que inspecciona el módulo y bloquea una reintroducción accidental de una ruta `Brain`/`.generate()` en este runtime.

La IA permanece disponible para funcionalidades explícitas y futura curaduría, pero no controla silenciosamente la personalidad cotidiana de los bots.

## Revisión de personajes

`CharacterProfile` contiene drivers canónicos para Cari, Cami y Sunna. Chie conserva vacíos los campos opcionales de motivación, miedo y arco porque todavía no existe una Biblia equivalente.

El repertorio de Sunna fue ampliado con crecimiento emocional y curiosidad discreta sin convertirla en un personaje extrovertido. También existen follow-ups authored para interacciones Cami/Sunna y Sunna/Chie.

Las pruebas actuales protegen:

- drivers canónicos;
- claves únicas;
- selección determinista;
- variantes authored;
- brevedad/voz de Sunna;
- follow-ups entre personajes;
- frontera authored-only del runtime social.

## Mundo y observación: corrección de auditoría

La revisión directa de `main` confirma que `app/db/world_models.py` define `WorldCatalogEntry` y `WorldUsageStat`, es decir, existe la base persistente para catálogo y estadísticas agregadas.

Sin embargo, en esta pasada no se localizó un `WorldService` verificable en el árbol actual ni un call-site verificable de `WorldService.observe()`. Por rigor, **no se debe afirmar que ese servicio ya esté integrado** hasta localizar código ejecutable y pruebas que demuestren el flujo.

Esto cambia el diagnóstico anterior: el mundo tiene modelos persistentes, pero la capa de servicio/observación sigue siendo un punto de auditoría pendiente.

## CI

`.github/workflows/ci.yml` ejecuta Ruff y Pytest sobre Ubuntu/Python 3.12 en pushes a `main`/`foundation/**` y pull requests. GitHub documenta que los workflows se definen en `.github/workflows` y que los jobs/steps constituyen la cadena ejecutable.

Para el commit actual de auditoría `47b6402f12b0af7efe2a4252cdbcc8b7252fc98e`, GitHub no devuelve workflow runs ni status checks mediante las consultas disponibles. Por ello **no se declara CI verde**.

La documentación oficial de GitHub también recomienda permisos mínimos y referencias de acciones versionadas; la CI actual ya limita `permissions` a `contents: read`, aunque las acciones están fijadas por tags mayores (`@v5`, `@v6`) y no por SHA.

## Comparación arquitectónica

La estructura del proyecto mantiene una separación razonable entre routers, módulos, servicios, personajes, persistencia y Brain opcional. La documentación oficial de aiogram respalda el uso de routers anidados y dependency injection para desacoplar dependencias; el proyecto ya sigue esa dirección mediante módulos/routers propios.

La documentación oficial de SQLAlchemy confirma que `AsyncSession` es mutable y no debe compartirse entre tareas concurrentes; por ello la estrategia de sesiones cortas por operación debe conservarse y cualquier integración de observación mundial debe respetar esa frontera transaccional.

Un framework externo de bots revisado presenta una separación similar entre entrada, middleware, router, servicios y persistencia. La diferencia importante para este proyecto es que aquí la personalidad authored, el mundo y la persistencia son requisitos de dominio, no sólo infraestructura del bot.

## Estado de auditoría

No se modifican los porcentajes globales anteriores sin evidencia adicional. La nueva evidencia sí endurece el diagnóstico del subsistema mundo: modelos persistentes presentes, servicio/observación no demostrado.

## Próximos puntos de auditoría

1. Localizar o implementar de forma mínima y determinista el servicio de observación mundial, si el diseño actual realmente lo requiere.
2. Conectar primero una acción real y observable de bot a esa capa, con prueba persistente de extremo a extremo.
3. Ejecutar/observar CI posterior a los cambios y conservar evidencia de la ejecución.
4. Revisar si la CI necesita `workflow_dispatch`, concurrencia y/o fijación de acciones por SHA antes de considerarla madura para releases.
5. Ampliar interacciones entre personajes mediante contexto/relación/rutina, no sólo acumulando frases.
6. Convertir documentación de anime/maid en datos de dominio consultables.
7. Mantener la GUI detrás del avance del dominio.
