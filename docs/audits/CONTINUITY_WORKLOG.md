# Continuidad del proyecto — registro permanente

Este archivo existe para evitar repetir auditorías, correcciones o funcionalidades ya terminadas.

## Estado de referencia

Fecha de esta nota: 2026-09-20
Rama: `main`
Último trabajo en esta sesión: flujo de respuesta humana de Tío Otaku, detector de vocativos y bandeja recuperable de aprobaciones Gacha.

## Progreso estimado

Estos porcentajes son estimaciones de alcance funcional, no una métrica de tests:

| Área | Estado |
|---|---:|
| Arquitectura/Core modular | 95% |
| Persistencia SQLite/SQLAlchemy/transactions | 97% |
| Seguridad y control de acceso Telegram | 96% |
| Runtime, workers, eventos y jobs durables | 95% |
| BotManager/Windows/instalador/portable | 97% |
| Módulos funcionales principales | 93% |
| WaifuMon/progresión/trivia/misterio | 91% |
| Personajes/canon/repertorio | 84% |
| Interacciones entre personajes | 82% |
| Ciudad Animals/world ledger/curador | 88% |
| IA secundaria y curaduría | 76% |
| Puente humano Tío Otaku | 90% |
| Producto global | 82% |

El 82% global no significa “82% del código escrito”. Representa cuánto de la visión funcional conocida está implementada y validada. La deuda principal restante está en expansión autoral de mundo/canon, profundidad de interacciones, más contenido y superficies de usuario; no en el esqueleto técnico.

## YA CORREGIDO — NO REPETIR COMO SI FUERA PENDIENTE

### Seguridad Telegram
- Allowlist central de grupos/supergrupos.
- Privado limitado al administrador configurado.
- Middleware fail-closed antes de sincronización de miembros.
- Callbacks privados autentican al usuario que pulsa, no al autor del mensaje del bot.
- Emisores automáticos vuelven a verificar la allowlist antes de enviar.
- Chie comprueba permisos administrativos reales antes de configurar.

### Persistencia y transacciones
- `Database.session()` mantiene la frontera de transacción del llamador.
- SQLite usa WAL, foreign keys, busy timeout y modo IMMEDIATE para escrituras.
- `MemberRepository.touch()` y `set_membership()` admiten transacción compuesta.
- `RequestService.create_paid()` ya no hace rollback/commit interno indebido.
- Los cargos con referencia son idempotentes.
- Worker/event/job lease recovery tiene fencing por lock/heartbeat.
- TaskSupervisor no pierde un worker nuevo cuando termina una tarea antigua.

### WaifuMon
- Encuentro activo único por comunidad.
- Intento único por usuario/encuentro.
- Captura atómica `active -> captured`.
- Recompensas protegidas por referencia idempotente.
- Evolución/fusión protegida contra carreras.
- Expiración no puede sobrescribir estados terminales.
- Encuentros vencidos se retiran antes de crear otro.
- Trivia vence limpiamente y no bloquea la siguiente ronda.
- Drop raro requiere aprobación humana de un solo uso.
- Bandeja privada \`/gacha_pendientes\` permite recuperar aprobaciones si se perdió la notificación inicial.
- Misterio diario: ronda única por día, intento único, ganador único y recompensa idempotente.

### Cami Publisher
- Claim atómico antes de cada envío para evitar doble publicación concurrente.
- Reconciliador de `delivery_unknown`.
- Programación local se convierte explícitamente a UTC antes de persistir.
- Grupo de publicación respeta allowlist actual.

### Personajes
- Respuestas normales son authored-only y deterministas.
- Brain no sustituye la conversación social proactiva.
- Director soporta selección ponderada e interacciones entre pares.
- Sunna tiene repertorio de afecto, curiosidad, pertenencia y crecimiento; no reducirla solo a silencio.
- Existen escenas authored de Cari/Cami/Sunna/Chie y follow-ups cruzados.
- Canon sensible no confirmado sigue fuera de los perfiles.

### Ciudad Animals
- Ledger agregado de observaciones sin necesidad de guardar texto libre.
- Catálogo persistente de lugares, roles, acciones, temas, relaciones y escenas.
- Seed idempotente.
- Insights hot/cold/unseen.
- Borrado de estadísticas personales.
- Curador diario opcional.
- Propuestas de mundo pasan por aprobación humana; la IA no modifica canon automáticamente.

### Tío Otaku
- Tío Otaku no es una quinta IA autónoma.
- Solicitudes explícitas se almacenan en inbox persistente.
- Captura idempotente por chat + mensaje.
- Bandeja privada `/tio_pendientes`.
- ACK/resolve con transición atómica.
- Respuesta humana explícita mediante `/tio_responder ID mensaje`.
- Si Telegram falla, la solicitud permanece pendiente.
- El detector exige vocativo explícito y evita capturar frases como “mi tío”.
- El sistema transporta la respuesta; no la inventa con LLM.

## VALIDACIÓN YA OBTENIDA

- CI reciente verde sobre `d4315ec5306345c3af5b7707eab9f2d0d39d183d`.
- Windows Build reciente verde sobre `d4315ec5306345c3af5b7707eab9f2d0d39d183d`.
- En la etapa inmediatamente anterior: CI #673 verde y Windows #314 verde sobre `c13da70731d18bdd71533e0e03982d58d58e2e91`.
- CI #1111 quedó verde sobre `a21d5eafc75e4f744240a8d4ca3638ef99ff8680` (código con fencing de Tío).
- Windows #741 está ejecutando el mismo SHA; ya superó checkout/setup y sigue en construcción de ejecutables. Todavía no debe etiquetarse como “Windows validado” hasta terminar.
- Las modificaciones posteriores a ese SHA que solo cambien documentación no alteran el binario, pero se mantienen fuera de la validación funcional hasta que su propio CI concluya.

## ÚLTIMO BLOQUE EJECUTADO — 2026-09-20

### Corrección de composición
- Cami dejó de montar `AdminModule`, porque ese módulo es el flujo de aprobación de drops raros de Sunna.
- Se añadió una regresión en `tests/test_bot_composition.py` para impedir que Cami vuelva a exponer la superficie Gacha de Sunna.
- Commit del cambio de código: `22804d3cd2fede673ca9299a6c3eec7f79608987`.
- CI #1114 y Windows #744 quedaron asociados a ese SHA; deben consultarse antes de llamar a este bloque validado.

### Auditoría funcional
- `/ranking` ya estaba implementado: no volver a tratarlo como pendiente.
- El catálogo de Ciudad Animals, el ledger, el curador, el puente de Tío Otaku y las interacciones authored ya existen en `main`.
- No repetir sus implementaciones salvo que una nueva auditoría encuentre un defecto concreto.

## ÚLTIMO BLOQUE IA — 2026-09-20

### Corrección local-first del Brain
- Cuando `LLM_PROVIDER` queda vacío, Ollama se intenta antes que Gemini/Groq/Cerebras/OpenRouter.
- Un proveedor explícito conserva prioridad sobre el fallback local.
- Esto mantiene la política de ahorro de API: la nube solo entra como fallback si existe una credencial/configuración válida.
- Commit de implementación: `ae4240083ca85458c00c4d7adbe033c1d3161b9d`.
- Regresión de prioridad: `1fe4c48538167d729263ff603b1cb232eb20c059`.
- El último SHA de código de este bloque es `1fe4c48538167d729263ff603b1cb232eb20c059`.

## ÚLTIMO BLOQUE DE CONTINUIDAD — 2026-09-20

- Cami ya no monta `AdminModule`; la aprobación Gacha pertenece exclusivamente a Sunna.
- El Brain es local-first cuando no existe proveedor explícito: Ollama precede a los backends externos configurados.
- El menú de Cari ahora expone `/tio_responder`, manteniendo el flujo de Tío Otaku completamente humano.
- El ranking, misterio diario, catálogo de Cami, curador de Ciudad Animals y repertorio de interacciones ya existían y no deben rehacerse sin encontrar un defecto concreto.
- Progreso global mantenido en **82%**: no se incrementa por simple endurecimiento técnico; el trabajo restante principal sigue siendo profundidad de producto, contenido autoral confirmado, más interacciones/superficies y cierre de versión.
- Código de esta tanda: `22804d3cd2fede673ca9299a6c3eec7f79608987` (composición), `1fe4c48538167d729263ff603b1cb232eb20c059` (Brain), `cb0c94a14fb4ddc3abe4c56a57717af066d6e07` (menú Tío).
- Nota de validación: cada modificación funcional debe esperar su CI y Windows correspondientes antes de considerarse cerrada.

## TRABAJO PENDIENTE / PRÓXIMOS OBJETIVOS

1. Profundizar canon y repertorio solamente usando material autoral confirmado; no inventar hechos narrativos.
2. Aumentar cobertura de interacciones dirigidas entre los cuatro personajes y su continuidad de conversación.
3. Completar más superficies funcionales de Cami/Chie/Cari sin depender de IA.
4. Mejorar la experiencia del operador humano de Tío Otaku (contexto, navegación de solicitudes y trazabilidad de respuestas) sin convertirlo en bot autónomo.
5. Continuar pruebas de concurrencia/recuperación en módulos que todavía no tengan regresiones específicas.
6. Mantener el empaquetado Windows y CI verde en cada bloque.
7. Crear una versión/release etiquetada solo cuando el contenido funcional de la siguiente etapa esté suficientemente cerrado.

## REGLA DE CONTINUIDAD

Antes de modificar algo:
- leer este archivo;
- no repetir ninguna corrección listada arriba;
- comprobar el SHA actual de `main`;
- revisar CI asociado al SHA;
- continuar desde el primer pendiente real.


## ÚLTIMO BLOQUE EJECUTADO — 2026-09-20 (continuación)

### Telemetría relacional de Ciudad Animals
- Se añadió `ChatModule._observe_interaction()` para registrar el uso de relaciones authored entre personajes en scopes world, user y user_chat.
- La observación ocurre después de enviar el follow-up authored, por lo que una interacción fallida no se convierte en una métrica falsa.
- Commit: `24cad87ca998eae9dc0fc0d10a12ef6266eaa891`.
- Regresión: `d226c348a0d515ab6bc7c231efb0373f0ce8aba9`.

### Cobertura de interacciones
- Se añadió una barrera CI que recorre las 12 parejas dirigidas entre Cari, Sunna, Cami y Chie.
- La prueba acepta cualquier `CharacterIntent` authored disponible y exige speaker + follow-up correctos.
- Esto evita borrar accidentalmente una relación existente sin detectarlo.
- Primera versión demasiado estricta provocó CI #1123; se corrigió sin relajar la garantía de cobertura.
- Commit de la barrera corregida: `c87685801f174a813035a3bd7528be8cf926c345`.

### Gacha concurrente
- Se añadió regresión con dos instancias de Database contra el mismo SQLite para comprobar que una referencia Gacha concurrente termina en una sola tirada, un solo cobro y una sola copia.
- El test detectó un import mal ubicado en la primera implementación; CI lo señaló con Ruff y fue corregido.
- Commit final de código/test: `1f0bf96e6682f53c97bcc08c9bbf7b7cd77a6d2b`.

### Validación definitiva de este bloque
- CI #1126: SUCCESS sobre `1f0bf96e6682f53c97bcc08c9bbf7b7cd77a6d2b`.
- Windows Build #756: SUCCESS sobre el mismo SHA.
- Windows verificó los cinco ejecutables, smoke test de BotManager, instalador, ZIP portable y checksums.
- Los CI #1123, #1124 y #1125 anteriores fallaron únicamente por defectos en los tests nuevos (criterio de matriz/import), y fueron corregidos antes de la validación final.
- El estado actual de `main` queda en `1f0bf96e6682f53c97bcc08c9bbf7b7cd77a6d2b`.

### Estado de producto
- Progreso global se mantiene en **82%**. No sube por añadir pruebas, telemetría o hardening si no se completa una parte sustancial de la visión de producto.
- Interacciones puede considerarse aproximadamente **84%** por la cobertura completa de las parejas dirigidas.
- Personajes/canon se mantiene alrededor de **84%** porque el contenido autoral confirmado sigue siendo el límite.
- Ciudad Animals puede mantenerse alrededor de **88-89%**; el ledger, catálogo, curador y métricas relacionales ya están conectados.
- La prioridad restante sigue siendo profundidad de producto, más contenido autoral confirmado, superficies de Cami/Chie/Cari, mejor UX del operador humano y cierre de versión.

### NO REPETIR
- No volver a implementar el ledger de Ciudad Animals, el catálogo persistente, el curador diario, el puente humano de Tío Otaku, Gacha idempotente, Misterio diario, publicación durable de Cami, control de acceso privado, allowlist de comunidades, fencing de leases ni las matrices authored de interacción salvo que una auditoría futura encuentre un defecto concreto.


## ÚLTIMO BLOQUE EJECUTADO — UX DEL OPERADOR TÍO OTAKU — 2026-09-20

### Cerrado
- La bandeja de Tío Otaku ahora incluye Ver contexto para cada solicitud.
- Se añadió /tio_ver ID para consultar desde el privado del operador el estado, usuario, comunidad, mensaje original, timestamps y texto capturado.
- El contexto es estrictamente de solo lectura; no cambia el estado de la solicitud.
- El callback tio:request:view:ID también es solo lectura y está restringido al propietario.
- El flujo /tio_responder ID mensaje continúa siendo el único mecanismo para enviar una respuesta humana al grupo.
- Commit de UI: 2668ea862b4747c26c69b4d7f9ec56744e3576e1.
- Commit de módulo: f1594e93c1ab61fdfa5e7b21f3d7b3e094894cca.
- Commit final de regresiones: 814995a7fd805b3fea76871d554e01b2b925d5ad.
- CI #1132: SUCCESS sobre 814995a7fd805b3fea76871d554e01b2b925d5ad.
- Windows #762 estaba pendiente al último registro de código; debe verificarse antes de afirmar que el empaquetado de este commit fue validado.

### Corrección detectada durante validación
- CI #1131 detectó que una aserción existente suponía que el botón Resolver era la primera fila.
- Se actualizó el test para exigir simultáneamente el botón de contexto y el botón de resolución.
- No hubo un defecto de producción asociado a ese fallo de test.

### Estado actualizado
- Tío Otaku UX pasa de pendiente a implementado y validado en CI, quedando pendiente únicamente la certificación Windows del SHA final.
- No volver a implementar /tio_ver, el botón tio:request:view, ni el contexto read-only salvo que una auditoría futura encuentre un defecto concreto.
- Progreso global se mantiene en 82%.
