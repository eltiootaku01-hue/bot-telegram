# Estado persistente de continuidad del proyecto

Fecha de auditoría: 2026-09-20

Este archivo es una memoria técnica del trabajo ya realizado. Antes de volver a tocar un área, revisar este documento para evitar repetir auditorías ya cerradas sin una razón nueva.

## Corregido y validado

### Plataforma y persistencia
- Arquitectura modular de cuatro bots: Cari, Sunna, Cami y Chie.
- SQLite + SQLAlchemy async + aiosqlite.
- WAL, foreign keys, busy timeout y fronteras transaccionales centralizadas.
- Modos SQLite de transacción y sesiones de escritura con `IMMEDIATE`.
- Recuperación race-safe de eventos y jobs mediante fencing de lease.
- TaskSupervisor protegido contra callbacks tardíos de tareas antiguas.

### Seguridad Telegram
- Allowlist explícita de grupos/supergrupos mediante `AUTHORIZED_CHAT_IDS`.
- Privado restringido al administrador configurado.
- Middleware fail-closed antes de MemberSync.
- Callbacks privados autentican al usuario que pulsa, no al autor del mensaje embebido.
- Envíos automáticos de WildWaifu, Trivia, Cami y Tío Otaku comprueban autorización antes de entregar contenido a una comunidad.

### Sunna / WaifuMon
- Encuentro activo único por comunidad.
- Captura condicional `active -> captured`.
- Intentos únicos por usuario/encuentro.
- Recompensas de captura idempotentes.
- Evolución/fusión protegida contra carreras.
- Expiración no puede sobrescribir estados terminales.
- Encuentros vencidos se retiran antes de crear otro.
- Trivia: ronda activa única, rondas vencidas autocurativas y ganador único.
- Aprobaciones de drops raros: una sola decisión válida.
- Puntos: ledger con referencias idempotentes y protección de carreras.

### Cami
- Publicación durable con worker.
- Claim atómico `scheduled -> publishing`.
- Claim atómico de publicaciones de pedidos.
- Reconciliación de `delivery_unknown`.
- Programación convertida de hora de Ciudad Animals a UTC.
- Concurrencia de publicación cubierta por regresión.
- Catálogo local de medios y catálogo local de anime/manga.
- Recuperación manual de entregas ambiguas.

### Ciudad Animals
- Catálogo persistente de lugares, roles, acciones y relaciones confirmadas.
- Observación agregada global, usuario y usuario+chat.
- Curator diario de tendencias.
- Propuestas opcionales con IA separadas del canon.
- El runtime cotidiano sigue siendo determinista y authored-only.

### Personajes e interacciones
- Profiles de Cari, Cami, Sunna y Chie.
- Canon de Cari/Cami/Sunna separado del runtime.
- Repertorio authored-only.
- CharacterDirector determinista y sin generación de texto.
- Matriz de interacciones entre las cuatro identidades.
- Seguimientos multi-personaje y continuidad por uso de relación.
- Sunna no depende de respuestas vacías: existe repertorio de curiosidad, pertenencia, afecto, gratitud y crecimiento.

### Tío Otaku
- Es operador humano, no una quinta IA.
- Captura solo vocativos explícitos.
- Bandeja persistente.
- Contexto de solicitud.
- Respuesta manual exacta.
- Claim de respuesta para evitar doble envío.
- Recuperación si Telegram falla.
- Historial técnico de estados.
- IA no redacta respuestas como Tío Otaku.

### Windows
- Cinco ejecutables: BotManager + Cari + Sunna + Cami + Chie.
- Instalador Inno Setup.
- ZIP portable.
- Smoke test de BotManager.
- Checksums.
- CI Ubuntu y Windows verdes sobre `c13da70731d...`.

## Pendiente real

1. Profundidad autoral: aumentar repertorio y escenas usando únicamente material confirmado; ampliar Chie solo cuando exista material autoral confirmado.
2. Más interacciones en runtime: la matriz está cubierta, pero deben crecer las situaciones realmente ejercitadas por el usuario, no solamente el número de escenas.
3. Superficies: mejorar navegación práctica de Cari/Cami/Chie y reducir comandos que solo muestran texto descriptivo.
4. Tío Otaku: mejorar inbox, navegación histórica y trazabilidad visual sin automatizar su voz.
5. Concurrencia: auditar únicamente rutas que todavía carecen de una regresión específica.
6. Release final: etiquetar versión cuando el siguiente bloque funcional de producto esté cerrado y su CI haya pasado.

## Regla de no repetición

No volver a “auditar desde cero” TaskSupervisor, leases, access middleware, transacciones de MemberSync, RequestService, publicación atómica de Cami, expiración de WildWaifu, trivia stale-state, rare approvals o el paquete Windows salvo que aparezca evidencia nueva, una regresión, una modificación relevante o un requisito nuevo.

## Próximo objetivo

Primero profundizar superficies y continuidad de interacción; después cerrar una tanda funcional suficientemente grande para preparar el release final.

## Registro de ejecución — 2026-09-20 (bloque posterior al snapshot)

### Punto de partida comprobado
- `main` estaba en `c89cf3a7cc6202413642b4d772a85e58ef8356fe`.
- CI #1176: SUCCESS.
- Windows Build #806: SUCCESS.
- No se reabrieron TaskSupervisor, leases, access middleware, RequestService, Cami publication fencing, WildWaifu expiration, trivia stale-state, rare approvals ni empaquetado Windows, porque no apareció evidencia nueva que justificara otra auditoría completa.

### Trabajo realizado
1. **Catálogo base de Ciudad Animals**
   - Se incorporó `app/services/world_catalog.py`.
   - Define lugares, roles, acciones y relaciones ya respaldadas por el diseño del proyecto.
   - `ChatModule` siembra el catálogo al iniciar sin crear observaciones ficticias.
   - Se añadió `tests/test_world_catalog.py`.
   - No se añadió una biblia nueva de Chie ni hechos narrativos no confirmados.

2. **Validación de configuración del Bot Manager**
   - Se incorporó `app/services/setup_validation.py`.
   - Valida tokens/enlaces requeridos, IDs numéricos, duplicados, allowlist de grupos, ADMIN_USER_ID y chats de infraestructura.
   - Bot Manager ejecuta esta validación antes de guardar/iniciar.
   - Los secretos nunca se imprimen en los mensajes de validación.
   - Se añadió `tests/test_setup_validation.py`.

### Errores encontrados durante esta línea de trabajo
- En una regresión anterior, CI detectó imports incompletos en los tests de zona horaria; se corrigieron antes de continuar.
- CI también detectó que el test de concurrencia del publisher Cami no estaba configurando la nueva allowlist; se corrigió el fixture, no la lógica de producción.
- Ambos errores fueron usados para endurecer la suite en lugar de ocultarlos o saltar las pruebas.

### Evidencia de validación
- El estado anterior confirmado: CI #1176 y Windows #806 SUCCESS.
- Las modificaciones posteriores de esta sección deben considerarse pendientes hasta que sus propios pipelines sobre el SHA final aparezcan como SUCCESS.
- Regla: nunca considerar un bloque terminado únicamente porque el commit exista; exigir validación de GitHub Actions cuando el cambio lo requiera.

### Regla de no repetición reforzada
No volver a implementar otra capa de validación de configuración dentro de Tkinter ni duplicar `parse_numeric_ids`. Cualquier nueva superficie de configuración debe reutilizar `validate_setup()`.


## Registro posterior — superficies de operación

### Mejora entregada
- Bot Manager ahora valida configuración antes de iniciar procesos mediante `app/services/setup_validation.py`.
- Chie ahora presenta un panel comunitario accionable por sección, con comandos concretos y navegación de retorno.
- Se añadieron regresiones para la validación de configuración y las cinco secciones del panel.
- El panel no asume que Chie sea Sunna/Cami: remite explícitamente al bot responsable cuando una acción pertenece a otra identidad.

### Errores y correcciones
- El test de concurrencia de Cami inicialmente no declaraba el chat en la allowlist después de endurecer el publisher. Se corrigió el fixture; la protección de producción se mantuvo.
- No se detectaron errores funcionales nuevos en la implementación del panel antes de subirla.
- Los runs intermedios de CI/Windows cancelados por nuevos pushes no se consideran fallos funcionales; el SHA más reciente es la fuente de verdad.

### Validación pendiente de este bloque
- CI #1183 y Windows #813 deben terminar SUCCESS sobre `0ca6b5bab05199f8931cf7faea23e5a5eaf7bcc8`.
- No marcar esta mejora como cerrada por existencia del commit solamente.

### Próximo foco
Después de validar este bloque, priorizar superficies aún simples de Cari/Cami y la experiencia histórica de Tío Otaku, sin reabrir componentes de concurrencia ya cubiertos.



### Incidencia detectada por CI
- CI #1191 ejecutó 407 pruebas y falló 1: `test_cafe_menu_is_authored_and_contains_core_services`.
- Causa exacta: el mock del test aceptaba solo `text`, mientras el nuevo comportamiento correcto de producción pasó `reply_markup`.
- Corrección: el mock ahora acepta argumentos de presentación y exige que `reply_markup` exista. No se relajó el código de producción.
- Resultado esperado: nueva validación sobre el SHA `8322acdf92a5f54e8bc99c9d74d6624c5d9029a0`.


## Registro posterior — navegación del Café y revisión de superficies

### Mejora entregada
- `app/ui/cafe_keyboards.py` añade navegación del Café Otaku.
- El menú de Cari ofrece recomendación interna y enlaces configurados a Sunna, Cami y Chie.
- `CafeModule` conserva el uso de la misma zona horaria configurada y ahora recibe la instancia real de `Settings` desde `build_bot_modules()`.
- Se añadió regresión para impedir que la composición pierda esos enlaces.
- Se añadió callback directo para la recomendación determinista.

### Revisión para evitar duplicación
- Se comprobó que `/ranking` de Sunna ya consulta `GameProfile`, ordena por puntos/experiencia/ID y devuelve los diez primeros; no se volvió a implementar.
- Se buscó texto de placeholders como “Próximamente”, “se mostrará”, “no implementada” y “pendiente de implementar”; no se encontró una ruta falsa equivalente en el código actual.
- Se comprobó que Cami ya posee catálogo local de medios y fichas de anime/manga, y que Chie ya posee reglas, salud, mundo, propuestas y onboarding.

### Regla de no repetición
No recrear `/ranking`, catálogo de Cami ni los paneles de ayuda existentes salvo regresión o cambio de requisitos. Las próximas mejoras de producto deben centrarse en superficies todavía simples que aporten una capacidad nueva.


## Cierre de validación — SHA dddd55f40549d71d118f35939f390e8dc7c0459c

### Evidencia final
- CI #1193: SUCCESS.
- Windows Build #823: SUCCESS.
- Los dos pipelines apuntaron al mismo SHA `dddd55f40549d71d118f35939f390e8dc7c0459c`.
- Windows completó: 5 ejecutables, verificación de tamaños, smoke test de BotManager, instalador Inno Setup, manifest, ZIP portable, SHA-256 y subida de ambos artefactos.
- Artefacto portable: `bot-telegram-windows-portable`, digest `sha256:dcaca62b7b8ceab0a10e3026b16eabb699d8db0d6ec777bf2ff55447164cf16a`.
- Artefacto instalador: `bot-telegram-windows-installer`, digest `sha256:05e011633094c39ce2722c5acbab474423f98f357cb0042348e30eb073adebfa`.

### Estado de producto
- Estimación global conservadora: **79%**.
- No se incrementa artificialmente por haber cerrado CI/empaquetado: todavía existen trabajo de profundidad autoral, superficies avanzadas, GUI y evolución de la curación IA.
- El bloque de navegación/operación de esta sesión queda cerrado; no volver a implementarlo salvo regresión o requisito nuevo.

### Registro de decisiones para futuras sesiones
- No rehacer auditorías de concurrencia ya cerradas sin evidencia nueva.
- No reimplementar `/ranking`, `/ayuda`, catálogo base de Ciudad Animals ni transporte multi-identidad.
- Reutilizar `validate_setup()` para nuevas pantallas de configuración.
- Reutilizar `cafe_menu_keyboard()` para ampliar el Café sin duplicar enlaces.
- Toda mejora de producto nueva debe añadir código + regresión + CI antes de considerarse terminada.
- El archivo de continuidad es obligatorio como primera referencia antes de iniciar una nueva tanda.

## Snapshot 2026-09-20 — actualización posterior

Estado global conservador: 79%. Esta cifra estima cobertura frente a la visión completa del proyecto; no es una métrica de CI.

| Área | Estado estimado |
| --- | ---: |
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

### Bloque funcional cerrado en esta tanda

- Ayuda navegable por identidad: /ayuda ahora abre un panel específico de Cari, Sunna, Cami o Chie y permite navegar por secciones sin mezclar identidades.
- Interacción multi-identidad real: cuando una escena authored involucra a otro personaje, el follow-up se envía con el token Telegram de la identidad que realmente habla; en foros conserva message_thread_id. Si falta el token del compañero, no se falsifica el segundo hablante.
- Ciudad Animals inicial: el catálogo persistente incluye lugares, roles, acciones y relaciones confirmadas; el estado se siembra al arrancar sin generar observaciones ficticias.
- Validación del bloque: Ubuntu CI #1175 y Windows Build #805 quedaron success sobre el mismo SHA 6ecd41d6a482f0a70cf57eef5ceb2faab3c249fd.

### Checklist actualizado

- Profundidad autoral: EN PROGRESO. Se amplía solo material confirmado; no se creó una biblia nueva de Chie.
- Más interacciones: BLOQUE ACTUAL CERRADO. La matriz está cubierta, las relaciones confirmadas tienen variantes y el transporte multi-identidad ya representa al hablante real.
- Superficies: BLOQUE ACTUAL CERRADO para /ayuda; todavía pueden enriquecerse Cami/Cari/Chie con paneles de sus funciones.
- Tío Otaku: AVANZADO. No convertirlo en una quinta IA sigue siendo una invariante.
- Concurrencia: AVANZADO. Seguir solo cuando exista una ruta nueva sin regresión específica.
- Release final: LISTO PARA TAG una vez que este snapshot quede en main; no crear otro bloque funcional artificial solo para inflar el porcentaje.

### No repetir sin evidencia nueva

Además de los bloques anteriores, no volver a auditar desde cero el transporte multi-identidad de interacciones, el panel navegable de /ayuda ni la siembra del catálogo base de Ciudad Animals. Solo reabrirlos ante regresión, cambio de diseño o requisito nuevo.

## Bitácora maestra

La fuente principal de continuidad es `docs/audits/BITACORA_CONTINUA.md`. Este documento conserva contexto histórico; antes de iniciar nuevo trabajo debe leerse la bitácora maestra y luego usar este archivo como detalle histórico.

## Snapshot 2026-09-20

Estimación global conservadora del proyecto: 77%. No es una métrica de CI; es una estimación de cobertura funcional frente a la visión completa del proyecto.

| Área | Estado estimado |
| --- | ---: |
| Arquitectura Core | 92% |
| Persistencia / SQLite / transacciones | 97% |
| Telegram / seguridad / runtime | 95% |
| BotManager / Windows / empaquetado | 98% |
| Módulos funcionales | 92% |
| WaifuMon / progresión / trivia | 94% |
| Personajes / canon | 79% |
| Director / repertorio / rutinas | 75% |
| Ciudad Animals / Café Otaku | 70% |
| Interacciones / continuidad | 72% |
| IA secundaria / curación | 40% |
| GUI / experiencia de operador | 45% |

### Avance del checklist solicitado

- Profundidad autoral: EN PROGRESO. Se amplió únicamente material compatible con Cari/Cami/Sunna confirmado; no se creó una biblia nueva para Chie.
- Más interacciones: EN PROGRESO. La matriz ya cubre las 12 parejas dirigidas y ahora las relaciones confirmadas tienen variantes adicionales; el runtime ya usa choose_interaction con continuidad por uso.
- Superficies de usuario: EN PROGRESO. Se añadieron /ayuda por identidad y navegación histórica de Tío Otaku; Cami/Cari/Chie todavía pueden recibir superficies más ricas.
- Tío Otaku: AVANZADO. Captura explícita, inbox, contexto, respuesta humana, fencing y navegación histórica ya existen.
- Concurrencia: AVANZADO. Se cerraron muchas rutas y se sigue tocando solo donde falta regresión específica.
- Release final: PENDIENTE. No etiquetar todavía hasta cerrar el siguiente bloque funcional y obtener CI Ubuntu + Windows verdes sobre el mismo SHA.

### No repetir sin evidencia nueva

No reauditar desde cero los bloques ya marcados como corregidos arriba. Una nueva pasada debe buscar solo regresiones, consumidores nuevos o requisitos nuevos.
