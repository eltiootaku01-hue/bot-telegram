# WaifuMon — Arquitectura Card Core 2D

## Objetivo
Bot de Telegram coleccionable 2D. El ciclo principal es /roll -> /claim -> inventario -> intercambio.
El juego no necesita combate, 3D, GLTF, Three.js ni IA para las reglas.

## Flujo
~~~
Telegram -> Card Module -> Gacha -> Claim -> Inventory -> Trade
                       |
                       v
                    SQLite
                       |
                       v
                  TMA API -> Mini App 2D
~~~

## Núcleo Python
- app/game/cards.py: definición de carta.
- app/game/card_catalog.py: catálogo persistente.
- app/game/gacha.py: tiradas y rareza.
- app/game/inventory.py: posesión y cantidades.
- app/game/trade.py: intercambio atómico.
- app/modules/cards/module.py: comandos y callbacks.

## Datos mínimos
### CardDefinition
~~~
id
character_id
character_name
anime_origin
rarity
image_url
telegram_file_id
source_provider
source_url
license_note
collection_points
active
created_at
updated_at
~~~

### PlayerCard
~~~
id
user_id
card_id
quantity
obtained_at
updated_at
~~~
UNIQUE(user_id, card_id).

### CardRoll
~~~
id
chat_id
rolled_card_id
rolled_by_user_id
message_id
status
expires_at
claimed_by_user_id
claimed_at
created_at
~~~
UNIQUE parcial por chat para status=active.

### Trade
~~~
id
chat_id
seller_user_id
buyer_user_id
status
expires_at
created_at
accepted_at
~~~

### TradeItem
~~~
trade_id
card_id
quantity
~~~

## /roll
1. Validar chat.
2. Validar cooldown.
3. Generar roll_id único.
4. Resolver rareza + carta localmente.
5. Guardar CardRoll.
6. Enviar imagen 2D y botón Reclamar.

## /claim
UPDATE condicional active -> claimed.
Si rowcount=0, la carta ya fue reclamada o expiró.
Después incrementar PlayerCard dentro de la misma transacción.

Telegram permite reutilizar file_id de archivos ya almacenados en sus servidores, evitando re-subidas innecesarias. citeturn103066search0

## Inventario
Primera versión: paginación Inline.
Segunda versión: Mini App visual para colecciones grandes.
Datos mostrados: imagen, personaje, anime, rareza, puntos y cantidad.

## Mini App
Frontend mínimo:
~~~
webapp/index.html
webapp/css/style.css
webapp/js/app.js
webapp/js/api.js
~~~
Pantallas: Inicio, Mis cartas, Catálogo, Detalle, Intercambios.

Telegram exige validar server-side `Telegram.WebApp.initData`; `initDataUnsafe` no es una fuente confiable para autorización. citeturn783374search0

API mínima:
~~~
GET  /api/cards
GET  /api/cards/{id}
GET  /api/inventory
GET  /api/trades
POST /api/trades
POST /api/trades/{id}/accept
POST /api/trades/{id}/reject
~~~

## Stars
Stars es opcional.
Para bienes digitales dentro de Telegram se usa XTR; el flujo incluye invoice, pre_checkout_query y successful_payment. El charge id debe persistirse para idempotencia y posibles refunds. citeturn783374search1turn783374search3

## Arte
El runtime debe usar preferentemente telegram_file_id o assets estáticos propios.
El catálogo debe conservar source_provider, source_url y license_note para arte de terceros.
No convertir una URL externa en una dependencia crítica del juego.

## Qué retirar del MVP
~~~
webapp/nikke_tcg_demo.html
Three.js / GLTF
equipment_system.js
equipment_catalog.js
combat.js
combat effects
java_engine.py
combate / arena
~~~
El workflow de Pages también debe dejar de exigir esos artefactos.

## Qué conservar
- SQLite + SQLAlchemy async.
- autenticación TMA existente.
- seguridad e idempotencia.
- GameCardCollection y GameGachaRoll como base evolutiva.
- assets 2D.
- GitHub Actions y empaquetado.

## Prioridad
~~~
P0 CardDefinition + catálogo
P0 /roll
P0 /claim
P0 /inventory
P0 idempotencia
P1 Mini App 2D
P1 detalle de carta
P1 trade
P1 Stars opcional
P2 ranking
P2 shiny/eventos
~~~

## Criterio de éxito
El usuario debe poder entrar al grupo, usar /roll, reclamar una carta, verla en /inventory/Mini App y cambiarla con otro jugador sin necesidad de combate ni IA.