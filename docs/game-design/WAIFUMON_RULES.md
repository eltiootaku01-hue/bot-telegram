# WAIFUMON — reglas técnicas y de diseño

Fecha: 2026-09-21

## 0. Autoridad de reglas

Java es la autoridad de las reglas migradas de gameplay: gacha, combate, progresión y resolución derivada de etapa.

Python conserva validación, orquestación, persistencia, ledger y presentación.

La etapa visual de WaifuMon es una función pura del nivel y no un estado persistente.

## 1. Separación de sistemas

Hay tres conceptos diferentes:

- **Rareza de gameplay:** D, C, B, A, S, SS, SSS.
- **Nivel WaifuMon:** 1 a 30.
- **Tier de carta:** R, S, SR, UR.

No deben utilizarse como sinónimos.

## 2. Nivel y etapa visual

El nivel permitido es exactamente **1..30**.

La etapa se deriva de forma pura:

- nivel 1–10 → etapa 1;
- nivel 11–20 → etapa 2;
- nivel 21–30 → etapa 3.

No existe columna, variable persistente ni requisito de entrada independiente para `evolution_stage`.

Al subir de nivel solo cambia la etapa al cruzar 10→11 o 20→21.

## 3. Gacha

Una tirada cuesta 10 puntos y se registra con un `roll_id` estable.

La protección de mala suerte se mantiene: después de seis resultados D consecutivos, la siguiente tirada D se convierte en C.

Los resultados D/C priorizan candidatos todavía no poseídos cuando existe una alternativa equivalente disponible.

B, A, S, SS y SSS siguen la ruta de aprobación excepcional antes de entregar el personaje.

## 4. Fusión y arte

La fusión de rareza es:

- D → C con 10 copias;
- C → B con 40 copias;
- B → A con 60 copias;
- A → S con 80 copias.

La fusión depende de las copias requeridas y no de un nivel mínimo adicional. Consume las copias necesarias, incrementa una rareza, reinicia nivel a 1 y EXP a 0. La etapa no se escribe; nivel 1 implica etapa 1.

El arte evolutivo usa las mismas tres etapas:

| Nivel | Etapa |
|---|---|
| 1–10 | Etapa 1 |
| 11–20 | Etapa 2 |
| 21–30 | Etapa 3 |

El tier de carta R/S/SR/UR continúa siendo independiente.

No se implementan desnudos, desnudez parcial ni sexualización explícita.

## 4A. Arquitectura visual dual de combate

El sistema de presentación de WaifuMon separa deliberadamente el arte HD de colección y los sprites ligeros de batalla.

### Asset HD — Perfil / Colección

Ruta canónica:

`assets/production/cards/<id>--normal.jpg`

Contrato: JPEG/JPG vertical de **1024 × 1536**.

Se utiliza para:

- visor de colección;
- perfil de WaifuMon;
- gacha;
- inspección;
- selección de equipo.

El arte HD adicional continúa sujeto a la matriz visual y a sus compuertas de elegibilidad/QA.

### Asset de combate — Pixel Art / Chibi

Ruta canónica:

`assets/production/sprites/`

Cada personaje de combate puede aportar:

- `<id>_idle.png` — pose estática;
- `<id>_attack.png` — frame/pose de ataque;
- `<id>_hit.png` — reacción de daño.

Contrato técnico: PNG transparente de **128 × 128 px**.

Los sprites son exclusivamente presentación. No contienen estadísticas ni reglas y no sustituyen a las cartas HD.

### Mini App

La pantalla de selección utiliza cartas HD para formar un equipo de **3 WaifuMons**.

La pantalla de batalla utiliza exclusivamente los sprites Pixel Art/Chibi sobre un canvas HTML5 2D.

Una habilidad especial (`special`) activa un *cut-in* de **1.5 segundos** con la carta HD del personaje y, al terminar, devuelve la interfaz al canvas de sprites.

El *cut-in* es temporal y visual: nunca calcula, modifica ni sustituye el resultado del combate.

### Autoridad del engine

`WaifuMonRuleEngine.java` continúa siendo la única autoridad de cálculo para combate.

El DTO de `combat.resolve` entrega los resultados al frontend, incluyendo:

- acción;
- daño;
- crítico;
- vida restante del defensor.

El frontend solo traduce esos resultados a animaciones y estados visuales. No puede recalcular ni aceptar como autoridad local daño, multiplicadores, precisión o vida restante.

La especificación detallada se conserva en:

`docs/game-design/WAIFUMON_COMBAT_VISUAL_PIPELINE.md`

## 5. Waifu Detector

Cada jugador tiene tres usos diarios por comunidad.

La clave diaria usa la zona horaria de Ciudad Animals.

Cada uso crea una ronda durable con:

- jugador;
- comunidad;
- número de uso;
- waifu elegida;
- mob;
- expiración;
- resultado.

Los mobs son deterministas para el usuario, comunidad, fecha y número de uso. La ronda solo puede resolverse una vez.

Una victoria entrega experiencia a la waifu elegida. Una derrota consume igualmente la oportunidad diaria.

## 6. Regalos de Sunna

Sunna publica un regalo cada seis horas de tiempo del mundo, por lo que existen hasta cuatro slots diarios.

Ejemplos actuales:

- revista de moda: +30 EXP;
- rodaja de pan: +20 EXP;
- postre del Café: +40 EXP;
- fotocarta: +25 EXP.

Cada drop puede ser reclamado por tres personas como máximo.

Cada persona solo puede reclamar una vez el mismo drop.

La reclamación se resuelve en base de datos, no con un contador en memoria.

## 7. Absorción

Los objetos reclamados entran al inventario del jugador.

Para absorber:

1. el jugador abre sus objetos;
2. selecciona un objeto;
3. selecciona una waifu de su colección;
4. se consume exactamente una unidad;
5. la waifu recibe la experiencia correspondiente.

La reducción del inventario es atómica y la operación ocurre dentro de una transacción de escritura.

## 8. Encuentros salvajes

Un encuentro público tiene un máximo de **tres participantes distintos**.

Cada participante dispone de **una sola oportunidad**.

El estado persistido usa `GameAttempt(encounter_id, user_id)` como clave única, así que el mismo usuario no puede pulsar el mismo botón tres veces para conseguir tres recompensas.

Cuando llega el tercer participante:

- se registra su resultado;
- si es correcto, recibe su copia/progresión;
- el encuentro pasa a `closed`;
- los siguientes jugadores reciben "3 oportunidades ocupadas".

El sistema no hace depender la protección del frontend: aunque Telegram repita una callback, la base de datos sigue imponiendo la regla.

## 9. Historia de Ciudad Animals

Las mecánicas son parte del ambiente del Café, no sustituyen el canon de la obra principal.

Sunna utiliza juegos y regalos como puertas de entrada a la pertenencia:

- una partida compartida puede hacer que se quede en la mesa;
- un pequeño regalo puede representar atención cotidiana;
- el Detector es un juego de confianza y aprendizaje, no una traducción literal de su conflicto emocional;
- la evolución de nivel representa progreso jugable, no una declaración automática sobre el arco narrativo del personaje.

La historia de runtime existente mantiene esta separación y termina presentando el Café como un hogar compartido.

## 10. Invariantes de ingeniería

Cada mecánica debe cumplir:

1. estado durable;
2. transición atómica o clave única;
3. límite de uso en la base de datos;
4. respuesta explícita al callback;
5. recompensa idempotente;
6. tolerancia a reinicio;
7. manejo de `retry_after` para publicaciones automáticas;
8. no depender de un LLM para decidir reglas;
9. no convertir una estadística del mundo en canon automáticamente.

## 11. Problemas evitados

La investigación pública de Reddit, GitHub y documentación de Telegram se utilizó como revisión preventiva. Los problemas considerados incluyen:

- pity inexistente o poco claro;
- demasiadas tiradas de poco valor;
- duplicados sin utilidad;
- carreras de reclamación;
- cooldowns invisibles;
- doble cobro;
- doble recompensa;
- callbacks repetidas;
- flooding de Telegram;
- publicaciones duplicadas después de reinicios;
- estados activos que quedan bloqueados tras una expiración.

La investigación completa se conserva en `docs/research/2026-09-21-game-risks/` y `docs/research/2026-09-21-game-and-telegram-risk-research.md`.

## 12. Monetización y referidos en Mini App

La monetización de bienes y servicios digitales dentro de WaifuMon se realizará exclusivamente mediante Telegram Stars (XTR). El frontend de la Mini App no calcula precios finales ni valida pagos: el bot/backend debe crear la factura, atender el flujo de pre-checkout y confirmar el successful_payment antes de entregar el producto. El identificador telegram_payment_charge_id debe conservarse para trazabilidad y posibles reembolsos. Telegram documenta XTR como la moneda obligatoria para pagos de bienes y servicios digitales mediante su Payments API.

### 12.1 Productos in-game

La primera tienda puede exponer, por ejemplo:

- Ticket Premium — ítem consumible para funciones premium de WaifuMon.
- Starter Pack — paquete digital de inicio.

Reglas:
1. El precio y el invoice_payload son autoridad del backend.
2. El cliente web solamente solicita/inicia la compra; nunca acredita el producto por sí mismo.
3. Una compra confirmada debe ser idempotente por telegram_payment_charge_id y/o por una referencia interna única.
4. Una respuesta de pago fallida, cancelada o no validada no entrega ningún recurso.
5. El ledger de monetización debe conservar usuario, producto, cantidad de Stars, payload interno, charge ID, fecha y estado.

### 12.2 Referidos propios de WaifuMon

Se añade un programa simple de crecimiento:

**3 usuarios nuevos validados = 1 Ticket Premium.**

Un referido cuenta solamente cuando el backend confirma que:

- el usuario referido es nuevo para este programa;
- el enlace/parámetro de referencia pertenece a un invitador válido;
- la relación invitador → referido todavía no fue registrada;
- el nuevo usuario completó la condición de activación definida por el backend (por defecto, abrir la Mini App y completar la inicialización del perfil).

La concesión del tercer referido debe ser atómica e idempotente. La misma persona invitada no puede generar dos veces la recompensa para el mismo invitador.

La Mini App puede mostrar progreso (0/3, 1/3, 2/3, 3/3) y ofrecer un botón de compartir, pero no puede declararse a sí misma como dueña de la recompensa. El servidor debe calcular y devolver el contador/recompensa.

### 12.3 Parámetros de referencia

Para el programa propio puede utilizarse un parámetro de referencia en el deep link del bot/Mini App. El valor recibido en el cliente se considera no confiable hasta que el backend valide la identidad de Telegram mediante initData. Telegram advierte expresamente que initDataUnsafe no debe tratarse como fuente confiable.

Telegram también dispone de Affiliate Programs para Mini Apps, donde un creador o usuario puede recibir una comisión en Stars por compras realizadas por personas referidas. Ese mecanismo es distinto del programa interno 3 referidos = 1 Ticket Premium; ambos pueden coexistir, pero no deben mezclarse en el mismo ledger de recompensas.

### 12.4 UI estática

La Mini App de webapp/ implementa:

- interfaz mobile-first;
- adaptación al tema actual de Telegram;
- tienda visual preparada para productos digitales;
- indicador de referidos;
- botón de compartir;
- advertencia de que pago y recompensa son funciones server-side;
- Canvas 2D para combate;
- cut-in temporal de 1.5 segundos con carta HD.

La interfaz se mantiene libre de framework y dependencias de build para reducir tamaño, coste y carga en hardware modesto. Telegram recomienda diseños móviles, rápidos, adaptados a los colores dinámicos del cliente y respetuosos del área segura.

### 12.5 Despliegue

webapp/ se publica como artefacto estático mediante .github/workflows/deploy-pages.yml en cada push a main. GitHub Pages soporta este patrón mediante configure-pages, upload-pages-artifact y deploy-pages; el repositorio debe tener GitHub Pages configurado para usar GitHub Actions como fuente.

Las referencias documentales utilizadas para esta sección son la documentación oficial de Telegram Mini Apps/Payments/Affiliate Programs y la documentación oficial de GitHub Pages.
