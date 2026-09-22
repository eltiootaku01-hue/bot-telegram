# WaifuMon — extracción de arquitecturas de combate (2026-09-22)

Este documento resume patrones encontrados en proyectos abiertos y los convierte en
reglas propias de WaifuMon. No contiene bases de datos de cartas, personajes o
archivos completos copiados de terceros.

## 1. Patrones capturados

### Pokémon Showdown / poke-engine

Los motores revisados separan el cálculo en capas:

1. estadísticas del atacante/defensor;
2. potencia base de la acción;
3. modificadores de estado/tipo;
4. crítico;
5. aleatoriedad controlada;
6. aplicación final del daño.

Una referencia explícita de Pokémon Showdown muestra la estructura del daño base:

`int(int(int(2 * level / 5 + 2) * basePower * attack / defense) / 50)`

y después la aplicación de modificadores. También mantiene por separado `typeMod`,
`crit` y el randomizador. La implementación propia de WaifuMon conserva la
separación conceptual, pero usa números propios y semillas deterministas.

### RPG Maker MV/MZ

El patrón de base de datos útil es declarativo:

- `Actors.json`
- `Enemies.json`
- `Skills.json`
- `States.json`
- `Troops.json`

Las bases de datos son arrays posicionales y las skills almacenan una expresión
de daño. WaifuMon no ejecuta JavaScript arbitrario: el contrato propio usa
campos tipados y enumera efectos.

### HearthClone / TCG-Engine

Los motores revisados separan fases, triggers y estados:

- fase de acción;
- resolución;
- cola de triggers;
- procesamiento de muertes;
- final de turno.

Esto se adopta como un modelo conceptual para futuras batallas WaifuMon, sin
copiar clases ni tablas de cartas.

## 2. Esquema normalizado propio

Cada personaje jugable puede representarse como:

- `card_id`: identificador estable;
- `name`: nombre visible;
- `base_atk`: ataque base;
- `base_def`: defensa base;
- `element_type`: elemento;
- `skills`: acciones declarativas;
- `status_effects`: estados que puede aplicar.

## 3. Fórmula propia de WaifuMon

Para ataques con estadísticas explícitas:

`base = floor((2 * level / 5 + 2) * skill_power * attack / max(1, defense) / 10)`

`modified = floor(base * element_multiplier * status_multiplier * move_multiplier)`

Si hay crítico:

`final = floor(modified * crit_multiplier)`

En ausencia de crítico:

`final = max(damage_floor, modified)`

La aleatoriedad no se obtiene del reloj ni de Math.random: cualquier variación debe
derivarse de una semilla de turno.

## 4. Contrato de crítico

- `crit_rate` está en 0..100.
- `crit_multiplier` normalmente es 1.5.
- La tirada se deriva de SHA-256 de la semilla de turno + atacante + defensor.
- La resolución es reproducible.

## 5. Elementos

El motor no impone una tabla Pokemon. WaifuMon utiliza una matriz pequeña y
explicable:

- super_weak = 1.50
- weak = 1.25
- neutral = 1.00
- resist = 0.75
- strong_resist = 0.50

La matriz concreta debe vivir en configuración propia de WaifuMon.

## 6. Estados

Los estados son datos, no código arbitrario:

- `poison`: DoT porcentual por turno;
- `bleed`: DoT físico reducido por defensa;
- `stun`: impide una acción durante un turno;
- `shield`: absorbe daño antes del HP.

Cada estado tendrá duración, potencia, acumulación máxima y momento de resolución.

## 7. Gacha

El motor actual ya usa una tabla propia determinista:

SSS 0.05%
SS  0.15%
S   0.50%
A   1.30%
B   4.00%
C  24.00%
D  70.00%

y un pity propio: después de 6 resultados D consecutivos, el séptimo se fuerza a
C. Esta tabla es una regla de WaifuMon, no una extracción de datos de otro juego.

## 8. Protección de propiedad intelectual

Se reutilizan ideas de arquitectura y matemáticas genéricas; no se incorporan
bases de datos completas, assets de personajes o textos largos de terceros.


## 8. Fuentes externas rastreadas

### Pokémon Showdown / Smogon

Repositorio y calculadora:
- https://github.com/smogon/pokemon-showdown
- https://github.com/smogon/damage-calc

Patrones útiles observados:
- separación entre cálculo base, crítico, modificadores, efectividad de tipo y daño final;
- datos de especie/movimiento/condiciones separados de la lógica del simulador;
- randomización y crítico resueltos como etapas distintas;
- efectos de estado modelados como condiciones con hooks de ciclo de turno.

Referencia matemática concreta usada solo como comparación:
- Gen 2 calcula el daño a partir de nivel, potencia, ataque y defensa y luego aplica crítico, clima, STAB y efectividad.
- En el pipeline moderno, el crítico se aplica por separado, después se procesa el randomizador, STAB y efectividad.

**Decisión WaifuMon:** no copiar la tabla de tipos ni la fórmula completa de Pokémon. Se conserva solamente la idea de pipeline por etapas y se usa una fórmula propia documentada arriba.

### YGOJSON / datos de cartas Yu-Gi-Oh!

Fuentes:
- https://github.com/iconmaster5326/YGOJSON
- https://github.com/byi8220/duellinksjson
- https://github.com/arshtyi/ygo-cards

Campos observados en registros JSON:
- identificador;
- nombre;
- texto/efecto;
- tipo de carta;
- tipo de monstruo;
- especie;
- ATK;
- DEF;
- nivel;
- atributo;
- rareza;
- límite;
- origen/conjunto.

**Normalización WaifuMon:**
`card_id`, `name`, `base_atk`, `base_def`, `element_type`, `skills`, `status_effects`.

El proyecto local no incorpora una copia masiva de esas bases de datos. El esquema JSON propio solamente modela los conceptos necesarios para el juego.

### RPG Maker MV/MZ

Fuentes:
- https://github.com/nightquill/rpgmaker-agent-skills
- https://github.com/3nginius/RuneTranslatePublic
- https://github.com/JaimeDevCode/RPGMakerTranslator

Patrones observados:
- `Actors.json`, `Enemies.json`, `Skills.json`, `States.json`, `Troops.json` como datos declarativos;
- una skill puede contener tipo de daño, objetivo, costes, efectos y una fórmula;
- los estados representan efectos persistentes con reglas de duración/resolución.

Una referencia de RPG Maker documenta fórmulas expresadas con variables como `a.atk`, `a.mat`, `b.def` y funciones como `Math.max`.

**Decisión WaifuMon:** no evaluar JavaScript arbitrario. Las skills se representan como datos tipados y la fórmula se ejecuta únicamente en el motor Java.

### Hearthstone-clone / TCG

Fuente de referencia abierta:
- https://github.com/EnginKARATAS/hearthstone-clone-game
- https://github.com/tducasse/poc-card-game

Patrones observados:
- estado persistente del turno;
- jugador/oponente con mazo, mano, tablero y héroe;
- recurso por turno;
- robo de carta al iniciar turno;
- elección de acción;
- resolución de interacciones;
- botón/acción de final de turno.

**Decisión WaifuMon:** el archivo `turn-phases.json` adopta una máquina de fases propia:
DRAW → ACTION → RESOLUTION → CLEANUP → END.

### M.U.G.E.N / CNS

Fuentes:
- https://github.com/fanyer/mugen/blob/master/chars/kfm/kfm.cns
- https://github.com/fanyer/mugen/blob/master/docs/cns.html
- https://github.com/fakoli/FightersParadise/blob/main/docs/mugen-compatibility.md

Patrones observados:
- sección `[Data]` para vida, ataque y defensa;
- `[Statedef]` para el estado de una acción;
- `HitDef` para daño, hit/guard flags, prioridad, pausas, tiempos de golpe y velocidades;
- controladores separados para transiciones y efectos;
- multiplicadores de ataque/defensa como parte del estado del luchador.

**Decisión WaifuMon:** esos conceptos se convierten en atributos tipados de personaje/skill/estado, pero no se reutilizan archivos CNS ni personajes completos.

## 9. Matriz de extracción → implementación

| Fuente | Qué se reutiliza conceptualmente | Qué NO se copia |
|---|---|---|
| Pokémon Showdown | pipeline de daño y separación de modificadores | fórmula completa de una generación, tabla de tipos, datos Pokémon |
| YGOJSON | estructura de registros de cartas | base de datos de cartas, textos, imágenes |
| RPG Maker | esquema declarativo de skills/estados | JavaScript ejecutable de fórmulas y bases de datos de juegos |
| Hearthstone clones | fases de turno, recursos, mano/mazo/tablero | cartas, assets, texto, lógica específica del clon |
| M.U.G.E.N | Data/State/HitDef y separación de controladores | personajes, CNS completos, assets y contenido de combate |

## 10. Correcciones de contrato realizadas durante el rastreo

El esquema JSON define `element_type` como el nombre canónico. Se corrigió el bridge Python→Java y `stats.resolve` para utilizar ese campo; los tests también lo exigen.

El bridge Java ofrece además wrappers async en la fachada Python para evitar bloquear el event loop de Telegram durante llamadas al proceso Java.

## 11. Regla de proveniencia

Las fuentes externas sirven para arquitectura, terminología y comparación matemática.
Las reglas que gobiernan WaifuMon son exclusivamente las presentes en
`engine/waifumon/src/main/java/com/eltiootaku01/waifumon/WaifuMonRuleEngine.java`
y sus recursos JSON.

No se importan automáticamente personajes, cartas, textos, assets ni fórmulas propietarias de terceros.


## 12. Fórmulas y estructuras capturadas con mayor precisión

### Pokémon Showdown / damage-calc

La familia moderna de fórmulas usa una base del tipo:

`baseDamage = floor(floor(floor((2 * Level / 5 + 2) * Power * Attack / Defense) / 50) + 2)`

y después aplica modificadores como objetivo múltiple, clima, crítico, aleatoriedad, STAB, efectividad y otros efectos de la generación. El propio calculador separa explícitamente cálculo de potencia, ataque, defensa, daño base y modificadores finales.

Fuentes:
- https://github.com/smogon/pokemon-showdown/blob/master/sim/battle-actions.ts
- https://github.com/smogon/pokemon-showdown/blob/master/sim/battle.ts
- https://github.com/smogon/damage-calc/blob/master/calc/src/mechanics/gen789.ts

**Conversión WaifuMon:** se conserva el pipeline y el uso de enteros/rounding por etapas, pero se cambia la constante final y los modificadores para que sean reglas originales del proyecto. La fórmula actual está formalizada en `combat-formula.json` y ejecutada por Java.

### RPG Maker

Un `Skill` serializado puede contener:
- `damage.formula`;
- tipo de daño;
- elemento;
- varianza;
- crítico;
- repeticiones;
- objetivo;
- costes;
- `effects[]`.

Un `State` mantiene duración/condiciones de retirada y puede modificar cómo se comporta un actor durante el combate.

Fuentes:
- https://github.com/Apress/beg-rpg-maker-mv/blob/master/9781484219669/9781484219669_Ch3/Chapter%203/data/Skills.json
- https://github.com/tonbijp/RPGMakerMZ/blob/master/Reference/Game_Action.md
- https://github.com/DKPlugins/DK-Doctor/blob/main/docs/rpgmaker-format-spec.md

**Conversión WaifuMon:** no se ejecuta JavaScript arbitrario. `skill_effect` es un objeto tipado y cada estado tiene un `status_id`, duración y resolución controlada por el engine.

### M.U.G.E.N

El ejemplo KFM muestra:
- `[Data]`: vida, ataque, defensa y parámetros persistentes;
- `[Statedef]`: tipo de estado, física, control y animación;
- `HitDef`: daño, guard damage, prioridad, ventanas, hit/guard flags y comportamiento tras recibir el golpe.

Fuentes:
- https://github.com/fanyer/mugen/blob/master/chars/kfm/kfm.cns
- https://github.com/fanyer/mugen/blob/master/docs/cns.html

**Conversión WaifuMon:** esos conceptos se reducen a `Character`, `Skill`, `CombatState` y `StatusEffect`; no se incorpora el engine M.U.G.E.N ni contenido de KFM. La licencia del entorno M.U.G.E.N tiene restricciones de uso comercial, por lo que el repositorio de WaifuMon no depende de sus binarios o assets.

### TCG / Hearthstone-like

Un clon abierto sencillo separa:
- comienzo de partida;
- draw phase;
- play phase;
- use phase;
- ending condition.

Otro clon documenta recursos por turno, robo y botón de final de turno, además de efectos tipados como daño, curación, robo, armadura y empowerment.

Fuentes:
- https://github.com/weepingwitch/cardgame
- https://github.com/EnginKARATAS/hearthstone-clone-game
- https://github.com/oyachai/HearthSim

**Conversión WaifuMon:** la máquina propia queda:
DRAW → ACTION → RESOLUTION → CLEANUP → END,
con una cola conceptual de triggers y un único commit de estado al cerrar el turno.
