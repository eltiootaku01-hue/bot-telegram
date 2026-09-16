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

## Mundo y observación: integración verificada

La revisión anterior dejó una duda porque la búsqueda de código de GitHub no indexaba `WorldService`. La inspección directa del árbol y de los archivos actuales corrige ese diagnóstico.

`app/services/world.py` contiene `WorldService.observe()`, `register_catalog_entry()`, `user_summary()` e `insights()`. La implementación actualiza agregados de forma determinista y usa una inserción protegida por savepoint más reintento de `UPDATE` ante `IntegrityError` para el caso de dos procesos que descubren la misma clave por primera vez.

Más importante: `app/modules/chat/module.py` **sí consume realmente** `WorldService`. La ruta de chat:

```text
Telegram Message
  ↓
ChatModule.handle_text()
  ↓
CharacterIntentRouter
  ↓
CharacterDirector
  ↓
authored response
  ↓
message.answer()
  ↓
_observe_scene()
  ↓
WorldService.register_catalog_entry()
  ↓
WorldService.observe()
  ↓
SQLite / WorldUsageStat
```

La observación conserva tres dimensiones útiles: uso mundial de la escena, intención atribuida al bot que recibe la petición y uso de la escena dentro de la relación usuario-chat. Los follow-ups se atribuyen al `speaker` real de la escena, no automáticamente al bot que recibió el mensaje.

Se añadió una prueba de integración en `tests/test_chat_world_attribution.py` que ejecuta `ChatModule.handle_text()` con una entrada realista y verifica que la respuesta authored se emite y que la observación mundial, la intención de Cari y la atribución `user_chat` quedan persistidas.

Por tanto, el estado correcto ya no es “servicio no integrado”: es **integración real demostrada en el módulo de chat, con cobertura de persistencia**, aunque todavía no existe evidencia equivalente para todas las demás superficies de bot.

## Riesgos pendientes del mundo

- La integración demostrada está concentrada en `ChatModule`; no debe extrapolarse automáticamente a juegos, trivia, media, requests u otros módulos.
- `_seed_catalog()` usa un indicador en memoria (`_catalog_seeded`); si la base se sustituye o se recrea mientras el proceso continúa vivo, ese indicador podría quedar desincronizado con el catálogo persistente.
- El servicio guarda el texto authored como `label` del catálogo. Esto es funcional, pero debe revisarse si el catálogo evoluciona hacia metadatos de dominio más ricos y estables que no dependan de la redacción de una escena.
- `handle_text()` envía la respuesta de Telegram antes de persistir la observación. Si la persistencia falla, el usuario puede recibir el mensaje aunque la métrica no quede registrada. Para estadísticas de bajo riesgo esto puede ser aceptable, pero debe decidirse explícitamente antes de usar estas observaciones para invariantes de negocio.

## CI

`.github/workflows/ci.yml` ejecuta Ruff y Pytest sobre Ubuntu/Python 3.12 en pushes a `main`/`foundation/**` y pull requests. GitHub documenta que los workflows se definen en `.github/workflows` y que los jobs/steps constituyen la cadena ejecutable.

Para el commit `2b66324ac41f66006c7865e61f96318bc1fddde3`, la ejecución **Windows build** `35054934750` terminó correctamente: instalación, pruebas nativas, ejecutables, smoke test de BotManager, instalador, portable, checksums y artefactos finalizaron con éxito.

No se obtuvo un workflow run de la CI Ubuntu/Pytest asociado a ese commit mediante las consultas disponibles. El estado combinado tampoco devuelve checks. Por ello **no se declara CI global verde**. Esto es una distinción importante: Windows build verde no equivale a Ruff + Pytest verdes.

La CI actual limita `permissions` a `contents: read`. Las acciones están fijadas por tags mayores (`@v5`, `@v6`), no por SHA; esa decisión queda como endurecimiento posterior, no como requisito para la integración de mundo actual.

## Comparación arquitectónica

La estructura del proyecto mantiene una separación razonable entre routers, módulos, servicios, personajes, persistencia y Brain opcional. La documentación oficial de aiogram respalda el uso de routers y dependency injection para desacoplar dependencias; el proyecto ya sigue esa dirección mediante módulos/routers propios.

La documentación oficial de SQLAlchemy confirma que `AsyncSession` es mutable y no debe compartirse entre tareas concurrentes; por ello la estrategia de sesiones cortas por operación debe conservarse. La implementación de `WorldService` recibe una sesión explícita y `ChatModule` abre una sesión por operación, evitando convertir una sesión global en estado compartido.

En la comparación externa se observaron patrones repetidos de separación entre entrada Telegram, lógica de dominio, persistencia y pruebas. Algunos proyectos de bots de juegos también mantienen el motor de reglas independiente del adaptador Telegram. Esa referencia refuerza la decisión de mantener personajes, mundo y reglas locales fuera del Brain y del transporte Telegram.

## Estado de auditoría

No se modifican los porcentajes globales anteriores sin evidencia suficiente. La evidencia nueva sí cambia el diagnóstico cualitativo del subsistema mundo: **la capa de servicio existe y tiene un consumidor real en chat; ahora falta ampliar la misma disciplina de integración y pruebas a las demás superficies de dominio**.

## Próximos puntos de auditoría

1. Ejecutar/observar CI posterior al nuevo test de integración y corregir cualquier fallo antes de ampliar funcionalidad.
2. Auditar otros módulos para localizar acciones de dominio que todavía no generan observaciones de mundo donde deberían hacerlo.
3. Revisar la semántica de `_seed_catalog()` y separar catálogo de metadatos de la redacción de diálogos si el dominio lo requiere.
4. Ampliar interacciones entre personajes mediante contexto/relación/rutina, no sólo acumulando frases.
5. Convertir documentación de anime/maid en datos de dominio consultables.
6. Mantener la GUI detrás del avance del dominio.
