# WaifuMon — evolución, arte y especialidades de combate

Fecha: 2026-09-21

## Regla canónica de nivel

El nivel de una WaifuMon es un valor durable de **1 a 30**.

La etapa visual no es un estado independiente. Se deriva siempre y únicamente del nivel:

| Nivel | Etapa visual |
|---|---|
| **1–10** | **Etapa 1** |
| **11–20** | **Etapa 2** |
| **21–30** | **Etapa 3** |

La función `evolution_stage_for_level(level)` implementa esta relación como función pura. SQLite no guarda una columna de etapa.

## Fusión de rareza

La fusión de gameplay es independiente de la etapa visual.

| Rareza actual | Rareza nueva | Copias consumidas |
|---|---|---:|
| D | C | 10 |
| C | B | 40 |
| B | A | 60 |
| A | S | 80 |

La fusión:

1. consume las copias requeridas;
2. incrementa exactamente una rareza;
3. fija el nivel en **1**;
4. fija la EXP en **0**;
5. no escribe ninguna etapa visual;
6. por consecuencia de nivel 1, la etapa resultante es **Etapa 1**.

No existe una regla de nivel mínimo adicional en esta fusión.

## Arte evolutivo

El arte evolutivo usa tres etapas derivadas del nivel:

### Etapa 1 — niveles 1–10

`assets/production/cards/<character-id>--stage1.jpg`

### Etapa 2 — niveles 11–20

`assets/production/cards/<character-id>--stage2.jpg`

### Etapa 3 — niveles 21–30

`assets/production/cards/<character-id>--stage3.jpg`

Cada archivo de producción debe ser JPEG exacto de **1024×1536** y aprobar el validador.

La ausencia de un archivo aprobado nunca activa un fallback visual genérico.

## Rareza, carta y etapa son conceptos distintos

Una ficha puede mostrar:

`Carta: SR`
`Rareza de combate: A`
`Nivel: 21`
`Etapa visual: 3`
`Elemento: agua`

Cada dato responde a una regla diferente.

## Estadísticas

Las estadísticas de combate siguen siendo calculadas por el motor Java a partir de nivel, rareza, elemento, poder de catálogo y potencial.

El nivel 30 es el máximo. Un nivel superior es inválido y debe fallar cerrado.

## Especialidades

La especialidad se deriva inicialmente del elemento:

| Elemento | Especialidad |
|---|---|
| aire | velocidad |
| tierra | dureza |
| fuego | habilidad de fuego |
| agua | curación |
| neutro | fuerza bruta |
| hielo | control |
| luz | soporte |
| oscuridad | golpe crítico |
| rayo | ataque explosivo |
| mente | precisión |
| arcano | poder arcano |

Cada especialidad aumenta una familia principal de estadísticas, pero nunca deja las restantes en cero.

## Relación entre evolución y combate

La clase no solamente cambia el dibujo.

El nivel alimenta las estadísticas y esas estadísticas participan en el poder del Waifu Detector.

Por eso:

- subir de R a S cambia el arte;
- subir de S a SR cambia nuevamente el arte;
- subir de nivel aumenta las estadísticas;
- la especialidad cambia la forma en que crece el poder;
- una waifumon de agua y otra de tierra pueden tener el mismo nivel pero resolver combates de formas distintas.

## Diseño de cartas

No se debe usar la escala R/S/SR de cartas para describir automáticamente la evolución de una criatura.

Una ficha puede mostrar simultáneamente:

`Carta: SR`
`WaifuMon: S`
`Rareza de combate: A`
`Elemento: agua`
`Especialidad: curación`

Cada dato responde a una pregunta diferente.

## Objetivo visual

La evolución debe sentirse visible incluso sin leer las estadísticas:

`R → S`: "ahora tiene identidad de combatiente"

`S → SR`: "ahora tiene presencia de personaje avanzado"

La diferencia debe lograrse mediante:

- encuadre;
- vestuario;
- pose;
- accesorios;
- efectos;
- escenario;
- expresión;
- silueta.

No debe depender solamente de hacer la misma imagen más brillante.

## Estado actual del arte

El catálogo contiene 78 personajes jugables.

El manifiesto existente registra 17 artes de personaje terminadas de la colección base (21,79%). Esas piezas son activos de catálogo y no significan que las tres etapas R/S/SR estén terminadas para esos personajes.

La implementación de este documento ya puede resolver la etapa correcta y buscar automáticamente el asset correspondiente. La producción de las cadenas completas R→S→SR sigue siendo trabajo artístico pendiente.
