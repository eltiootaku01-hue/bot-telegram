# Estado técnico — 2026-09-19

## Estado verificable

Commit de referencia: `3f2e4a1261a5ea4b2111e226a6e769e674e6b802`

CI #938:
- Ruff: OK
- Pytest: OK
- 312 pruebas pasadas
- Sin fallos de Pytest en el SHA de referencia

Windows Build #579:
- dependencias: OK
- pruebas nativas de media/encoder: OK
- Inno Setup: OK
- cinco ejecutables compilados y verificados
- smoke test de BotManager: OK
- instalador: OK
- ZIP portable: OK
- SHA-256: OK
- artefactos de instalador y portable subidos correctamente

## Núcleo endurecido

- Telegram access control centralizado.
- Privados de usuario habilitados para funciones de usuario; workflows administrativos permanecen protegidos por `ADMIN_USER_ID`.
- Callbacks autenticados por `callback.from_user`.
- Allowlist explícita para grupos/supergrupos.
- Envíos en segundo plano de Sunna/Trivia/Cami sujetos a la misma allowlist.
- SQLite WAL + transacciones IMMEDIATE para operaciones de escritura.
- Lease fencing para eventos/jobs.
- TaskSupervisor race-safe.
- Publicaciones de Cami con claim atómico y transacción inmediata durante la toma de turno.
- Encuentros WildWaifu con transiciones terminales condicionadas.
- Trivia con rondas vencidas autocurativas y ganador único.
- Gacha persistente e idempotente, con referencias ligadas a jugador + comunidad.
- Misterio diario con ronda única por comunidad/día, ganador único, recompensa idempotente y recuperación tras fallo de publicación.
- Estadísticas de Ciudad Animals agregadas, sin texto libre persistido.
- Borrado individual de estadísticas identificables mediante `/borrar_mi_memoria`.
- Resolver de comunidad para estado privado multi-comunidad.
- Entradas de Ciudad Animals seeded desde catálogo persistente.
- `/misterio` integrado en el comando de Sunna.
- Inputs de horario validan explícitamente datetimes naïve antes de convertirlos entre UTC y zona mundial.

## Producto funcional actual

Cari:
- presencia comunitaria;
- conversación determinista;
- escenas y rutinas del Café Otaku.

Sunna:
- Gacha;
- WaifuMon;
- encuentros;
- colección;
- evolución;
- combate;
- trivia;
- puntos;
- ranking;
- inventario privado;
- Misterio diario del Café Otaku.

Cami:
- captura/catálogo de medios;
- etiquetado;
- programación;
- publicación durable;
- recuperación de entregas ambiguas;
- pedidos asociados a medios.

Chie:
- onboarding y comprobación de permisos;
- creación de temas del foro;
- panel comunitario;
- reglas;
- bienvenida;
- configuración;
- coordinación de pedidos;
- métricas de Ciudad Animals.

## Límites deliberados

La IA sigue siendo opcional y secundaria. El runtime social y los personajes usan repertorio authored/determinista. La IA no es fuente de canon.

El mundo narrativo y las escenas pueden seguir creciendo, pero los cambios deben incorporarse mediante catálogo/repertorio autorizado y no mediante generación libre en la ruta cotidiana.

## Evidencia

El SHA de referencia quedó validado por CI #938 y Windows Build #579. La validación Windows cubrió compilación, verificación, smoke test, instalador, ZIP portable y checksums. Los artefactos permanecen asociados a esa ejecución de GitHub Actions.
