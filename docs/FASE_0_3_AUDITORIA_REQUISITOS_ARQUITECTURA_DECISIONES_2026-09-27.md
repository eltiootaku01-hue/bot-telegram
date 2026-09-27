# FASE 0.3 — AUDITORÍA DE REQUISITOS, ARQUITECTURA Y DECISIONES

Repositorio: eltiootaku01-hue/bot-telegram
Rama: main
Fecha: 2026-09-27
HEAD auditado base: 4f2141759483a3f8f3e3610e3b3cad8d1ec2f314
HEAD de continuación FASE A: 1743b29c9c5fc66d2dfb08bd989bb84de8060efa
Naturaleza: auditoría + diseño. No implementación funcional.

## Regla de lectura

Este documento continúa FASE 0.1 y FASE 0.2. La existencia de un archivo, clase, función, tabla, ruta, mock o test no prueba integración.

Estados: VERIFICADO, PARCIAL, FALTANTE, MOCK/FALLBACK, LEGACY, NO VERIFICADO y DECISIÓN PENDIENTE DEL USUARIO.

No se ejecutaron servicios externos de Telegram, Discord, Google o chats web; tampoco se realizó una prueba productiva completa de Chromium. Los tests existentes demuestran solo los contratos que cubren.

## 1. Resumen ejecutivo

El repositorio contiene actualmente dos caminos de generación de lenguaje que no están unificados:

1. LocalWorkflow -> ProviderManager -> providers API/Ollama.
2. GUI/Tavern -> WebChatQueueManager -> QWebEngineView -> chat web.

El requisito confirmado para esta fase establece que el chat web en la PC debe ser el mecanismo conversacional principal de los personajes roleables. Por tanto, el camino actual de ProviderManager sigue siendo real, pero no coincide todavía con el objetivo arquitectónico confirmado.

La ruta más cercana al objetivo es Tavern GUI: WaitressSessionManager construye un prompt de roleplay y lo entrega a WebChatQueueManager. En cambio, el runtime Telegram moderno no demuestra la inyección de WaitressSessionManager.

También existen huecos importantes: no hay sistema persistente de espera por regreso de mesera; no se demuestra RESTING -> AVAILABLE automático; el selector TCG usa MOCK_INVENTORY; el combate tiene rental fallback; MatchHistory existe pero no se escribe en finish_match; no se demostró una identidad global; no existe un modelo estructurado completo de emociones/relaciones; la interfaz TCG web no coincide con el contrato actual del endpoint.

## 2. Tabla completa de hallazgos

| Hallazgo | Evidencia / ruta | Estado | Requisito confirmado | Tipo | Próxima investigación | Implementar ahora | Decisión usuario |
|---|---|---|---|---|---|---|---|
| Telegram moderno -> Tavern | __main__ crea TelegramProjectsAdapter sin WaitressSessionManager; adapter acepta manager opcional | PARCIAL | Sí | Integración | Trazar un único entry point y prueba E2E | No | Detalles de integración: sí |
| Tavern GUI -> WebQueue | gui/app.py _wire_backend() crea WebChatQueueManager y build_tavern_manager() | VERIFICADO | Sí | Integración | Ejecutar GUI -> WebQueue -> respuesta | No | No |
| Session Tavern persistente | active_sessions, waitresses, users, user_inventory en memory/schema.sql; _start_session() | VERIFICADO | Sí | Funcionalidad real | E2E real | No | No |
| AVAILABLE -> BUSY | _on_ticket_started() / _set_waitress_state() | VERIFICADO | Sí | Estado | Ejecución real | No | No |
| BUSY -> RESTING | _mark_resting_if_idle() actualiza is_busy=0,is_resting=1 | VERIFICADO | Sí | Estado | Temporizadores/reinicio | No | No |
| RESTING -> AVAILABLE | No se encontró transición automática equivalente | FALTANTE | Pendiente de confirmar como regla final | Diseño | Semántica del retorno y evento | No | Sí |
| Usuario espera regreso de mesera | No hay tabla/servicio de waiting/followup identificado | FALTANTE | Sí como caso de uso | Diseño | Contrato de intención y consumo | No | Sí |
| TelegramOutbox moderno | create_pending, followups, drain, DELIVERED/FAILED | VERIFICADO | Sí como infraestructura | Integración real | Reinicio real | No | No |
| Tavern -> TelegramOutbox | Tavern usa message_sender directo; no Outbox | FALTANTE | No está confirmado que toda salida deba unificarse | Diseño | Comparar garantías de entrega | No | Sí |
| Prompt roleplay | prompt_builder.py: WaitressPromptProfile + build_chat_messages(); manager lo entrega al WebQueue | VERIFICADO | Sí | Feature real | Continuidad y contexto | No | Sí para contrato final |
| Prompt analysis | MamaMiaSupervisor local + opcional Gemini audit; devuelve SupervisorDirective | PARCIAL | Sí | Diseño | Contrato estructurado mínimo | No | Sí |
| Análisis con intención/severidad/emociones | Actualmente no produce ese esquema estructurado | FALTANTE | Concepto confirmado, esquema no cerrado | Diseño | Definir campos | No | Sí |
| Autoridad del modelo | Cambios de DB/economía se ejecutan desde código, no desde texto del modelo | VERIFICADO parcial | Sí | Arquitectura | Probar todas las mutaciones futuras | No | No |
| Emociones | No hay entidad persistente dedicada; solo afinidad en WaifuRegistry | FALTANTE | Sí | Diseño | Modelo y reglas | No | Sí |
| Relaciones | No se encontró modelo de confianza/respeto/amistad/enojo/miedo/etc. | FALTANTE | Sí | Diseño | Modelo y reglas | No | Sí |
| Memoria | MemoryStore con aprobación, expiración, conflictos, provenance y FTS | VERIFICADO | Sí | Infraestructura | Medir crecimiento | No | No |
| Historial reciente | No se demostró un almacén dedicado para todos los mensajes con retención explícita | NO VERIFICADO | Sí como concepto de estudio | Diseño | Definir estado/memoria/historial | No | Sí |
| Afinidad | WaifuRegistry._waitress_affinity y tip_waitress() | PARCIAL | Sí | Sistema existente | Decidir source of truth | No | Sí |
| Identidad global | IDs separados: BOT-IA, Tavern telegram_id, TCG User.id, wallet.user_id, Discord | FALTANTE | Sí como objetivo de análisis | Diseño | Identidad canónica + mappings | No | Sí |
| Identidad de meseras | Listas diferentes en Tavern, TCG, GUI y Playwright | FALTANTE | Sí | Diseño | Catálogo único o dominios separados | No | Sí |
| TCG inventory -> deck | selector usa MOCK_INVENTORY; confirmación usa CardInstance real | PARCIAL + MOCK/FALLBACK | Sí | Integración | Mapear inventario real al selector | No | Detalles UI: sí |
| Rental deck | get_or_create_rental_deck() fabrica Waifu Principiante/Escudo de Madera/Poción de Taberna | MOCK/FALLBACK | No confirmado como producto | Diseño | Confirmar si rental es regla final | No | Sí |
| MatchHistory | Modelo existe; finish_match() no crea MatchHistory | FALTANTE | Sí si historial es requisito final | Función faltante | Revisar consumidores/tests adicionales | No | No para existencia; sí para detalles |
| Recompensa duelo TCG | No hay recompensa conectada a finish_match() | FALTANTE / NO VERIFICADO | Importe/regla no confirmados | Diseño | Confirmar moneda y recompensa | No | Sí |
| Economía Tavern | chocolates_balance en bot_ia_memory.sqlite3 | VERIFICADO | Sí | Sistema real | Unificación solo si se decide | No | Sí |
| Economía BOT-IA | wallet.points en bot_ia_economy.sqlite3, WAL | VERIFICADO | Sí | Sistema real | Medición y scope | No | No |
| Economía TCG | User.coins existe; consumidor real no demostrado | NO VERIFICADO | No | Diseño/posible legacy | Buscar consumidores | No | Sí |
| Economías compartidas | No se demostró fuente única entre Tavern/BOT-IA/TCG | NO VERIFICADO | No confirmado | Diseño | Confirmar intención | No | Sí |
| ProviderManager | LocalWorkflow._run_local_provider(); runtime/config declaran OpenAI como normal | VERIFICADO actual / conflicto objetivo | No como cerebro principal de personajes | Arquitectura | Definir papel futuro | No | Sí |
| Web Chat local | web_chat.py sirve HTML que llama /v1/query -> WebApi -> BotApplication | VERIFICADO | Sí como UI web local, no como chat web externo de personajes | Arquitectura | Separar ambos conceptos | No | No |
| GUI Web persona | _send_web_persona() manda mensaje raw al WebQueue | VERIFICADO | Sí | Integración | Unificar con prompt roleplay | No | Sí |
| Contexto de personaje en Web persona | _send_web_persona() no usa build_chat_messages() | PARCIAL | Sí | Integración | Pipeline único de persona | No | Sí |
| Mama Mia en runtime Tavern | build_tavern_manager() no inyecta mama_mia_supervisor | FALTANTE | Sí si supervisión es parte del flujo final | Integración | Definir análisis | No | Sí |
| WebQueue Qt | services/web_queue.py conectado a GUI; persistent profile/cookies | VERIFICADO | Sí | Infraestructura | E2E y RAM | No | No |
| WebQueue Playwright | core/web_queue.py tiene seis pages y Chromium | VERIFICADO como componente | Sí | Compatibilidad | Verificar si debe sobrevivir | No | Sí |
| WebQueue Playwright en runtime normal | GUI entra a _async_main() solo con Python <3.14; pyproject requiere >=3.14 | LEGACY/PARCIAL | No como camino principal | Legacy | Decidir destino | No | Sí |
| Una página por personaje | Qt crea un QWebEngineView; select_bot cambia ID pero no demuestra recreación | NO VERIFICADO | Sí estudiar | Runtime | Confirmar páginas/perfiles reales | No | Sí |
| Sesiones web persistentes | QWebEngineProfile persistent storage + cookies | VERIFICADO | Sí | Arquitectura | Medir continuidad y recuperación | No | Sí para lifecycle |
| Tiempos roleplay | No se encontró delay por personaje/contexto | FALTANTE | Sí | Diseño | Definir reglas de timing | No | Sí |
| Indicador leyendo | No se encontró feature específica | NO VERIFICADO | No obligatorio | UX | Evaluar solo si aporta | No | Sí |
| TCG web | public/inventory.html existe | VERIFICADO como archivo | Sí si superficie TCG sigue | UI | Validar contrato y serving | No | Sí |
| TCG web E2E | URL placeholder; shape JS no coincide con endpoint; imports de auth/db ausentes del árbol | FALTANTE | Sí si se quiere esta superficie | Integración | Decidir superficie oficial | No | Sí |
| Google Drive/Photos | No se encontraron integraciones | FALTANTE | Solo interés futuro | Diseño | Definir backup/export | No | Sí |
| Backup SQLite local | BackupService + SQLiteBackupManager, snapshots locales validados | VERIFICADO | Sí | Infraestructura | Restauración real | No | No |
| Backup externo | No existe transferencia cloud | NO VERIFICADO | Sí como posibilidad futura | Diseño | Provider/cifrado/retención | No | Sí |
| Ollama | OllamaProvider, keep_alive=0, qwen3:1.7b config/test | VERIFICADO técnico | Sí como auxiliar opcional | Infraestructura | Medir RAM/latencia/calidad | No | No |
| Ollama <=500MB | No existe medición real | NO VERIFICADO | Sí como objetivo orientativo | Medición | Benchmark real | No | Sí antes de fijar techo |

## 3. Arquitectura actual encontrada

```text
Telegram moderno / GUI / Web
            ↓
       BotApplication
            ↓
   LocalBrain + Router
            ↓
       LocalWorkflow
       ├─ Librarian
       ├─ ContextBuilder
       ├─ MemoryStore
       ├─ Agents / Rules
       ├─ EvidenceGate
       └─ ProviderManager
             ├─ OpenAI
             ├─ Groq
             ├─ OpenRouter
             ├─ Coze (disabled)
             └─ Ollama (disabled)

GUI Tavern
    ↓
WaitressSessionManager
    ↓
build_chat_messages()
    ↓
WebChatQueueManager
    ↓
QWebEngineView / chat web

TCG independiente
    ↓
python-telegram-bot / Discord bot
    ↓
SQLAlchemy
    ↓
bot_database.db
```

Conclusión: la arquitectura actual contiene piezas reutilizables, pero no existe todavía un único pipeline de personajes que use chat web como cerebro conversacional y BOT-IA como autoridad de dominio.

## 4. Arquitectura objetivo PROPUESTA

```text
Telegram / GUI / Web
        ↓
    BOT-IA CORE
 Identity / State / Rules
 Memory / Events / Economy
        ↓
 Character Engine
   ├─ ROLEPLAY PROMPT
   └─ ANALYSIS PROMPT
        ↓
      WebQueue
        ↓
 Browser / Chromium
        ↓
     Chat web
        ↓
    texto generado
        ↓
 BOT-IA valida/aplica
        ↓
 reglas / eventos / estado
        ↓
      Telegram
```

Esto es una propuesta, no una decisión implementada.

Principios propuestos:
- El chat web genera lenguaje.
- BOT-IA mantiene autoridad sobre economía, identidad, emociones, relaciones, inventarios y permisos.
- La salida textual del modelo no modifica directamente la base.
- SQLite activas permanecen locales.
- Backups externos son snapshots/exportaciones, no la base viva.
- Ollama es opcional y bajo demanda.
- No se mantiene un LLM local grande como proceso principal.

## 5. Prompts: respuesta vs análisis

### Prompt de respuesta

Existe y está conectado al camino Tavern GUI. __build_chat_messages()__ crea mensajes separados de system/user y añade identidad, rol, personalidad, contexto y directivas.

Estado: VERIFICADO estáticamente.

### Prompt de análisis

MamaMiaSupervisor ofrece una rama local determinista y una rama opcional de auditoría con Gemini. El contrato actual produce directivas, no un objeto estructurado de intención/severidad/emociones/consecuencia.

Estado: PARCIAL.

Decisión pendiente: definir el contrato mínimo de análisis antes de implementarlo.

## 6. Emociones, relaciones y memoria

El repositorio tiene afinidad por mesera en __WaifuRegistry__, pero no tiene un almacén estructurado completo para emoción y relación.

Propuesta conceptual, aún no aprobada:

```text
Estado actual: emoción/afinidad/estado de la mesera
Memoria resumida: hechos importantes y relación
Historial: mensajes/eventos recientes con retención limitada
```

Debe evitarse convertir cada interacción en memoria persistente sin una política de retención.

## 7. TCG

### Motor y persistencia

__Card__, __CardInstance__, __GroupDrop__, __ActiveMatch__ y __MatchHistory__ existen en SQLAlchemy.

### Inventory -> Deck

El selector no consume CardInstance reales; consume __MOCK_INVENTORY__. La confirmación posterior sí intenta escribir referencias reales y bloquear CardInstance.

Estado: PARCIAL + MOCK/FALLBACK.

### Rental

El motor puede completar slots faltantes con cartas sintéticas.

Estado: MOCK/FALLBACK; decisión pendiente sobre si es producto o compatibilidad.

### Historial y recompensas

MatchHistory existe, pero __finish_match()__ no demuestra el insert. No se encontró recompensa económica conectada al final del duelo. La regla de recompensa debe confirmarse antes de implementarse.

## 8. Economía

Se encontraron tres conceptos separados:

```text
Tavern          → chocolates_balance → bot_ia_memory.sqlite3
BOT-IA Café     → points             → bot_ia_economy.sqlite3
TCG             → coins              → bot_database.db
```

No se debe fusionarlos por intuición. El requisito de una identidad/economía global necesita una decisión explícita sobre si son monedas distintas o una sola.

## 9. Identidad

Identificadores encontrados:

- BOT-IA __user_id__.
- Tavern __telegram_id__.
- Memory/Session __user_id__.
- TCG __User.id__.
- TCG __User.discord_id__.
- Economy __wallet.user_id__.

No se demuestra una entidad común.

Identidad de meseras también está fragmentada: Tavern, TCG, GUI y Playwright mantienen listas distintas.

## 10. WebQueue, Chromium y continuidad

### services/web_queue.py

Es la implementación conectada al runtime Qt. Usa QWebEngineView, QWebEngineProfile, cookies persistentes, FIFO, MutationObserver, timeouts y circuit breaker.

### core/web_queue.py

Es una implementación Playwright que crea seis páginas por IDs de mesera. Su entrada GUI está condicionada a Python < 3.14, mientras el proyecto declara Python >= 3.14.

### Continuidad

La persistencia de perfiles está demostrada, pero no la recuperación completa de la conversación tras crash, cierre accidental, expiración o creación de una nueva conversación.

NO VERIFICADO.

### Número de páginas

No debe afirmarse que hay seis páginas activas en el runtime normal. El Qt path crea un QWebEngineView; el Playwright core crea seis en un camino condicionado.

## 11. RAM

No existe una medición actual suficiente para afirmar un consumo de 1.5 GB o 2.5 GB.

Riesgos:

- Chromium/QWebEngine.
- Playwright multisesión.
- Procesos separados de run_all.py.
- Ollama durante inferencia.
- pools/hilos permanentes de la GUI.

El objetivo 1.5/2.5 GB debe permanecer como objetivo de diseño hasta obtener mediciones reales.

No cerrar sesiones web solo por ahorrar RAM antes de medir el impacto sobre continuidad.

## 12. Tiempos de respuesta

No existe una política específica por personaje/contexto para retardos naturales. Los timers de sesión, descanso y auto-delete no son equivalentes a timing de roleplay.

Estado: FALTANTE como feature de roleplay.

Decisión pendiente: mínimo/máximo, longitud, complejidad, emoción e indicador de lectura.

## 13. Almacenamiento externo

Backup local ya implementado y validado estructuralmente. No se encontraron integraciones Google Drive/Photos.

Propuesta:

```text
SQLite activa local
      ↓
snapshot validado
      ↓
backup/export externo
```

No usar una SQLite activa dentro de una carpeta sincronizada como solución por defecto.

## 14. TCG Web

__public/inventory.html__ existe, pero tiene tres evidencias de ruptura:

1. API_BASE_URL apunta a __https://TU-SERVIDOR.com__.
2. El JS espera __item.card.rarity__ mientras el endpoint devuelve __rarity__ plano y otros campos planos.
3. El router importa __api.dependencies__ y __api.security.telegram_auth__, archivos que no aparecen en el árbol actual.

Estado: FALTANTE como flujo E2E.

## 15. Componentes que deberían permanecer locales — PROPUESTA

- identidad y mappings;
- estados de meseras y sesiones;
- emociones y relaciones;
- memoria controlada;
- economía;
- inventarios y TCG engine;
- CardInstance / ActiveMatch / MatchHistory;
- reglas y eventos;
- SQLite activas;
- biblioteca/canon;
- configuración;
- perfiles web necesarios para continuidad.

## 16. Componentes que podrían usar almacenamiento externo — PROPUESTA

- snapshots SQLite;
- backups históricos;
- imágenes archivadas;
- exportaciones;
- documentos fríos;
- artefactos no requeridos para ejecución activa.

## 17. Componentes que podrían ejecutarse bajo demanda — PROPUESTA

- Ollama;
- backups/restores;
- reindexación;
- investigación externa;
- tareas pesadas;
- archivado/exportación;
- recuperación de sesión web.

## 18. Decisiones pendientes del usuario

1. Confirmar chat web como cerebro conversacional principal de los personajes.
2. Definir contrato del Prompt de Análisis.
3. Definir fuente de verdad de emociones/relaciones.
4. Definir identidad global y mappings externos.
5. Definir catálogo único de meseras.
6. Confirmar si rental deck es producto o fallback.
7. Confirmar significado de TCG User.coins.
8. Confirmar si hay recompensa TCG y sus reglas.
9. Confirmar MatchHistory como requisito final.
10. Decidir si TelegramOutbox debe ser autoridad común de salida.
11. Decidir papel de ProviderManager después de separar la generación web de personajes.
12. Definir lifecycle de sesiones web: hot/warm/cold y recuperación.
13. Definir timing de roleplay.
14. Decidir si public/inventory.html seguirá siendo la superficie oficial del TCG.
15. Definir backup externo: proveedor, cifrado y retención.
16. Definir política de historial reciente.

## 19. Orden recomendado de futuras fases — PROPUESTA

FASE 1: contratos de identidad, meseras, estados y eventos.
FASE 2: Tavern Telegram E2E real.
FASE 3: Character Engine: roleplay + analysis + reglas.
FASE 4: emociones y relaciones.
FASE 5: sistema de espera y regreso.
FASE 6: TCG inventory -> deck real.
FASE 7: TCG duelo completo: deck, history, rewards, unlock.
FASE 8: TCG Web.
FASE 9: medición de RAM/CPU/Chromium/WebQueue/Ollama.
FASE 10: backups externos.

## 20. Registro de cambios de esta fase

Solo se creó/actualizó documentación de auditoría. No se modificó código funcional.

Archivos de código modificados: NINGUNO.
Migraciones: NINGUNA.
Dependencias nuevas: NINGUNA.
Modelos Ollama instalados: NINGUNO.
Servicios externos ejecutados: NINGUNO.
Prueba E2E productiva: NO REALIZADA.

Este documento es el registro persistente de la FASE 0.3 para que futuras IA no dependan de la memoria de conversación.

Conclusión: existe una base sólida de componentes locales, Tavern, WebQueue, memoria, economía y TCG, pero no debe marcarse como terminado ningún flujo de personaje, identidad, emoción, retorno de mesera, deck real o TCG web hasta cerrar los huecos y ejecutar verificaciones reales.

## 21. FASE A — Continuación de auditoría contra main actual (2026-09-27)

### 21.1 Estado de verificación CI

El commit `1743b29c9c5fc66d2dfb08bd989bb84de8060efa` disparó CI run `36300571303` / run #3090.

Resultado observado en GitHub Actions:
- Ubuntu: FAILED en `Compile source and tests`.
- Windows: FAILED en `Compile source and tests`.
- `pytest` NO llegó a ejecutarse en ninguno de los dos runners.

Errores reportados por compilación:
- `src/bot/handlers/drop_handler.py:37` — f-string sin terminar.
- `src/bot/handlers/support_handler.py:39` — string sin terminar.
- `src/discord/bot.py:110` — f-string sin terminar.

Esto es un **BLOQUEO ACTUAL DE CI**, no una conclusión sobre el funcionamiento de las funciones auditadas. No se corrigieron estos archivos durante la auditoría.

### 21.2 Descubrimiento de LEGACY relevante

El árbol `build/lib/` contiene una arquitectura anterior mucho más amplia que la superficie actual de `src/`. No debe confundirse con el runtime actual.

Dentro de ese árbol aparecen, entre otros:
- `build/lib/app/core/jobs.py`: cola durable con deduplicación, recuperación de jobs en estado `processing`, heartbeat y backoff.
- `build/lib/app/modules/trivia/module.py`: trivia de comunidad, scheduler periódico y publicación a Telegram.
- `build/lib/app/game/trivia.py`: preguntas de anime y validación de respuesta, pero con solo cinco preguntas hardcodeadas.
- `build/lib/app/db/trivia_models.py`: `TriviaRound` y `TriviaAttempt`.
- `build/lib/app/modules/cami_media/publisher.py`: publicación durable de `MediaAsset` y pedidos mediante jobs.
- `build/lib/app/modules/cami_media/module.py`: ingestión, catalogación, etiquetado, programación y recuperación de publicaciones.
- `build/lib/app/services/forum_topics.py`: catálogo de topics Telegram incluyendo `noticias`, `memes`, `anime`, `trivia`, `pedidos`, etc.
- `build/lib/app/core/social_runtime.py`, `social_wake.py`, `social_turn.py`, `social_activity.py`: runtime de actividad social programada, con gate de conversación humana y lease exclusivo por chat/ventana.
- `build/lib/app/modules/cafe/module.py` y `build/lib/app/services/cafe_events.py`: eventos diarios y recomendaciones de Café.
- `build/lib/app/modules/media/module.py` y servicios de catálogo/media: biblioteca de material y captura controlada.

El `build/lib/app/core/bot_composition.py` de ese árbol registraba explícitamente módulos de trivia, Cami media/publisher, comunidad, juegos, moderación, social runtime y world runtime.

Clasificación:
- **LEGACY / REFERENCIA ARQUITECTÓNICA**.
- No existe evidencia de que `build/lib` sea el entry point actual de `main`.
- CI actual compila `src`, no `build/lib`.
- El hecho de que estas piezas estén completas dentro de `build/lib` no demuestra que estén operativas en el sistema actual.
- No se eliminan ni se migran automáticamente por esta auditoría.

### 21.3 Web Chat compartido

`src/services/web_queue.py` es la infraestructura actual conectada a la GUI:
- `WebChatQueueManager(QObject)`.
- FIFO de tickets.
- lock global `_WEB_MESA_UNICA` para el ciclo completo del ticket.
- `QWebEngineView` + `QWebEngineProfile`.
- cookies/storage persistentes.
- MutationObserver, timeout, circuit breaker y estados de ticket.

Esto demuestra una **cola WebChat compartida dentro del runtime Qt**, pero no una infraestructura común ya conectada a todos los servicios del Café.

`src/gui/task_orchestrator.py` sí tiene `Priority.HIGH/MEDIUM/LOW` y `asyncio.PriorityQueue`, pero su integración corresponde al camino Playwright/async de compatibilidad. El `main()` actual usa `_async_main()` solo si Python < 3.14; con Python 3.14 entra en `_qt_main()`. Por ello no debe declararse como la política global actual del WebChat.

### 21.4 Telegram

La superficie Telegram actual sí contiene:
- routing por `(chat_id, message_thread_id)`;
- moderación textual;
- comentarios;
- economía/Pity/afinidad;
- flujo de pedidos;
- soporte opcional de Tavern;
- Outbox durable.

Sin embargo:
- `_run_telegram()` no demuestra la inyección de `WaitressSessionManager` en el runtime moderno;
- la mesa Tavern sigue siendo 1 usuario + 1 mesera, no una mesa grupal;
- `handle_photo_update()` procesa fotos para entregas de pedidos, no un sistema genérico de Aportes;
- `TelegramOutboxStore` es real para el poller moderno, pero Tavern envía notificaciones mediante `message_sender` directo.

Estado por requisito:
- **Telegram core: CONECTADO/PARCIAL**.
- **Tavern Telegram: PARCIAL / NO VERIFICADO E2E**.
- **Aportes Telegram: FALTANTE como flujo de dominio**.
- **Publicación automática: NO VERIFICADA en la superficie actual**.

### 21.5 Discord

Se mantienen dos superficies distintas:
1. `src/discord/bot.py`: bot TCG con slash commands y persistencia propia.
2. `src/bot_ia/interfaces/discord_community.py` + `discord_moderation.py`: contratos de bienvenida, BurstGate, strikes, permisos y moderación.

No se demuestra que `src/discord/bot.py` consuma la infraestructura de Café/World/Social/Publications.

Estado:
- **Discord TCG: EXISTE / PARCIAL / NO VERIFICADO E2E**, además bloqueado actualmente por el error de sintaxis de `src/discord/bot.py`.
- **Discord Café: PARCIAL / NO VERIFICADO como runtime unido**.
- No se debe afirmar una arquitectura Telegram/Discord común ya operativa.

### 21.6 Mesas de charla

La implementación actual de `WaitressSessionManager` modela:
`telegram_id -> waitress_id -> active_sessions`.

Tiene:
- sesión estándar de 3 minutos;
- favorita de 5 minutos;
- exclusión de una sesión activa por usuario;
- exclusión de una sesión activa por mesera;
- timer de expiración;
- estado busy/resting;
- integración con WebQueue;
- cuenta de chocolates de Tavern.

No tiene:
- `group/server`;
- `channel/topic`;
- anfitrión;
- invitados;
- espectadores;
- invitaciones;
- cuenta de mesa;
- contribuciones a cuenta;
- límite de dos modificaciones;
- estados `CLOSING/CLEANING/AVAILABLE`.

Por tanto, la **Mesa de Charla grupal especificada NO EXISTE actualmente**.

Además, hay una inconsistencia que debe tratarse como bug de diseño/implementación pendiente:
- `expire_session()` y `_mark_resting_if_idle()` pueden dejar `is_resting=1`;
- no se encontró una transición automática equivalente a `RESTING -> AVAILABLE`;
- `_start_session()` tampoco rechaza explícitamente `is_resting=1`.

No se corrigió durante la auditoría.

### 21.7 Cuenta de mesa

No se encontró una cuenta estructurada de Mesa de Charla en la base actual de Tavern.

No existe evidencia de:
- subtotal fijo de mesa;
- consumos;
- aportes parciales;
- responsable de pago;
- balance final;
- máximo de dos modificaciones.

Estado: **FALTANTE**.

No debe reutilizarse `points` como transferencia libre: el requisito de contribuciones exige representar un pago parcial contra la cuenta de la mesa.

### 21.8 Trivia Anime

En `src/` actual no se encontró un módulo de Anime Trivia equivalente al requisito de dataset externo local.

Sí existe `src/gui/mini_games.py`, pero contiene PPT, 21 y UNO locales; no es trivia anime.

En `build/lib/` existe un sistema legacy de trivia:
- publicación comunitaria;
- scheduler;
- botones;
- validación en `TriviaService.answer()`;
- persistencia de `TriviaRound` / `TriviaAttempt`.

Pero `QUESTIONS` está hardcodeado con cinco preguntas.

Conclusión:
- **Trivia actual en src: FALTANTE**.
- **Trivia legacy build: LEGACY / REUTILIZABLE CON MIGRACIÓN, NO OPERATIVA ACTUAL**.
- El diseño solicitado de `1..1000` IDs en archivo de datos aún no existe.

### 21.9 Espacios Telegram / Discord

Telegram dispone de routing exacto por topic:
`TelegramRoomRouter.resolve(chat_id, message_thread_id)`.

`group_setup.py` mantiene un catálogo de rooms y `REPOST_FEEDS`.

El legacy `ForumTopicService` agrega un catálogo más amplio de topics, pero pertenece a `build/lib`.

Discord tiene canales configurables por nombre/propósito en `DiscordGroupSetup`, pero no se demuestra una capa común equivalente al router de Telegram que además resuelva `purpose` de forma uniforme.

Conclusión:
- **Telegram topics: CONECTADO/PARCIAL**.
- **Discord channels: CONECTADO en setup/gestión, no probado E2E para contenido**.
- **modelo común platform + group/server + channel/topic + purpose + permissions: PROPUESTO, no implementado**.

### 21.10 Publicación automática

En `src/` actual:
- `social_publish.py` construye una publicación y abre un draft de X;
- no publica automáticamente.
- `group_setup.py` registra `REPOST_FEEDS`, pero no se encontró un scraper/RSS/API consumer que las procese y publique.

En `build/lib/`:
- sí existe `CamiMediaPublisher` con jobs persistentes y publicación Telegram de `MediaAsset`;
- esa publicación se refiere a material ingerido/catalogado y pedidos, no demuestra un pipeline moderno de RSS/noticias/memes desde `REPOST_FEEDS`.

Conclusión:
- **publisher actual Café: FALTANTE/PARCIAL**.
- **publisher legacy Cami: EXISTE dentro LEGACY**.
- **repost automático desde fuentes configuradas: NO VERIFICADO / no conectado en src actual**.

### 21.11 Noticias, imágenes y AniNoticias

No existen en el árbol actual los datasets/carpets esperados `data/trivia`, `data/news` o `data/images`.

No se encontró un pipeline actual que:
1. consulte noticias;
2. preserve fuente;
3. resuma;
4. seleccione imagen web;
5. cachee la imagen;
6. publique en un topic configurado.

El sistema legacy de anime/media sí mantiene referencias y catalogación de material, pero no constituye por sí mismo AniNoticias actual.

Estado:
- **Noticias automáticas: FALTANTE**.
- **Imagen web identificable + caché: FALTANTE**.
- **Fuente original visible en publicación: REQUISITO, no demostrado en src actual**.

### 21.12 Anime del día / aniversarios / memes

No se encontró en `src/` un scheduler/publisher actual para:
- anime del día;
- aniversario `hace X años`;
- meme del día.

`TeaTimeScheduler` y los juegos locales no equivalen a un publisher de contenido.

El legacy tiene eventos/recomendaciones y social runtime, pero esto no se demuestra como el runtime actual.

Estado: **NO IMPLEMENTADO / LEGACY PARCIAL**.

### 21.13 Aportes y moderación

La moderación actual:
- sí existe para texto/comandos;
- en Telegram se ejecuta antes de comandos;
- puede devolver `allow/delete_redirect/delete_warn/ban`.

Sin embargo, el flujo de foto actual se limita a adjuntos pendientes de pedidos.

No existe una cola de `Aporte` con:
- autor;
- timestamp;
- referencia;
- evaluación;
- decisión;
- evidencia de moderación;
- rechazo/aprobación persistente.

El sistema de quejas `ComplaintStore` es económico/administrativo y no es un moderador de aportes.

Estado:
- **Moderación textual: CONECTADA/PARCIAL**.
- **Aportes: FALTANTE**.
- **Moderación de imagen por IA: NO VERIFICADA**.

### 21.14 Publicaciones compartidas / fuentes externas

La configuración `REPOST_FEEDS` prueba que el concepto de fuentes externas existe.

Fuentes actuales encontradas en `group_setup.py`:
- `https://t.me/eltiootaku`;
- `https://t.me/yandere_nsfw`;
- `https://t.me/danbooru_sfw`;
- `https://t.me/danbooru_nsfw`.

Pero no se encontró en `src/`:
- consumidor;
- polling;
- RSS;
- scraper;
- filtro;
- scheduler;
- publisher conectado.

La configuración por sí sola queda en **EXISTE / NO CONECTADO**.

El legacy `CamiMediaPublisher` demuestra que hubo un diseño real de publicaciones durables, por lo que antes de crear otro publisher se debe evaluar una migración selectiva de ese diseño.

### 21.15 Sistema de contenido a puerta cerrada

El legacy `SocialRuntime` muestra un patrón útil ya existente:
`wake -> observe -> decide -> exclusive turn -> speak`.

También:
- bloquea actividad cuando hay conversación humana;
- usa wake durable por chat;
- usa un lease exclusivo por ventana.

Esto es muy cercano al concepto solicitado de:
`evento + tarea programada + actividad real`.

Pero el compositor legacy es **authored/determinista**, no WebChat; no demuestra el pipeline moderno de Character Engine.

Clasificación:
- **LEGACY reutilizable conceptualmente**.
- No migrar automáticamente sin revisar contratos y source of truth.

### 21.16 Prioridad del WebChat

Existe una prioridad HIGH/MEDIUM/LOW en `src/gui/task_orchestrator.py`, pero no es la política única demostrada de todo el sistema.

`src/services/web_queue.py` actualmente muestra exclusión mutua global y FIFO de tickets.

Por tanto:
- **FIFO + mutex: VERIFICADO en código actual**.
- **prioridad global de tareas Café: NO VERIFICADA**.
- **política definitiva: DECISIÓN PENDIENTE DEL USUARIO**.

No se debe copiar todavía HIGH/MEDIUM/LOW al WebChat principal solo por existir en el orquestador legado/compat.

### 21.17 Riesgo de contexto WebChat

Riesgos confirmados:
- la cola debe evitar mezclar tarea, personaje, usuario y mesa;
- el Qt path mantiene un `QWebEngineProfile` persistente;
- la GUI actual tiene un solo `QWebEngineView` visible en la tarjeta WebQueue;
- el `select_bot()` cambia la selección lógica pero no demuestra la creación de una página/perfil independiente por personaje.

No se debe afirmar “seis páginas” para el runtime Qt normal.

El Playwright legacy sí crea seis páginas, pero solo está alcanzable en el camino Python <3.14.

Estado de continuidad crash/restart/reconstrucción de conversación: **NO VERIFICADO E2E**.

### 21.18 Riesgo de RAM

No existe una medición real reciente que valide el objetivo de 1.5 GB o el techo operacional de ~2.5 GB.

Riesgos concretos:
- QWebEngine/Chromium;
- Playwright multisesión en legacy;
- múltiples procesos TCG de `run_all.py`;
- PySide6;
- Ollama bajo demanda.

La optimización debe basarse en medición, no en cerrar sesiones por intuición.

### 21.19 Riesgo de crecimiento de datos

Superficies con crecimiento potencial:
- `MemoryStore` y FTS;
- `active_sessions` y estado de sesiones;
- outbox/followups;
- economía transaccional;
- `bot_database.db` TCG;
- assets/media si se migra el legacy;
- futuros attempts de trivia;
- logs/eventos sociales si se migran.

No existe aún un contrato global de retención/archivado para todo el Café.

### 21.20 Mapa de reutilización

| Requisito | Existe | Conectado | Prueba | Reutilización recomendada |
|---|---|---|---|---|
| WebChat compartido | Sí | GUI Qt | tests de contrato; E2E no | Reutilizar `src/services/web_queue.py` |
| Mutex de Mesa Única WebChat | Sí | Sí dentro del queue | estática | Reutilizar |
| Prompt roleplay | Sí | Tavern GUI | estática | Reutilizar `prompt_builder.py` |
| Sesiones Tavern | Sí | GUI | tests de Tavern + estática | Reutilizar `WaitressSessionManager` como base 1:1 |
| Mesa grupal | No | No | No | Extender, no crear segundo sistema |
| Cuenta estructurada | No | No | No | Nuevo agregado al dominio de mesa |
| Room routing Telegram | Sí | Sí | tests existentes | Reutilizar |
| Discord setup | Sí | parcial | no E2E | Reutilizar contratos, unir runtime posteriormente |
| Moderación textual | Sí | Telegram | tests/estática | Reutilizar |
| Aportes | No | No | No | Nuevo dominio de aportes |
| REPOST_FEEDS | Sí | No consumer | No | Reutilizar config, crear solo consumer tras decidir diseño |
| Publisher durable Cami | Sí en build | Legacy | No runtime actual | Evaluar migración selectiva; no duplicar |
| Trivia | Sí en build | Legacy | tests legacy no activos en src | Migrar concepto; datos deben salir de Python |
| Social wake/turn | Sí en build | Legacy | no runtime actual | Evaluar como base del scheduler |
| Cami media library | Sí en build | Legacy | no runtime actual | Evaluar como base de media/assets |
| Anime catalog | Sí en build | Legacy | no runtime actual | Evaluar como fuente factual |
| X publisher | Sí | solo draft | no E2E | No sirve como publisher Café sin ampliar contrato |
| Economía | Sí, fragmentada | parcial | unit tests | No fusionar sin decisión |
| TCG engine | Sí | Telegram/Discord propios | parcial | Mantener separado hasta cerrar autoridad |
| TCG Web | Sí como HTML | roto/no E2E | no | Revalidar contrato antes de tocar UI |

### 21.21 Sistemas duplicados o paralelos

Se identifican al menos estas parejas/superficies que no deben fusionarse automáticamente:
- `src/services/web_queue.py` vs `src/bot_ia/core/web_queue.py`.
- `src/gui/task_orchestrator.py` vs cola Qt actual.
- Tavern `chocolates_balance` vs Café `wallet.points` vs TCG `User.coins`.
- Telegram Tavern waitresses vs GUI/Playwright/TCG maid catalogs.
- Café Telegram modern vs TCG Telegram.
- Café/Discord community contracts vs TCG Discord bot.
- `build/lib/app/*` vs `src/*`.

### 21.22 Propuesta de arquitectura final

**PROPUESTA**, no implementada:

```
Telegram / Discord / GUI
          ↓
      Event Router
          ↓
      BOT-IA Core
   ┌──────┼─────────┐
 Identity State   Rules
   │       │         │
 Memory  Economy  Permissions
   │       │         │
   └──────┴──── Events
              ↓
       Café Services
   ┌─────────┼──────────┐
 Tables    Trivia    Publishers
   │         │           │
   └─────────┼───────────┘
             ↓
        Task Scheduler
             ↓
       Shared WebQueue
             ↓
 Persistent browser/session
             ↓
         Web Chat
             ↓
     text / proposal / summary
             ↓
         BOT-IA validates
             ↓
    platform adapter publishes
```

Reglas arquitectónicas:
- las tareas locales no pasan por WebChat;
- solo tareas que necesitan lenguaje/modelo usan la cola;
- economía/estado/reglas son deterministas y locales;
- las publicaciones automáticas son disparadas por scheduler/eventos, no por comandos arbitrarios del usuario;
- cada tarea WebChat debe transportar explícitamente tipo de contexto y una clave de sesión aislada.

### 21.23 Decisiones pendientes actualizadas

Antes de implementar Mesa/Publisher/Trivia, quedan pendientes:
1. source of truth de identidad de usuario entre Telegram, Discord, Tavern, Café y TCG;
2. catálogo oficial de meseras y aliases;
3. si `chocolates`, `points` y `coins` son monedas distintas;
4. regla exacta de precio de Mesa compartida y cómo se calcula consumo;
5. significado de las 2 modificaciones de cuenta;
6. política de espectadores y reacciones por plataforma;
7. duración de CLEANING dentro del rango 5–10 min y reglas de busy/resting;
8. contrato de trivia y tamaño real del dataset;
9. fuentes externas autorizadas para noticias/reposts y sus términos de uso;
10. fuente de imágenes, caché, retención y licencias;
11. política de moderación de Aportes e intervención humana;
12. si el publisher legacy Cami es base a migrar;
13. prioridad global WebChat;
14. lifecycle hot/warm/cold de sesiones;
15. definición de un task context ID que aisle personaje/usuario/mesa;
16. superficie TCG Web oficial y contrato API;
17. límites de retención de memoria, outbox, assets y eventos.

### 21.24 Resultado de FASE A

La auditoría actual **NO autoriza todavía una implementación grande**.

La reutilización prioritaria queda:
- **WebQueue Qt actual** para infraestructura compartida;
- **WaitressSessionManager** como base de sesiones 1:1;
- **TelegramRoomRouter** para routing exacto;
- **moderación existente** para la capa textual;
- **configuración REPOST_FEEDS** como inventario de fuentes, sin asumir consumer;
- **legacy Cami publisher / JobQueue / Trivia / SocialRuntime / AnimeCatalog** como material de migración controlada, no como runtime activo.

Bloqueadores actuales:
- CI rojo por tres SyntaxError en `src/`;
- Tavern Telegram no inyectado en runtime moderno;
- ausencia de Mesa grupal;
- ausencia de cuenta de mesa;
- absence de Trivia dataset 1..1000 en `src/`;
- ausencia de pipeline de noticias/imágenes/reposts en `src/`;
- falta de Aportes con moderación persistente;
- duplicidad de economías e identidades;
- continuidad WebChat y RAM aún no verificadas mediante ejecución real.

No se modificó código funcional durante esta FASE A.
