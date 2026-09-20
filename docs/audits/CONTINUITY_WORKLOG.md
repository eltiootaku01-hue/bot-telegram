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
