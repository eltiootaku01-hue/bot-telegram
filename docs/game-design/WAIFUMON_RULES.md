# WAIFUMON — reglas técnicas y de diseño

Fecha: 2026-09-21

## 1. Separación de sistemas

Hay tres ejes diferentes y no deben mezclarse:

- **Rareza de gameplay:** D, C, B, A, S, SS, SSS.
- **Nivel de la waifu:** 1 a 25.
- **Clase de carta:** R, SR, UR.

La rareza decide principalmente disponibilidad y requisitos de evolución. El nivel determina la progresión de poder/arte. La clase de carta identifica una presentación especial de la misma waifu.

## 2. Gacha

Una tirada cuesta 10 puntos.

Cada tirada queda registrada en `game_gacha_rolls` con un `roll_id` estable. Repetir el mismo callback no debe crear otra tirada ni volver a cobrar.

La mala suerte tiene una protección suave: después de seis resultados D consecutivos, el siguiente resultado D se convierte en C. El contador se guarda en el perfil.

Los resultados D/C intentan priorizar personajes todavía no poseídos cuando existen candidatos equivalentes disponibles. Así, un duplicado sigue siendo posible, pero el sistema evita convertir las primeras tiradas en una repetición sin utilidad.

B, A, S, SS y SSS siguen una ruta de aprobación excepcional antes de entregar el personaje.

## 3. Colección y progreso

Cada waifu de una colección tiene:

- nivel 1..25;
- experiencia;
- copias;
- rareza;
- etapa de evolución.

Las copias adicionales no desaparecen: aumentan la colección y la progresión.

La evolución normal solo está permitida cuando la waifu alcanza **nivel 25** y se utiliza la misma identidad de personaje.

Reglas actuales de copias:

- D → C: 10 copias.
- C → B: 40 copias.
- B → A: 60 copias.
- A → S: 80 copias.

La fusión es una transición SQL condicional. Dos clicks simultáneos no pueden evolucionar la misma fila dos veces.

## 4. Arte y presentación

La progresión visual implementada es deliberadamente no explícita:

| Nivel | Presentación |
|---|---|
| 1–5 | chibi, ropa cotidiana, cabeza y hombros |
| 6–10 | anime, ropa cotidiana, medio cuerpo |
| 11–15 | anime, atuendo temático, cuerpo completo |
| 16–20 | anime premium, vestuario especial de evento |
| 21–25 | anime premium, vestuario de forma final |

Las clases mantienen la misma identidad del personaje:

- R: versión base.
- SR: variante especial de profesión/evento.
- UR: variante especial con escena/efectos exclusivos.

No se implementan desnudos, desnudez parcial ni sexualización explícita. La etapa superior sigue siendo una versión premium del personaje con vestuario definido.

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
