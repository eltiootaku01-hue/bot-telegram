# FASE 0.3 — AUDITORÍA DE REQUISITOS, ARQUITECTURA Y DECISIONES

Repositorio: eltiootaku01-hue/bot-telegram
Rama: main
Fecha: 2026-09-27
HEAD auditado: 4f2141759483a3f8f3e3610e3b3cad8d1ec2f314
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