# Auditoría atómica — WaifuMon Scavenger / inventario de chatarra

Fecha: 2026-09-22
Rama auditada: main

## 0. Resumen ejecutivo

El repositorio contiene una arquitectura de WaifuMon considerablemente más completa que su inventario visual real.

Estado físico observado en GitHub:

- 533 archivos versionados en el árbol auditado.
- Java/Maven: motor de reglas + contrato NDJSON + recursos JSON + tests JUnit.
- Python: bridge Java, API aiohttp/TMA, HMAC de Telegram, persistencia, servicios de juego y módulos Telegram.
- WebApp: HTML/CSS/JS estático, Canvas 2D, efectos visuales y cliente de API.
- Assets binarios de producción: 2 entradas de cartas, ambas almacenadas mediante Git LFS como punteros en el árbol Git.
- Sprites de combate reales en `assets/production/sprites/`: 0 PNG; solo README.
- Audio bruto real: 0 archivos; solo README.
- UI bruta real: 0 archivos; solo README.
- VFX bruto real: 0 archivos; solo README.
- Iconos brutos reales: 0 archivos; solo README.
- Quarantine: 51 SVG de personajes + 3 imágenes raster adicionales visibles en el árbol.

Esto significa que buena parte del sistema visual está implementada como contrato, manifiesto o fallback de código, pero todavía no como biblioteca de producción distribuible.

---

# 1. INVENTARIO DE LO QUE YA TENEMOS

## 1.1 Backend & Red

### Motor Java

Ruta:

`engine/waifumon/`

Stack:

- Java 21.
- Maven.
- Jackson.
- JUnit 5.
- Maven Shade para generar un JAR ejecutable.

Archivos principales:

- `engine/waifumon/src/main/java/com/eltiootaku01/waifumon/Main.java`
- `engine/waifumon/src/main/java/com/eltiootaku01/waifumon/WaifuMonRuleEngine.java`
- `contract/EngineRequest.java`
- `contract/EngineResponse.java`

Transporte:

- NDJSON por stdin/stdout.
- Contrato versión `1.0`.
- Campos externos en snake_case.
- `request_id`.
- `correlation_id`.
- `player_id`.
- `community_id`.
- `command`.
- `payload`.
- `idempotency_key`.

La autoridad del gameplay migrado es Java.

Reglas ya cubiertas por el engine:

- gacha;
- combate simple;
- resolución de combate mediante fórmula declarativa;
- estados;
- progresión;
- evolución;
- estadísticas;
- estilo por elemento;
- potencial.

El engine además mantiene una caché de idempotencia en memoria y rechaza reutilización de una misma clave con otro fingerprint.

### Bridge Python → Java

Ruta:

`app/game/java_engine.py`

El bridge:

- descubre el JAR;
- descubre Java del sistema o runtime bundled;
- levanta un proceso persistente;
- serializa JSON por línea;
- verifica `request_id`;
- propaga códigos de error del engine;
- expone wrappers async mediante `asyncio.to_thread()`.

Esto evita bloquear el event loop de aiohttp/Telegram cuando se utiliza el bridge.

### Fachada Python

Ruta:

`app/game/engine.py`

`GameEngine` ya es una fachada sobre Java, no un segundo motor matemático independiente.

Sin embargo, hay dos contratos de resolución de combate dentro del engine Java:

1. `combat.resolve` — usado actualmente por el camino principal de Mini App/Telegram.
2. `combat.resolve_formula` — contiene la fórmula detallada documentada en `combat-formula.json`.

El primer camino usa una fórmula sencilla de potencia + nivel + variación semilla + multiplicador de rareza.

El segundo usa:

`base = floor(floor(floor((2 * level / 5 + 2) * skill_power * attack / defense) / 10))`

y después:

`modified = floor(base * element_multiplier * status_multiplier * move_multiplier)`

y finalmente crítico y damage floor.

### API Python / aiohttp

Ruta:

`app/api/tma_server.py`

Servidor:

- aiohttp.
- corriendo como servidor no bloqueante gestionado por BotManager.
- thread/event-loop propio.
- creación de schema antes de levantar la API.
- cierre coordinado de runner y engine.

Endpoints de negocio actualmente identificados:

- `GET /api/combat/init`
- `POST /api/combat/action`
- `POST /api/store/invoice`

### Autenticación HMAC Telegram

Ruta:

`app/api/tma_auth.py`

La API valida:

- `X-Telegram-Init-Data`;
- alternativa `Authorization: TMA ...`;
- HMAC con `WebAppData` + token del bot;
- unicidad de campos de initData;
- hash hexadecimal;
- `auth_date`;
- expiración máxima;
- tolerancia de reloj futura;
- objeto `user`;
- ID de usuario positivo.

La aplicación no usa `initDataUnsafe` como autoridad.

### CORS / seguridad de API

El middleware de TMA:

- valida origen contra `TMA_ALLOWED_ORIGINS`;
- permite OPTIONS como preflight;
- añade `Cache-Control: no-store`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- devuelve error JSON uniforme.

Además, la comunidad configurada debe estar explícitamente autorizada por la allowlist de chats.

### Combate TMA

`TmaCombatService`:

- obtiene comunidad configurada por Chie;
- rechaza comunidad no autorizada;
- carga colección del usuario;
- permite un tutorial determinista con Taiga si no hay colección;
- limita nivel 1..30;
- genera contrato de assets;
- delega daño al engine Java;
- incorpora idempotency key ligada al usuario/comunidad.

La respuesta devuelve:

- atacante;
- defensor;
- acción;
- daño;
- crítico;
- HP;
- state version;
- event IDs;
- reward IDs.

### Telegram Stars

Ruta:

- `app/api/tma_payments.py`
- `app/modules/tma_payments/module.py`
- `app/services/tma_payments.py`

Productos declarados:

- `premium_ticket`
- `starter_pack`

Moneda:

- `XTR`.

Flujo:

`POST /api/store/invoice`
→ creación de factura Telegram Stars
→ `pre_checkout_query`
→ validación de usuario/producto/moneda/precio
→ `successful_payment`
→ fulfillment durable/idempotente.

La entrega usa `telegram_payment_charge_id` como referencia de idempotencia y existe prueba de cobro repetido que no duplica el inventario.

### Infraestructura Telegram adicional

El repositorio también contiene:

- cuatro identidades de bot;
- BotManager;
- SQLite WAL;
- jobs durables;
- event bus;
- turn arbiter;
- scheduler WildWaifu;
- trivia;
- puntos;
- requests;
- moderación;
- Cami publisher;
- Chie setup;
- Social Runtime.

---

# 1.2 Frontend & WebApp

Ruta:

`webapp/`

Archivos funcionales:

- `index.html`
- `css/style.css`
- `js/api.js`
- `js/combat.js`
- `js/effects.js`
- `js/main.js`
- `README.md`

### HTML

La Mini App contiene:

- encabezado de jugador;
- equipo 0/3;
- recursos;
- showcase de carta;
- HUD de HP;
- Canvas 768x432;
- botones attack/special/defend;
- tienda Stars;
- referral;
- cut-in de especial;
- overlay CRT.

### Canvas 2D

La implementación de combate es Canvas 2D.

Hay:

- render de personajes;
- carga de sprites;
- fallback visual cuando falta el sprite;
- poses `idle`, `attack`, `hit`;
- barra/estado HP;
- hit flash;
- partículas;
- shake;
- cut-in.

No hay una implementación WebGL/shader GLSL real en el árbol auditado.

### Screenshake

El movimiento de cámara se implementa en JavaScript mediante una transformación aleatoria limitada durante el impacto.

No requiere assets externos.

### CRT

Implementado en CSS:

- scanlines;
- flicker;
- vignette;
- mezcla visual;
- reglas `prefers-reduced-motion`.

### Foil holográfico

Implementado en CSS/DOM:

- `foil-glare`;
- gradientes violeta/rojo;
- tilt 3D con `rotateX/rotateY`;
- desplazamiento del glare;
- soporte para orientación del dispositivo;
- `DeviceOrientationEvent.requestPermission()` cuando el navegador lo exige.

No es un shader GPU; es una composición CSS.

### Efectos VFX generados por código

Ruta:

`webapp/js/effects.js`

Clase:

`LightweightCombatEffects`

Incluye:

- partículas circulares;
- streaks;
- burst;
- slash;
- additive compositing;
- vida corta;
- drag;
- bounded frame step;
- máximo duro de 96 partículas.

Esto cubre una parte del VFX sin depender de archivos externos.

### GitHub Pages

Existe workflow:

`.github/workflows/deploy-pages.yml`

Valida:

- HTML;
- JS;
- CRT;
- foil;
- device orientation;
- Canvas;
- partículas;
- sintaxis con `node --check`.

La API se inyecta mediante `TMA_API_BASE_URL`.

---

# 1.3 Chatarra Visual & Audio

## Producción de cartas

Ruta:

`assets/production/cards/`

Entradas visibles en el árbol:

1. `alisa-kujo--normal.jpg`
2. `alisa-kujo--r.jpg`

Pero ambos son punteros Git LFS en el contenido Git, no bytes JPEG inline.

Sus objetos LFS declarados son:

- normal: 105502 bytes reales declarados.
- R: 100468 bytes reales declarados.

El contrato exige:

- 1024×1536;
- JPEG/JPG;
- 50 KiB..8 MiB;
- provenance;
- aprobación.

La proveniencia de ambos assets está documentada como `original`/cleared.

### Estado global del arte

`assets/waifus/art_manifest.json`:

- total: 78;
- producción aprobada: 1;
- pendientes: 60;
- quarantined_noncompliant: 17.

Distribución por tier:

- R: 2
- S: 6
- SR: 51
- UR: 19

El único personaje marcado `production_approved` es:

- Alisa Kujo.

### Discrepancia detectada

`assets/waifus/art_progress.json` mantiene:

- `total_cards = 78`
- `completed_cards = 0`

mientras `art_manifest.json` ya declara 1 item completado/aprobado.

Eso indica un tracker de progreso stale que necesita reconciliación.

---

## Sprites de combate

Ruta:

`assets/production/sprites/`

Estado físico:

**0 PNG de combate.**

Solo existe:

- `assets/production/sprites/README.md`

El contrato está plenamente definido:

- `<id>_idle.png`
- `<id>_attack.png`
- `<id>_hit.png`
- 128×128;
- PNG;
- transparencia alfa.

Pero el manifiesto:

`assets/waifus/combat_visual_manifest.json`

declara 78 personajes × 3 poses = **234 referencias lógicas** y todas figuran `pending`.

Por tanto:

**234 sprites objetivo existen en contrato, 0 bytes de sprite están en producción.**

El frontend tiene fallback cuando no encuentra la imagen.

---

## Audio

Ruta:

`assets/raw/audio/`

Estado físico:

**0 archivos de audio.**

Solo existe README.

No hay actualmente:

- click;
- hover;
- confirm;
- cancel;
- attack;
- hit;
- critical;
- special;
- victory;
- defeat;
- ambience.

Por tanto el combate actual es visual/silencioso a nivel de asset externo.

El manifest Scavenger sí define fuentes CC0 para audio, pero sus bytes no están extraídos en el árbol actual.

---

## UI / HUD externos

Ruta:

`assets/raw/ui/`

Estado físico:

**0 archivos.**

Solo README.

La UI actual existe principalmente en:

- HTML;
- CSS;
- Canvas;
- emojis;
- elementos generados.

El manifest Scavenger sí define candidatos CC0 de Kenney y otros packs, pero permanecen fuera del working tree físico.

---

## VFX externos

Ruta:

`assets/raw/vfx/`

Estado físico:

**0 archivos.**

Solo README.

No hay sheets externos de:

- hit spark;
- slash;
- explosion;
- burst;
- dust;
- smoke;
- energy;
- shield.

Los únicos VFX realmente presentes en runtime son los generados por `effects.js`.

---

## Iconos

Ruta:

`assets/raw/icons/`

Estado físico:

**0 archivos.**

Solo README.

---

## Quarantine

El árbol contiene:

- 51 SVG de personajes en `assets/quarantine/`;
- además de 3 JPG raster visibles:
  - `card_stages/alisa-kujo--ur.jpg`
  - `generated/kuro-shiny-card-v1.jpg`
  - `generated/waifu-card-concept.jpg`.

Los SVG de quarantine no están autorizados automáticamente para producción.

Entre los personajes presentes como SVG se encuentran:

Ai Hoshino, Akame, Akane Kurokawa, Akeno Himejima, Aki Nijou, Ako Tamaki, Albedo, Alisa Kujo, Asuna Yuuki, Boa Hancock, Celistia Ralgris, Cha Hae-In, Chelsea, Chisato Hasegawa, Chizuru Mizuhara, Darkness, Elizabeth Liones, Emilia, Erina Nakiri, Erza Scarlet, Esdeath, Hinata Hyuga, Ino Yamanaka, Jibril, Kuroka, Lilith Asami, Lucy Heartfilia, Makima, Mary Kikakujou, Midnight, Mikasa Ackerman, Mirajane Strauss, Momo Yaoyorozu, Nami, Nejire Hadou, Nene Yashiro, Nico Robin, Oguri Cap, Power, Rangiku Matsumoto, Raphtalia, Reiko Kujirai, Rias Gremory, Rin Tohsaka, Taiga, Tsunade, Venelana Gremory, Violet Evergarden, Yor Forger, Yoruichi Shihouin y Yumeko Jabami.

---

# 1.4 Lógica & Esquemas

## Card schema

Ruta:

`engine/waifumon/src/main/resources/waifumon/card-schema.json`

Campos principales:

- card_id;
- name;
- base_atk;
- base_def;
- base_hp;
- cost;
- element_type;
- skills;
- status_effects.

Elementos permitidos:

- fuego;
- agua;
- tierra;
- aire;
- hielo;
- luz;
- oscuridad;
- rayo;
- mente;
- arcano;
- neutro.

## Skills

Cada skill puede definir:

- skill_id;
- name;
- power;
- category;
- crit_rate;
- crit_multiplier;
- element_multiplier;
- status_effect;
- skill_effect.

Tipos de skill effect:

- damage;
- heal;
- shield;
- apply_status;
- draw;
- resource.

## Status effects

El schema permite:

- poison;
- bleed;
- stun;
- shield.

El recurso `status-effects.json` agrega duración, resolución y fórmulas.

## Card data de prueba

Solo hay **1 archivo de carta de ejemplo**:

`cards.sample.json`

Contiene:

- 1 carta;
- 2 skills:
  - claw;
  - guard;
- 2 status effects:
  - stun;
  - shield.

Esto es suficiente como contrato de prueba, pero no como dataset de cartas.

## Turn phases

`turn-phases.json` define:

1. DRAW
2. ACTION
3. RESOLUTION
4. CLEANUP
5. END

## Gacha

`gacha-rates.json` define:

- SSS 0.05%
- SS 0.15%
- S 0.50%
- A 1.30%
- B 4.00%
- C 24.00%
- D 70.00%

Pity:

- 6 D consecutivos;
- siguiente resultado mínimo C.

## Fórmula de combate declarativa

`combat-formula.json` define:

- base;
- modified;
- critical;
- minimum;
- crit seed;
- element modifiers;
- status modifiers;
- move modifiers;
- seeded randomness.

Multiplicadores documentados:

- strong 1.25
- neutral 1.0
- resist 0.75

## Fórmula ejecutada realmente

El método `combatFormulaResolve()` del Java engine implementa la fórmula declarada.

El método `combatResolve()` implementa una ruta simplificada de combate y es la que utiliza el wrapper TMA actual.

Este es uno de los gaps P0 para cerrar si se busca una sola semántica de combate para todos los clientes.

---

# 2. MATRIZ DE VACÍOS

| Área | Estado | Evidencia | Gap |
|---|---|---|---|
| Java engine | ✅ Implementado | Maven + RuleEngine + JUnit | Solo cubre un subconjunto del gameplay |
| Python aiohttp API | ✅ Implementado | /api/combat/init, /action, /store/invoice | API de combate aún pequeña |
| HMAC TMA | ✅ Implementado | validate_init_data | Debe seguir siendo única autoridad de identidad |
| Telegram Stars | ✅ Implementado | invoice + pre_checkout + successful_payment | Falta ampliar catálogo de productos |
| Persistencia | ✅ Implementado | SQLite + ledger + idempotencia | state_version Java aún 0 |
| WebApp HTML/CSS/JS | ✅ Implementado | 7 archivos | Dependencia fuerte de assets externos aún ausentes |
| Canvas 2D | ✅ Implementado | combat.js | Sin shader GPU |
| CRT | ✅ Implementado | CSS | Efecto puramente visual |
| Screenshake | ✅ Implementado | Canvas JS | Sin assets dedicados |
| Foil holográfico | ✅ Implementado | CSS + orientation | No hay shader real |
| Partículas | ✅ Implementado por código | effects.js | VFX externos todavía 0 |
| Sprites 128×128 | ⚠️ Contrato solamente | manifest 78×3 | 234 referencias, 0 PNG físicos |
| Cartas HD | ⚠️ 1 personaje aprobado | LFS + manifests | Solo Alisa está aprobada |
| Variantes shiny | ⚠️ Lógica solamente | cards.py | Bytes visuales faltantes |
| UR alt holo | ⚠️ Definido | manifests | Producción vacía |
| Armor break / sabun | ❌ No materializado | no assets de ese tipo en tree | Buscar material CC0/original |
| Hit sparks | ❌ | raw/vfx vacío | Falta spritesheet específico |
| Slash sprites | ❌ | raw/vfx vacío | Falta colección promovida |
| Explosion sprites | ❌ | raw/vfx vacío | Falta colección promovida |
| Audio interfaz | ❌ | raw/audio vacío | Sin click/confirm/cancel |
| Audio combate | ❌ | raw/audio vacío | Sin hit/critical/special/victory |
| UI icon packs | ❌ | raw/icons vacío | Sin iconografía física |
| HUD assets externos | ❌ | raw/ui vacío | HUD actual solo CSS/HTML |
| Card dataset | ⚠️ Demo | cards.sample.json | 1 carta, 2 skills |
| Skill dataset | ⚠️ Demo | cards.sample.json | No hay biblioteca real |
| Status dataset | ✅ Contrato | status-effects.json | Falta integrarlo de forma completa al estado durable |
| Relaciones/personajes | ✅/⚠️ | world catalog + character canon | Falta expandir contenido interactivo |
| Scavenger sources | ✅ Manifiesto | scavenger_manifest.json | Descargas declaradas pero raw folders vacíos |
| Provenance | ✅ Contrato | provenance_manifest.json | Debe acompañar cada asset promovido |
| Art progress | ⚠️ Inconsistente | 0 vs 1 completado | Tracker stale |
| Scavenger test | ⚠️ Stale | test espera manifest 1.1.0, manifest actual 1.4.0 | Debe reconciliarse |

## Vacíos especialmente importantes

### P0 — combate

Hay dos caminos de resolución:

`combat.resolve` y `combat.resolve_formula`.

El contrato detallado está documentado y ejecutado por Java, pero el endpoint principal de TMA continúa usando el camino simplificado.

### P0 — assets de combate

El backend exige sprites:

`<id>_{idle|attack|hit}.png`

pero el directorio de producción tiene 0 PNG.

Consecuencia:

- fallback visual;
- no hay identidad gráfica individual durante batalla;
- el cut-in puede depender de cartas HD;
- el runtime no puede entregar una experiencia visual completa de 78 personajes.

### P0 — audio

No existe todavía ningún asset sonoro físico.

### P1 — variaciones visuales

La lógica de cartas contempla:

- normal;
- shiny;
- UR alt holo;
- outfits;
- fusion cards;
- mature gating.

Pero la biblioteca visual materializada todavía no acompaña esa riqueza de reglas.

### P1 — schemas/dataset

Hay contrato robusto, pero solo una carta de ejemplo.

### P1 — Scavenger extraction

El manifiesto tiene descargas CC0 verificadas, pero las carpetas raw están vacías en el árbol auditado.

### P1 — deployment integrity

Las cartas de producción usan Git LFS. La auditoría debe comprobar explícitamente que el pipeline de Pages y los paquetes Windows consumen los objetos LFS reales y no solo los punteros.

---

# 3. LISTA DE BÚSQUEDA PRIORITARIA

Estas búsquedas deben apuntar a recursos redistribuibles, no a ripping de personajes de anime ni a packs cuya licencia impida redistribución.

## 1. Sprites de combate

`"CC0 128x128 transparent pixel battle character sprites idle attack hit"`

Objetivo:

- cerrar el contrato 128×128;
- conseguir material que pueda adaptarse legalmente;
- estudiar poses idle/attack/hit.

## 2. Hit sparks / slash / impact

`"CC0 ヒットエフェクト スプライトシート slash impact transparent PNG"`

Objetivo:

- hit spark dedicado;
- slash;
- impact burst;
- pequeñas explosiones;
- alternativas a partículas 100% procedurales.

## 3. Audio de interfaz

`"CC0 game UI button click confirm cancel selection sound effects WAV OGG"`

Objetivo:

- click;
- hover;
- confirm;
- cancel;
- menu navigation.

## 4. Audio de combate

`"CC0 Kampf Treffer kritischer Treffer Spezialangriff Soundeffekte WAV OGG"`

Objetivo:

- hit;
- critical;
- special;
- victory;
- defeat;
- armor/shield impact.

## 5. HUD / cyberpunk UI

`"CC0 cyberpunk HUD status bar crosshair inventory UI PNG SVG"`

Objetivo:

- retículas;
- barras;
- paneles;
- iconos;
- frames;
- elementos visuales para romper la dependencia exclusiva de CSS.

---

# 4. CONCLUSIÓN ATÓMICA

WaifuMon ya tiene:

- motor Java;
- bridge Python;
- API aiohttp;
- HMAC Telegram;
- combate;
- Stars;
- WebApp;
- Canvas 2D;
- CRT;
- screenshake;
- foil holográfico;
- partículas procedurales;
- contratos JSON;
- gacha;
- estados;
- fases;
- persistencia;
- idempotencia;
- manifests;
- provenance;
- pipeline Scavenger.

Lo que **no** tiene todavía en volumen suficiente es la capa de bytes visuales/sonoros:

- 234 referencias de sprites → 0 PNG reales;
- 78 cartas lógicas → 1 personaje aprobado;
- raw audio → 0;
- raw UI → 0;
- raw VFX → 0;
- raw icons → 0;
- card sample → 1 carta;
- skill sample → 2 skills.

Por tanto, el cuello de botella actual de WaifuMon ya no es principalmente infraestructura: es **contenido visual/audio materializado + unificación semántica del combate + expansión del dataset de cartas/skills**.

## Referencia técnica de la auditoría

Árbol auditado:

`main @ d085646395dc35993fb0f7899bb516fe40b10830`

Esta auditoría es inventario; no considera un asset “presente” solamente porque exista una referencia en un manifest.
