# Estado técnico — 2026-09-19

## Estado verificable

Commit de referencia: `321a2533bcd12c448c4c31b26fcfcc13c0e3149b`

CI #879:
- Ruff: OK
- Pytest: OK
- 294 pruebas pasadas

Windows Build #520:
- dependencias: OK
- pruebas nativas de media/encoder: OK
- Inno Setup: OK
- resolución de versión: OK
- compilación de los cinco ejecutables: en ejecución al momento de registrar esta auditoría

## Núcleo endurecido

- Telegram access control centralizado.
- Privados de usuario habilitados para funciones de usuario; workflows administrativos permanecen protegidos por `ADMIN_USER_ID`.
- Callbacks autenticados por `callback.from_user`.
- Allowlist explícita para grupos/supergrupos.
- Envíos en segundo plano de Sunna/Trivia/Cami sujetos a la misma allowlist.
- SQLite WAL + transacciones IMMEDIATE para operaciones de escritura.
- Lease fencing para eventos/jobs.
- TaskSupervisor race-safe.
- Publicaciones de Cami con claim atómico.
- Encuentros WildWaifu con transiciones terminales condicionadas.
- Trivia con rondas vencidas autocurativas y ganador único.
- Gacha persistente e idempotente, con referencias ligadas a jugador + comunidad.
- Estadísticas de Ciudad Animals agregadas, sin texto libre persistido.
- Borrado individual de estadísticas identificables mediante `/borrar_mi_memoria`.
- Resolver de comunidad para estado privado multi-comunidad.

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
- inventario privado.

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
