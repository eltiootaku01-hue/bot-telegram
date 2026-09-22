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
