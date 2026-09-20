# Bitácora maestra de desarrollo continuo — Bot Telegram

**Repositorio:** `eltiootaku01-hue/bot-telegram`  
**Rama operativa:** `main`  
**Fecha de corte:** 2026-09-20  
**Último checkpoint:** ver sección 23; el encabezado histórico no sustituye ese checkpoint.  
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

**SHA actual:** `a79fb778eb9d677ee41d8f9a5d979d31323f402b`

**CI #1194:** SUCCESS  
**Windows Build #824:** SUCCESS

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
