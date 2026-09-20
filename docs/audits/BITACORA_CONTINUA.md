# Bitácora maestra de desarrollo continuo — Bot Telegram

**Repositorio:** `eltiootaku01-hue/bot-telegram`  
**Rama operativa:** `main`  
**Fecha de corte:** 2026-09-20  
**Último checkpoint operativo:** ver la sección 28; el SHA de main y el último SHA funcional se registran por separado.  
**Objetivo:** evitar trabajo repetido, conservar evidencia de errores/pruebas y dirigir cada nueva sesión hacia áreas todavía incompletas.

---

## 1. Regla de uso obligatoria

Antes de modificar código:

1. Leer esta bitácora completa o, como mínimo, las secciones **Estado actual**, **No repetir**, **Errores**, **Pendientes** y **Última evidencia CI**.
2. Consultar el SHA actual de `main`.
3. Comprobar los últimos workflows de Ubuntu y Windows.
4. Comparar el estado actual con esta bitácora.
5. Reabrir un área cerrada solo si existe:
   - regresión;
   - cambio de arquitectura;
   - requisito nuevo;
   - evidencia de producción;
   - prueba ausente que cubra una nueva carrera real.
6. Todo cambio terminado debe existir en GitHub y tener regresión/validación adecuada antes de marcarse como cerrado.

La bitácora es una **memoria técnica**, no una lista de intenciones.

---

# 2. Estado actual

## 2.1 Evidencia de GitHub

**SHA actual histórico:** `a79fb778eb9d677ee41d8f9a5d979d31323f402b`

**Checkpoint histórico:** CI #1194 SUCCESS / Windows Build #824 SUCCESS

### CI #1194

- Ruff: SUCCESS.
- Pytest: SUCCESS.
- Resultado: **408 passed, 52 warnings**.
- Python utilizado por CI: 3.12.
- No hubo fallos de pruebas en el último SHA.

### Windows Build #824

SUCCESS sobre el mismo SHA.

Completó:

- instalación de dependencias;
- pruebas nativas de media/encoder;
- instalación de Inno Setup;
- resolución de versión;
- compilación de los cinco ejecutables;
- verificación de tamaños de los ejecutables;
- smoke test de BotManager;
- construcción del instalador;
- verificación del instalador;
- generación del manifest;
- construcción del ZIP portable;
- generación de SHA-256;
- subida de artefactos.

Artefactos actuales:

- `bot-telegram-windows-installer`
  - digest: `sha256:cbd739b0af4369b2b6d38d8bbf04f5596bf44c40008435d813d291a67e9e8fca`
- `bot-telegram-windows-portable`
  - digest: `sha256:6d9172089684915be53c8c8cf5f96dce51091ed0eb055d34b39a6befda5ae250a`

**Conclusión:** el último estado de GitHub está funcionalmente verde y empaquetado.

---

# 3. Porcentaje global actual

## Estimación conservadora: **79%**

Esta cifra representa cobertura frente a la visión completa del proyecto.  
**No es un porcentaje de CI.**

| Área | Estado |
|---|---:|
| Arquitectura Core | 92% |
| Persistencia / SQLite / transacciones | 97% |
| Telegram / seguridad / runtime | 96% |
| BotManager / Windows / empaquetado | 98% |
| Módulos funcionales | 93% |
| WaifuMon / progresión / trivia | 94% |
| Personajes / canon | 80% |
| Director / repertorio / rutinas | 77% |
| Ciudad Animals / Café Otaku | 78% |
| Interacciones / continuidad | 82% |
| IA secundaria / curación | 40% |
| GUI / experiencia de operador | 48% |

### Motivo por el que no se declara 100%

Todavía existe trabajo sustancial en:

- profundidad autoral;
- repertorio y situaciones de personaje;
- superficies avanzadas de usuario;
- experiencia histórica/operativa de Tío Otaku;
- curación IA desacoplada;
- expansión del mundo;
- GUI más completa;
- release final cuando el siguiente bloque funcional esté realmente cerrado.

No aumentar el porcentaje solo porque una auditoría técnica haya quedado verde.

---

# 4. Arquitectura cerrada y que no debe rehacerse sin evidencia

## Core

- Cuatro identidades independientes:
  - Cari
  - Sunna
  - Cami
  - Chie
- Tío Otaku no es una quinta IA.
- Código local primero; IA secundaria.
- Módulos con routers y tareas supervisadas.
- Lifecycle de módulos centralizado.
- TaskSupervisor race-safe.

## Persistencia

- SQLite + SQLAlchemy async + aiosqlite.
- WAL.
- foreign keys.
- busy timeout.
- `synchronous=NORMAL`.
- fronteras transaccionales en `Database.session()`.
- sesiones de escritura SQLite con `IMMEDIATE`.
- transacciones composables en repositorios/servicios que lo necesitan.
- recuperación de jobs/events mediante lease fencing.
- índices parciales/únicos para estados activos y referencias idempotentes.

## Telegram / seguridad

- `AUTHORIZED_CHAT_IDS` obligatorio para grupos/supergrupos.
- Privado restringido al administrador configurado.
- Middleware fail-closed antes de MemberSync.
- Callback privado autenticado mediante `callback_query.from_user`.
- Los envíos automáticos comprueban la allowlist.
- No usar puntos, balances ni estado de juego como mecanismo de autorización.

## BotManager / Windows

- `BotManager.exe`
- `Cari.exe`
- `Sunna.exe`
- `Cami.exe`
- `Chie.exe`
- Inno Setup.
- ZIP portable.
- checksums.
- smoke test.
- CI Windows.

## Brain / IA

- Opcional.
- Local-first.
- Providers configurables.
- No gobierna canon.
- No sustituye el runtime determinista de personajes.
- La actividad social proactiva no invoca Brain.
- No inventar datos de la comunidad en el contexto LLM.

---

# 5. Sunna / WaifuMon — ya cerrado técnicamente

No repetir una auditoría completa de estas invariantes salvo regresión nueva:

- solo un encuentro salvaje activo por comunidad;
- intentos únicos por usuario/encuentro;
- captura mediante transición condicionada;
- recompensa de captura idempotente;
- evolución/fusión protegida contra carreras;
- expiración no pisa estados terminales;
- encuentros vencidos se retiran antes de crear otro;
- trivia activa única;
- trivia vencida autocurativa;
- ganador de trivia único;
- recompensa de trivia con referencia idempotente;
- rare approvals de una sola decisión;
- ledger de puntos con referencias idempotentes;
- protección de cargos concurrentes.

Archivo de referencia:
`docs/audits/2026-09-19-sunna-waifumon-lifecycle.md`

---

# 6. Cami — ya cerrado técnicamente

No repetir desde cero:

- worker durable;
- claim atómico `scheduled -> publishing`;
- claim atómico de publicaciones de pedidos;
- protección contra doble envío en concurrencia;
- reconciliación de `delivery_unknown`;
- recuperación manual;
- programación local -> UTC;
- catálogo persistente;
- permisos del escritorio privado;
- allowlist del grupo antes de publicación.

La regresión de concurrencia del publisher debe conservarse.

---

# 7. Ciudad Animals — estado

## Ya implementado

- catálogo persistente;
- entradas de lugares;
- roles;
- acciones;
- relaciones confirmadas;
- escenas authored;
- observaciones agregadas;
- scopes:
  - world
  - user
  - user_chat
- insights hot/cold/unseen;
- catálogo sembrado al iniciar;
- no se generan observaciones ficticias solo por sembrar catálogo;
- acciones de Sunna pueden alimentar observación agregada;
- existe diseño para curador IA separado del runtime diario.

Archivo base:
`docs/CIUDAD_ANIMALS_WORLD.md`

Código principal:
`app/services/world.py`
`app/services/world_catalog.py`
`app/db/world_models.py`

## Pendiente

El mundo todavía necesita más **vida funcional real**, no simplemente más filas de catálogo:

- escenas contextuales;
- eventos cotidianos;
- interacciones que dependan de estado;
- más situaciones del Café;
- integración progresiva de acciones reales;
- curación periódica con aprobación humana;
- expansión narrativa solo desde material confirmado por el autor.

---

# 8. Personajes y canon

## Cari

Canon separado del runtime.

Ideas estructurales ya confirmadas:

- protectora;
- energética;
- optimista;
- extrovertida;
- competitividad amistosa;
- impulso a ayudar;
- miedo a no ser suficientemente fuerte;
- arco hacia aprender a confiar y aceptar ayuda.

## Cami

Canon separado del runtime.

Ideas estructurales confirmadas:

- analítica;
- estratégica;
- observadora;
- introvertida;
- curiosidad intelectual;
- empatía silenciosa;
- honestidad intelectual;
- miedo a equivocarse y perjudicar a alguien;
- arco desde comprender mediante análisis hacia integrar análisis + empatía + confianza.

## Sunna

Canon separado del runtime.

Ideas estructurales confirmadas:

- descendiente de Jörmungandr;
- reservada;
- sensible;
- observadora;
- leal;
- baja autoestima;
- miedo a volver a quedarse sola;
- curiosidad ante experiencias cotidianas;
- arco de “la serpiente busca el sol”;
- su linaje no debe interpretarse como maldad inherente.

## Chie

No inventar una biblia narrativa nueva mientras no haya material autoral confirmado.

Su runtime actual debe tratarla principalmente como:

- coordinadora;
- servicial;
- nerviosa;
- orientada a permisos;
- avisos;
- reglas;
- organización.

---

# 9. Director / repertorio / rutinas

Ya existe:

- `CharacterProfile`;
- `DialogueScene`;
- `CharacterDirector`;
- `CharacterIntentRouter`;
- `RoutineDirector`;
- repertorio authored-only;
- follow-ups entre personajes;
- selección determinista;
- pruebas de cobertura de identidad;
- pruebas que impiden convertir Sunna en una caricatura de “Hm / No sé”.

## Pendiente

Aumentar:

- variedad situacional;
- estados emocionales;
- situaciones del Café;
- interacciones espontáneas authored;
- relaciones más profundas.

No confundir “más líneas” con “más profundidad”. Priorizar escenas nuevas que aporten comportamiento distinto.

---

# 10. Interacciones multi-identidad

Ya corregido:

- el follow-up authored se envía con la identidad Telegram real del personaje que habla;
- no se falsifica el segundo hablante;
- se conserva `message_thread_id` cuando corresponde;
- si falta token del segundo personaje, no se fabrica una identidad falsa;
- existe inyección de transporte para tests;
- hay pruebas específicas de transporte y rotación.

No repetir salvo regresión.

---

# 11. Tío Otaku

Regla absoluta:

**Tío Otaku es humano.**

Ya existe:

- captura de vocativo explícito;
- bandeja;
- contexto;
- estados;
- claim para evitar doble respuesta;
- recuperación;
- respuesta manual;
- navegación histórica;
- trazabilidad;
- ninguna generación automática de su voz.

## Pendiente

- inbox más visual;
- navegación histórica más cómoda;
- mejores filtros/estados;
- más herramientas de operador;
- auditoría visual del flujo.

No convertirlo en un agente autónomo.

---

# 12. Superficies ya cerradas

No recrear sin requisito nuevo:

- `/ranking`;
- `/ayuda` navegable;
- panel comunitario accionable de Chie;
- menú navegable del Café Otaku;
- catálogo base de Ciudad Animals;
- transporte multi-identidad;
- validación de configuración del BotManager.

Reutilizar las abstracciones existentes.

---

# 13. Errores reales encontrados durante el desarrollo

Esta sección existe específicamente para que una futura sesión no cometa el mismo error otra vez.

## Error A — callback privado autenticado contra el usuario equivocado

### Síntoma

Un callback privado podía evaluarse con el `from_user` del mensaje embebido en vez del usuario que pulsó el botón.

### Causa

El extractor de mensaje resolvía `update.message/edited_message` antes del `callback_query`.

### Corrección

El callback pasa a ser fuente primaria cuando existe y el actor se toma de:

`callback_query.from_user`

### Regresión

Se creó un test donde el mensaje pertenece al bot y el click pertenece al administrador.

### Resultado

Corrección validada por CI.

---

## Error B — test de concurrencia de Cami incompatible con nueva allowlist

### Síntoma

El publisher rechazó correctamente el grupo del fixture como no autorizado.

### Causa

El test de concurrencia todavía construía `Settings` sin `AUTHORIZED_CHAT_IDS`.

### Corrección

Se modificó el fixture, no la protección de producción.

### Lección

Cuando una nueva política central de seguridad entra en producción, todos los tests de flujos legítimos deben declarar explícitamente el contexto autorizado.

---

## Error C — test Cami concurrente usando SQLite :memory:

### Síntoma

La prueba concurrente no representaba correctamente varias sesiones.

### Causa

`:memory:` no era adecuado para ese escenario multi-conexión.

### Corrección

El test pasó a SQLite respaldado por archivo temporal.

### Lección

Las pruebas de carrera deben usar una base que reproduzca la topología real de conexiones.

---

## Error D — tests de zona horaria con imports incompletos

### Síntoma

La lógica era correcta pero CI fallaba al ejecutar la regresión nueva.

### Causa

Faltaban imports de `pytest` y `timezone`.

### Corrección

Imports completados y contrato endurecido para rechazar datetimes timezone-aware donde el sistema espera almacenamiento naive UTC.

---

## Error E — Trivia: transacción interna incompatible con el llamador

### Síntoma

`TriviaService` todavía hacía commits/rollbacks internos, a diferencia del resto de servicios endurecidos.

### Riesgo

Un flujo superior no podía mantener atomicidad sobre todo el conjunto de operaciones.

### Corrección

La responsabilidad de la transacción volvió al llamador y los errores de integridad usan nested transactions donde corresponde.

### Regresión

Se añadió una prueba que ejecuta la respuesta dentro de una transacción superior y fuerza rollback.

---

## Error F — expiración de WildWaifu pisando estado terminal

### Síntoma

Un proceso de expiración podía intentar escribir `expired` después de una captura.

### Corrección

Transición SQL condicionada por:

- ID;
- estado `active`;
- `expires_at <= now`.

### Regresión

Una fila `captured` nunca vuelve a `expired`.

---

## Error G — encuentros/trivia vencidos bloqueando nuevos elementos

### Síntoma

El índice único de activos podía dejar una fila vencida en estado `active`.

### Corrección

Retiro autocurativo de filas vencidas antes de crear el siguiente evento.

---

## Error H — TaskSupervisor podía perder el seguimiento de una tarea nueva

### Síntoma

Callback tardío de una tarea antigua podía quitar del diccionario una tarea nueva con el mismo nombre.

### Corrección

`_finish()` solo elimina si el objeto de tarea registrado es exactamente el mismo.

---

## Error I — lease fencing de Event/Job recovery

### Síntoma

Un recovery viejo podía pisar un worker que había renovado el lease.

### Corrección

UPDATE condicionado por ID + status + locked_at + heartbeat_at exactos.

---

# 14. Errores de CI que NO deben interpretarse como fallos del código final

Durante desarrollo hubo runs fallidos/cancelados por cambios consecutivos.

La regla correcta:

- un run viejo fallido no invalida un SHA posterior;
- un run cancelado por un nuevo push no es un fallo funcional;
- la fuente de verdad es el último SHA que tenga CI + Windows SUCCESS.

No borrar del historial los fallos reales: se conservan aquí para conocer su causa.

---

# 15. Pruebas acumuladas relevantes

La suite incluye, entre otras:

- CharacterDirector;
- repertorio;
- rutinas;
- interacciones;
- seguridad de chat;
- callbacks privados;
- MemberSync;
- repositorios de miembros;
- transacciones;
- RequestService;
- puntos/idempotencia;
- GameAttempt;
- capturas;
- evolución;
- fusión;
- encuentros;
- WildWaifu scheduler;
- rare approvals;
- trivia;
- world service;
- world catalog;
- Cami publisher;
- jobs;
- events;
- TaskSupervisor;
- acceso/allowlist;
- configuración BotManager;
- operator health;
- native media/encoder;
- BotManager smoke test en Windows.

**Último resultado completo:** 408 pruebas pasadas.

---

# 16. Siguiente trabajo recomendado

Orden de prioridad para la siguiente sesión:

### Prioridad 1 — profundidad de interacción

Crear escenas authored nuevas que produzcan comportamientos diferentes:

- llegada de un usuario;
- conversación sobre anime;
- usuario que gana/perder en WaifuMon;
- usuario que agradece a Sunna;
- Cami corrigiendo una inconsistencia;
- Chie ayudando con organización;
- Cari detectando que alguien necesita ayuda;
- pequeña escena grupal de las cuatro.

Cada escena debe incluir:

1. código;
2. uso real;
3. observación/world event cuando corresponda;
4. regresión;
5. CI.

### Prioridad 2 — Ciudad Animals vivo

Pasar de “catálogo + observación” a pequeñas escenas/eventos cotidianos deterministas.

### Prioridad 3 — Tío Otaku

Mejorar la bandeja histórica y herramientas de operador sin automatizar su voz.

### Prioridad 4 — curación IA

Diseñar el primer informe periódico:

observaciones -> tendencias -> propuesta -> aprobación humana.

La IA no debe modificar el canon directamente.

### Prioridad 5 — release final

Solo después de cerrar una tanda funcional real:

- CI Ubuntu SUCCESS;
- Windows SUCCESS;
- artefactos presentes;
- SHA único;
- bitácora actualizada.

---

# 17. Regla de “no repetir 100 veces”

No volver a implementar:

- middleware de allowlist;
- TaskSupervisor fencing;
- Event/Job lease fencing;
- MemberSync transaction ownership;
- RequestService transaction ownership;
- rare approval fencing;
- WildWaifu expiration fencing;
- trivia stale-state;
- Cami publication claim;
- Cami delivery reconciliation;
- transporte multi-identidad;
- /ranking;
- /ayuda;
- panel de Chie;
- menú del Café;
- catálogo base de Ciudad Animals;
- validación de BotManager.

Solo abrirlos si aparece evidencia nueva.

---

# 18. Último estado de documentación

Documentos de referencia existentes:

- `docs/CIUDAD_ANIMALS_WORLD.md`
- `docs/audits/2026-09-19-sunna-waifumon-lifecycle.md`
- `docs/audits/2026-09-20-continuity-state.md`
- auditorías específicas de seguridad, social runtime, acceso Telegram y empaquetado Windows.

Esta bitácora debe ser el primer documento consultado en las siguientes sesiones.

---

# 19. Criterio de cierre de cualquier bloque futuro

Un bloque NO está terminado porque:

- exista el archivo;
- compile localmente;
- “parezca correcto”;
- el asistente haya explicado el código.

Un bloque está terminado cuando:

1. el código está en GitHub;
2. existe regresión suficiente;
3. la regresión pasa;
4. CI pasa cuando corresponde;
5. Windows pasa cuando afecta empaquetado/runtime;
6. la bitácora registra qué cambió;
7. la bitácora registra los errores encontrados;
8. se actualiza la lista de “no repetir”.

---

# 20. Snapshot final de esta bitácora

**Estado global:** 79%  
**SHA:** `a79fb778eb9d677ee41d8f9a5d979d31323f402b`  
**CI:** #1194 SUCCESS  
**Windows:** #824 SUCCESS  
**Pytest:** 408 passed  
**Empaquetado:** SUCCESS  
**Artefactos:** instalador + portable presentes  
**Bloque técnico:** estable  
**Bloque de producto:** continúa en profundidad autoral, mundo vivo, superficies avanzadas, operador e IA curadora.

**Regla inmediata para la siguiente sesión:** no rehacer infraestructura cerrada; comenzar por una capacidad de producto nueva que pueda ser probada y observada.


# 21. Bloque adicional — Misterio diario del Café Otaku (2026-09-20)

## Motivo

Se detectó una superficie declarada pero incompleta: el menú del Café mostraba “Misterio diario”, aunque no existía una función ejecutable asociada.

## Implementación realizada

- Nuevo motor determinista: `app/services/cafe_mystery.py`.
- Cinco minicasos authored con opciones y resolución.
- Selección estable por `fecha + chat_id`; no depende de estado aleatorio del proceso.
- Los casos se consideran cotidianos/no canónicos y no añaden hechos narrativos.
- `CafeModule` expone `/misterio`.
- Se añadió botón inline `🕵️ Misterio` al menú del Café.
- El callback diferencia correctamente entre abrir el caso y responder una opción.
- Botones de un día anterior se rechazan como vencidos.
- Las aperturas y resoluciones alimentan el world observation ledger.
- `cafe_mystery` quedó declarado también en `WORLD_CATALOG`.

## Regresiones

- `tests/test_cafe_mystery.py`: valida catálogo, determinismo y selección por chat.
- `tests/test_cafe_module.py`: valida que el menú anuncie el misterio y que publique un caso con botones.
- `tests/test_cafe_surface.py`: valida el botón `cafe:mystery:open`.

## Error detectado antes de CI

El primer diseño utilizó el mismo prefijo de callback para abrir el misterio y para responderlo, pero el botón de apertura tenía tres segmentos y el parser de respuesta esperaba cuatro. La implementación se separó en:

- `cafe:mystery:open` para abrir;
- `cafe:mystery:<case_index>:<option_index>` para responder.

La regresión quedó cubierta antes de considerar el bloque terminado.

## Evidencia de validación

- SHA validado del código: `b10a94af7d81a5b9316ee18180bb005a5805833c`.
- CI #1207: SUCCESS.
- Windows Build #837: SUCCESS.
- El empaquetado Windows completó ejecutables, smoke test, instalador, ZIP portable, checksums y artifacts.

## Decisión de no repetición

No volver a auditar el misterio diario ni el botón de navegación salvo regresión. El siguiente trabajo debe crear una capacidad diferente que aporte comportamiento nuevo al producto.

# 22. Estado de corte de esta bitácora

- Código funcional validado: `b10a94af7d81a5b9316ee18180bb005a5805833c`.
- Última suite conocida: 408 pruebas pasadas en CI #1194 antes de este bloque; el CI del bloque actual también terminó SUCCESS.
- Porcentaje global conservador: **79%**.
- El incremento de este bloque mejora principalmente Ciudad Animals/Café Otaku, pero no justifica elevar artificialmente el global.
- Próximo foco: situaciones authored nuevas e interacción contextual; no reabrir infraestructura ya cerrada.

---

# 23. CHECKPOINT MAESTRO — 2026-09-20 10:01 ART

## Estado certificado de GitHub

- Rama: `main`
- SHA actual: `9244bf7ed818a0ec899b8f2dbcbfe65cc0f3c903`
- Commit actual: `docs: record Cafe mystery validation block`
- CI #1208: **SUCCESS**
- Windows Build #838: **SUCCESS**
- Ambos pipelines corresponden al mismo SHA.

### CI #1208

- Ruff: SUCCESS.
- Pytest: SUCCESS.
- Resultado exacto: **412 passed, 52 warnings**.
- No hubo fallos de pruebas en el SHA actual.

### Windows Build #838

SUCCESS sobre el mismo SHA.

Verificaciones completadas:

- instalación de dependencias;
- pruebas nativas de media/encoder;
- Inno Setup;
- resolución de versión;
- compilación de los cinco ejecutables;
- verificación de ejecutables;
- smoke test de BotManager;
- instalador;
- manifest;
- ZIP portable;
- SHA-256;
- subida de artefactos.

Artefactos:

- `bot-telegram-windows-installer`
  - tamaño: 98,775,170 bytes
  - digest: `sha256:70dcc5dde5966fe531292c94d46465c4eb489d87d55502a04d724b7b70914376`
- `bot-telegram-windows-portable`
  - tamaño: 96,917,008 bytes
  - digest: `sha256:50c53bc8ea010ca2e8975fec80f4a753e46034402df0baa4e274f3712c9509e1`

## Qué se hizo desde el checkpoint anterior

El delta desde `a79fb778eb9d677ee41d8f9a5d979d31323f402b` contiene 14 commits y se concentró en el Café Otaku:

- Misterio diario determinista.
- Cinco minicasos cotidianos authored.
- Separación correcta de callbacks de apertura/respuesta.
- Integración del misterio en el menú del Café.
- Observación agregada de apertura/resolución.
- Inclusión del misterio en el catálogo de Ciudad Animals.
- Regresiones de misterio, superficie y catálogo.
- Correcciones de mocks/fixtures descubiertas por CI.

No se inventó canon narrativo nuevo durante este bloque.

## Errores reales registrados y aprendizaje

### 1. Parser de callback del Misterio
La primera versión reutilizaba el mismo patrón de callback para abrir y responder. El botón de apertura tenía tres segmentos y el parser de respuesta exigía cuatro.

**Corrección:** 
- apertura: `cafe:mystery:open`;
- respuesta: `cafe:mystery:<case_index>:<option_index>`.

**Regresión:** `tests/test_cafe_surface.py` y `tests/test_cafe_module.py`.

**Estado:** cerrado y validado.

### 2. Test del menú del Café
CI detectó un mock que aceptaba solo `text`, mientras producción correctamente pasaba `reply_markup`.

**Corrección:** el test se adaptó al contrato real de Telegram.

**Lección:** no relajar producción para satisfacer un mock incompleto.

**Estado:** cerrado y validado.

### 3. Concurrencia Cami
El test de carrera del publisher necesitó SQLite respaldado por archivo en vez de `:memory:` para representar conexiones concurrentes reales.

**Lección:** las pruebas de concurrencia deben reproducir la topología de persistencia usada en producción.

**Estado:** cerrado y validado.

### 4. Zona horaria
Se endurecieron los contratos para rechazar `datetime` timezone-aware donde el sistema espera valores naïve UTC/locales explícitos.

**Estado:** cerrado y validado.

### 5. Acceso de callbacks
Se corrigió la identificación del actor de callback para usar `callback_query.from_user` en vez del autor del mensaje embebido.

**Estado:** cerrado y validado.

## Capacidades que NO deben rehacerse

No volver a implementar desde cero:

- allowlist y middleware de acceso;
- autenticación correcta de callbacks;
- Transaction ownership de MemberSync/RequestService/Trivia;
- TaskSupervisor fencing;
- Event/Job lease fencing;
- puntos idempotentes;
- Gacha idempotente;
- WildWaifu expiration/stale cleanup;
- trivia stale lifecycle y winner fencing;
- rare approvals;
- Cami publication claim/reconciliation;
- catálogo local de anime/manga;
- búsqueda por personaje/alias;
- `/anime_ficha`;
- `/ayuda` por identidad;
- transporte multi-identidad;
- relaciones authored y continuidad relacional;
- Tío Otaku inbox/contexto/respuesta manual;
- validación del BotManager;
- catálogo base de Ciudad Animals;
- observación agregada y curador;
- menú del Café;
- recomendación determinista;
- Misterio diario;
- empaquetado Windows.

Solo reabrir una de estas áreas ante regresión, cambio de requisito, cambio de arquitectura o evidencia de producción.

## Porcentaje actual

**Estimación global conservadora: 82%.**

No se eleva artificialmente por el éxito de CI o Windows.

| Área | Estimación |
| --- | ---: |
| Arquitectura/Core | 95% |
| Persistencia/transacciones | 97% |
| Telegram/seguridad/runtime | 96% |
| Workers/events/jobs | 95% |
| BotManager/Windows/instalador/portable | 98% |
| Módulos funcionales | 93% |
| WaifuMon/progresión/trivia/misterio | 92% |
| Personajes/canon/repertorio | 84% |
| Director/rutinas/interacciones | 86% |
| Ciudad Animals/Café Otaku | 90% |
| IA secundaria/curaduría | 76% |
| Puente Tío Otaku | 90% |
| GUI/UX operador | 50% |

### Por qué sigue en 82%

La base técnica está muy avanzada y el proyecto ya compila/empaqueta de punta a punta, pero todavía falta profundidad de producto:

- más contenido autoral confirmado;
- escenas contextuales con mayor variedad;
- superficies de Cari/Cami/Chie todavía delgadas en algunos caminos;
- mejor experiencia histórica del operador humano;
- mayor curación y administración del mundo;
- GUI más completa;
- release etiquetado final con versionado deliberado.

## Próximo foco obligatorio

La siguiente sesión debe comenzar aquí, no desde infraestructura cerrada:

### Prioridad 1
Crear escenas authored contextuales nuevas con uso real:
- llegada;
- actividad del Café;
- reacción a victoria/derrota en juegos;
- ayuda;
- gratitud;
- pequeñas escenas de grupo.

Cada bloque necesita código + uso real + telemetría si corresponde + regresión + CI.

### Prioridad 2
Convertir Ciudad Animals de catálogo/telemetría en eventos cotidianos deterministas, sin inventar canon.

### Prioridad 3
Mejorar las superficies funcionales todavía simples de Cami/Chie/Cari.

### Prioridad 4
Seguir mejorando Tío Otaku como operador humano; nunca convertirlo en una quinta IA.

### Prioridad 5
Diseñar/afinar curación IA como proceso separado:
observaciones -> informe -> propuesta -> aprobación humana.

## Regla contra repetición accidental

Antes de empezar un nuevo bloque:

1. leer esta sección 23;
2. consultar `main`;
3. verificar el último CI y Windows;
4. escoger un pendiente de producto;
5. comprobar que no exista ya;
6. escribir primero código y regresión;
7. validar;
8. actualizar esta bitácora con SHA, workflows, errores y decisiones.

La bitácora debe registrar tanto los éxitos como los fallos de CI que hayan provocado cambios.

---

# 24. CORRECCIÓN DE CONTINUIDAD — 2026-09-20

## SHA realmente actual de `main`

- `main`: `dd941d5e231e61d74b64917dc099cfec6ead210b`
- Commit: `docs: refresh continuous development master log`
- Este commit modifica únicamente la bitácora maestra; no modifica código funcional.

## Último código funcional certificado

- SHA funcional: `9244bf7ed818a0ec899b8f2dbcbfe65cc0f3c903`
- CI #1208: **SUCCESS**
- Windows Build #838: **SUCCESS**
- Pytest: **412 passed, 52 warnings**
- Windows: cinco ejecutables + smoke test + instalador + ZIP portable + checksums + artifacts.

## Validación del cambio documental

- CI #1209: **SUCCESS** sobre `dd941d5e231e61d74b64917dc099cfec6ead210b`.
- Windows Build #839 fue disparado por el cambio documental. Su resultado debe tratarse como validación del repositorio/documentación; la certificación funcional del código sigue siendo Windows #838 sobre `9244bf7...` mientras no exista un cambio de código posterior.

## Regla corregida

La palabra **“actual”** en esta bitácora siempre debe referirse al SHA de `main` más reciente.

Cuando `main` tenga un commit solo documental posterior al último código:

- registrar ambos SHAs;
- identificar explícitamente cuál es el último código funcional;
- no declarar un SHA documental como si fuera una nueva versión funcional;
- no recalcular el porcentaje global por cambios puramente documentales.


---

# 25. RECONCILIACIÓN OPERATIVA — 2026-09-20

## Fuente de verdad

La rama main avanzó desde el antiguo snapshot c13da707... hasta:

- main actual: 6a25b0dd95ea02737135b8b8a50dbf1a8e198531
- commit main: docs: reconcile master log current and functional SHAs
- El commit de main es documental y no cambia la lógica funcional.

### Último código funcional certificado

- SHA funcional: 9244bf7ed818a0ec899b8f2dbcbfe65cc0f3c903
- CI #1208: SUCCESS
- Windows Build #838: SUCCESS
- Pytest: 412 passed, 52 warnings
- Windows verificó los cinco ejecutables, smoke test de BotManager, instalador, ZIP portable, checksums y artefactos.

### Estado inmediatamente posterior

- CI #1210: SUCCESS sobre 6a25b0dd95ea02737135b8b8a50dbf1a8e198531.
- Windows Build #840: ejecución iniciada sobre el mismo SHA; debe usarse como validación documental hasta que termine.
- No debe contarse 6a25... como una nueva versión funcional mientras el árbol no cambie código.

## Corrección del problema de continuidad

La bitácora contenía referencias a a79fb... que ya no representaban la punta de main. Se confirma mediante comparación de commits que a79fb... pertenece a una línea descendiente del código actual, pero no es la referencia operativa de main.

Regla nueva:

- main SHA = última referencia efectiva de la rama.
- functional SHA = último commit que modificó código y obtuvo CI + Windows SUCCESS.
- Un commit documental posterior no reemplaza el SHA funcional.
- Una rama experimental no se considera integrada hasta que el commit esté ancestral a main.

## No repetir

No volver a implementar ni auditar desde cero:

- TaskSupervisor;
- Event/Job lease fencing;
- MemberSync transaction ownership;
- RequestService transaction ownership;
- callbacks privados;
- allowlist;
- puntos/gacha idempotentes;
- WildWaifu/trivia lifecycle fencing;
- Cami publication fencing;
- Misterio diario;
- catálogo base de Ciudad Animals;
- catálogo anime/manga;
- /ayuda;
- transporte multi-identidad;
- Tío Otaku inbox/claim/respuesta manual;
- validación de BotManager;
- empaquetado Windows.

Solo reabrirlos ante regresión, nuevo requisito o evidencia de producción.

## Trabajo que sí queda abierto

1. Interacciones contextuales authored: escenas que reaccionen a eventos de juego/Café sin generar texto libre.
2. Ciudad Animals vivo: eventos cotidianos deterministas que utilicen el catálogo y observaciones.
3. Superficies: reducir caminos descriptivos en Cari/Cami/Chie.
4. Tío Otaku: mejorar navegación operativa e historial.
5. Curación IA: continuar snapshot -> propuesta -> aprobación sin autoescritura del canon.
6. Release: etiquetado final deliberado, con una única línea de código certificada.

## Porcentaje

Estimación global conservadora: 82%.

No se incrementa por commits documentales ni por un pipeline Windows todavía en ejecución.

## Regla de actualización

Cada nueva sesión debe:

1. leer la sección 25;
2. consultar main;
3. consultar CI y Windows;
4. comparar con functional SHA;
5. elegir una deuda abierta concreta;
6. implementar código + regresión;
7. validar;
8. añadir una entrada con errores, causa, corrección y evidencia.

---
# 26. REACCIONES CONTEXTUALES AUTHORED DE SUNNA — 2026-09-20

Objetivo: reaccionar a resultados reales de WaifuMon sin generación libre. Se añadieron GAME_SUCCESS y GAME_MISS, ocho líneas authored de Sunna y selección determinista mediante CharacterDirector.

Integración real: captura correcta, fallo de encuentro, gacha normal y misterio (éxito/fallo). Estas rutas no invocan Brain/LLM.

Errores encontrados en CI #1220:
1. test de misterio sin User/Chat para satisfacer las FK del GameProfile. Corrección: fixture completo.
2. test de gacha esperaba <b>Sunna:</b>, pero producción usa “🐍 Sunna:”. Corrección: expectativa del test.
3. test normal de gacha usaba Rarity.B y por ello entraba al flujo de aprobación rara. Corrección: CommonEngine con Rarity.D.

Validación final:
- SHA funcional: 585c01caf0c590786f05497dccfccc7a11efba5c
- CI #1222: SUCCESS
- Windows Build #852: SUCCESS sobre el mismo SHA
- Windows completó cinco ejecutables, verificación, smoke test de BotManager, instalador, manifest, ZIP portable, SHA-256 y artifacts.

Archivos principales: app/characters/models.py, app/characters/repertoire.py, app/modules/game/module.py, tests/test_game_capture.py, tests/test_game_gacha_handler.py.

No repetir: no reauditar esta capa desde cero salvo regresión, nuevo resultado de juego o cambio de arquitectura. Mantenerla authored-only; no convertirla en generación LLM.

Estado global conservador: 82%. No se incrementa por este bloque porque siguen abiertas GUI, profundidad autoral, superficies avanzadas y release final.

Próximo foco: escenas contextuales authored de Cari/Cami/Chie, eventos cotidianos de Ciudad Animals, superficies operativas, curación IA con aprobación humana y release final.


---
# 27. CHECKPOINT ACTUAL — INICIALIZACIÓN REAL DEL CATÁLOGO DE CIUDAD ANIMALS — 2026-09-20

## Problema detectado

La implementación de Ciudad Animals ya disponía de:

- WorldCatalogDefinition y WORLD_CATALOG;
- WorldService.seed_catalog();
- pruebas de idempotencia del seed;
- catálogo de lugares, roles, acciones y relaciones authored.

Sin embargo, la auditoría de composición encontró que seed_catalog() no tenía un consumidor productivo obligatorio. En consecuencia, una instalación real podía arrancar con el catálogo vacío aunque las pruebas unitarias del servicio pasaran.

## Corrección

Se creó app/modules/world/module.py con WorldCatalogModule.

El módulo:

1. pertenece al lifecycle común de los bots;
2. se monta en las cuatro identidades mediante app/core/bot_composition.py;
3. ejecuta WorldService.seed_catalog() durante on_startup();
4. conserva la idempotencia existente y no genera observaciones falsas;
5. se convirtió en paquete Python explícito mediante app/modules/world/__init__.py para que setuptools/PyInstaller lo reconozcan de forma determinista.

## Regresiones añadidas

- tests/test_bot_composition.py: todas las identidades deben incluir world-catalog.
- tests/test_world_catalog.py: WorldCatalogModule.on_startup() debe persistir todo el catálogo y el repertorio.
- Se preserva la prueba de seed idempotente para ejecuciones repetidas.

## Errores / aprendizaje

### A. Catálogo probado pero no inicializado en producción

Síntoma: el servicio y sus pruebas estaban correctos, pero no había una llamada garantizada desde el lifecycle real.

Causa: se había implementado el mecanismo de seed como capacidad de servicio sin convertirlo en una responsabilidad de arranque.

Corrección: módulo compartido de inicialización montado en las cuatro identidades.

Lección: una capacidad de persistencia no debe considerarse integrada hasta que exista un consumidor productivo verificable.

### B. Paquete Python implícito

Riesgo: el nuevo directorio podía funcionar en el árbol fuente pero no ser tratado igual por las herramientas de empaquetado.

Corrección: app/modules/world/__init__.py.

Lección: los nuevos subpaquetes destinados al ejecutable deben ser explícitos, no depender de namespace packages accidentales.

## Evidencia

- main / SHA actual: ae31d55776328ac8cc3963e42f6aad2181b0f31f
- CI #1228: SUCCESS
- Windows Build #858: SUCCESS
- Pytest en CI: 415 passed, 52 warnings
- Windows verificó los cinco ejecutables, smoke test de BotManager, instalador, manifest, ZIP portable, SHA-256 y subida de artefactos.

## Estado funcional

Este bloque sí queda cerrado. No volver a implementar ni auditar desde cero la inicialización del catálogo salvo regresión, cambio de arquitectura o nuevo requisito.

## Porcentaje global

82% conservador.

No se eleva por el hecho de que el catálogo ahora arranque correctamente: el fix cierra una brecha dentro de una capacidad ya existente. Las áreas grandes aún abiertas siguen siendo profundidad de producto, escenas contextuales, superficies avanzadas, GUI y maduración de la curación IA/release.

## No repetir

Añadir a la lista de capas cerradas:

- WorldCatalogModule / seed obligatorio de Ciudad Animals;
- paquete explícito app.modules.world;
- regresiones de startup del catálogo.

## Siguiente foco real

No volver a infraestructura cerrada. Comenzar por una capacidad de producto nueva, preferentemente:

1. eventos cotidianos authored de Ciudad Animals;
2. escenas contextuales de Cari/Cami/Chie con uso real;
3. mejora de la experiencia del operador humano Tío Otaku;
4. curación IA periódica con propuesta y aprobación humana;
5. preparación de release final versionado.


---
# 28. CHECKPOINT DOCUMENTAL — DIFERENCIA ENTRE MAIN Y CÓDIGO FUNCIONAL — 2026-09-20

Este commit de bitácora es únicamente documental.

- main en el momento de este checkpoint: dd8b7a0a99758017af4a5a5a8a4005ad783576ad
- último código funcional validado: ae31d55776328ac8cc3963e42f6aad2181b0f31f
- CI del código funcional: #1228 SUCCESS
- Windows del código funcional: #858 SUCCESS
- Pytest del código funcional: 415 passed, 52 warnings

Regla: el commit documental no se considera una nueva versión funcional ni cambia el porcentaje.

Esta sección existe para que una sesión futura no confunda el HEAD de main con el último SHA que modificó código.


# 29. Snapshot operativo — 2026-09-20 10:44 ART

## 29.1 Identidad exacta del estado actual

- Rama: `main`.
- SHA actual: `d3e5a67ac795eb7770453e53f1d117ec567520bf`.
- Este SHA contiene una corrección documental sobre el encabezado/checkpoint; las capacidades funcionales que lo preceden también forman parte de la cadena actual de `main`.
- No existe un SHA funcional separado que deba tratarse como entrega final.

## 29.2 Evidencia de validación del SHA actual

### CI #1231 — SUCCESS

- Ruff: SUCCESS.
- Pytest: SUCCESS.
- Resultado exacto: **416 passed, 52 warnings**.
- Python: 3.12.
- No hubo pruebas fallidas.
- Los warnings restantes no bloquearon CI.

### Windows Build #861 — SUCCESS

El mismo SHA completó instalación de dependencias, pruebas nativas de media/encoder, Inno Setup, resolución de versión, compilación de Cari/Sunna/Cami/Chie/BotManager, verificación de ejecutables, smoke test de BotManager, instalador, manifest, ZIP portable, SHA-256 y subida de artefactos.

Artefactos actuales:

- `bot-telegram-windows-installer` — 98,781,626 bytes — digest `sha256:799cfad31e0a657492c58aeeb92cf2b1d6018710bc47344b664f5797a1536bb7`.
- `bot-telegram-windows-portable` — 96,924,348 bytes — digest `sha256:8be3c8f3b200c6040e2ea196b1232a692da6d2cd734d09fb3b9582c3a504f486`.

## 29.3 Capacidades funcionales presentes en main desde el checkpoint anterior

### Ciudad Animals / Café

- Catálogo persistente formalizado en `app/services/world_catalog.py`.
- Inicializador `WorldCatalogModule` ejecutado por las cuatro identidades.
- Registro idempotente del catálogo y del repertorio authored.
- Lugares, roles, acciones y relaciones confirmadas declaradas como entradas del mundo.
- Café Otaku con recomendación diaria determinista.
- Misterio diario del Café con resolución authored y caducidad por día.
- El misterio cotidiano está explícitamente fuera del canon narrativo.
- Telemetría agregada en ámbitos world/user/user_chat.
- El mundo no almacena texto libre de conversación para sus métricas.

### Sunna / WaifuMon

- Reacciones authored para éxito/error de juego.
- Reacciones contextuales de misterio y gacha.
- Expresividad de Sunna ampliada sin convertirla en generación libre.
- Continuidad de interacciones conserva el uso acumulado del par/personaje donde está disponible.

### Interacciones multi-identidad

- `CharacterDirector.choose_interaction()` selecciona únicamente escenas authored.
- El segundo hablante se transporta con la identidad Telegram correspondiente.
- El seguimiento conserva `message_thread_id` cuando corresponde.
- Si falta el token del personaje compañero, el sistema no finge identidad.

## 29.4 Errores y correcciones de este tramo

1. **Checkpoint documental desfasado.** La bitácora mantenía un SHA funcional histórico distinto de `main`. Se corrigió el encabezado para distinguir el checkpoint histórico del estado operativo real.
2. **Módulo de mundo no empaquetable/descubrible de forma consistente.** Se añadió `app/modules/world/__init__.py` para tratar el módulo como paquete Python explícito.
3. **Siembra del catálogo no garantizada en todos los procesos.** Se incorporó `WorldCatalogModule` a la composición compartida y se probó su inicialización.
4. **Cobertura insuficiente de escenas/reacciones de Sunna.** Se añadieron reacciones authored para resultados de juego y se verificaron sus formatos.
5. **Pruebas sucesivas canceladas por pushes posteriores.** Los runs cancelados se conservaron como evidencia histórica; el cierre usa únicamente el último SHA con CI y Windows SUCCESS.

## 29.5 Nuevos bloques que NO deben repetirse

No recrear sin evidencia nueva:

- siembra del catálogo base de Ciudad Animals;
- `WorldCatalogModule` y su montaje en las cuatro identidades;
- misterio diario del Café;
- navegación básica del Café;
- recomendación diaria determinista;
- reacciones authored de Sunna para resultados básicos de juego;
- matriz de interacciones authored ya existente;
- transporte multi-identidad del follow-up;
- auditorías de concurrencia, leases y Cami publisher ya cerradas;
- `/ranking`, `/ayuda` y paneles básicos ya implementados.

Reabrir solamente ante regresión, cambio de requisitos o nueva evidencia de producción.

## 29.6 Porcentaje actual revisado

**Estimación global conservadora: 81%.**

No es una métrica de CI ni de líneas de código. Se incrementa solo por capacidades funcionales nuevas verificadas y reducción demostrable de deuda de producto.

| Área | Estado estimado |
| --- | ---: |
| Arquitectura Core | 92% |
| Persistencia / SQLite / transacciones | 97% |
| Telegram / seguridad / runtime | 96% |
| BotManager / Windows / empaquetado | 98% |
| Módulos funcionales | 94% |
| WaifuMon / progresión / trivia | 95% |
| Personajes / canon | 81% |
| Director / repertorio / rutinas | 80% |
| Ciudad Animals / Café Otaku | 83% |
| Interacciones / continuidad | 86% |
| IA secundaria / curación | 40% |
| GUI / experiencia de operador | 48% |

### Por qué sigue sin ser 100%

Queda trabajo real de producto en:

- mayor profundidad del repertorio y de los estados cotidianos;
- eventos persistentes del mundo y del Café más allá de catálogo/misterios;
- herramientas avanzadas para Tío Otaku como operador humano;
- curación IA periódica desacoplada del runtime;
- GUI de administración más completa;
- superficies de Cami/Chie/Cari todavía simples frente a la visión final;
- ampliación documental local y su integración como fuente de referencia.

## 29.7 Próximo bloque obligatorio

La siguiente tanda debe evitar infraestructura de bajo valor. La prioridad es una capacidad de producto con efecto observable.

**Objetivo:** ampliar el comportamiento cotidiano del Café Otaku mediante eventos authored y estado ligero, conectados al WorldService y probados de extremo a extremo.

Criterio de cierre:

- código en GitHub;
- prueba específica;
- persistencia verificada;
- CI SUCCESS;
- Windows SUCCESS si afecta runtime/empaquetado;
- bitácora actualizada;
- no repetir bloques ya cerrados.

## 29.8 Fuente de verdad

La fuente de continuidad sigue siendo este archivo: `docs/audits/BITACORA_CONTINUA.md`.

Antes de tocar código, comparar siempre: SHA actual de `main`, último CI SUCCESS, último Windows SUCCESS, sección de errores, lista de no repetición y pendientes de producto.
