# WaifuMon — evolución, arte y especialidades de combate

Fecha: 2026-09-21

## Regla principal

La **clase WaifuMon** representa la evolución de la criatura que el jugador posee.

Es independiente de:

- la rareza de obtención/combatiente D, C, B, A, S, SS, SSS;
- el tier visual/coleccionable de una carta R, S, SR, UR;
- la popularidad del personaje;
- el poder de balance del catálogo.

La clase evolutiva usa el nivel de la colección:

| Nivel global | Clase | Significado |
|---|---|---|
| 1–10 | R | monstruo/waifumon novato |
| 11–20 | S | primera evolución |
| 21–30 | SR | evolución avanzada |

La promoción ocurre al conseguir el siguiente nivel. Un R Lv.10 pasa a S Lv.11; un S Lv.20 pasa a SR Lv.21.

## Arte evolutivo

Cada clase exige una ilustración distinta.

### R — novata

- visible aproximadamente 20%;
- rostro, cuello y hombros pequeños;
- silueta cerrada;
- vestuario sencillo;
- expresión que presente la personalidad;
- sensación de criatura recién obtenida.

Archivo canónico esperado:

`assets/waifus/<character_id>--r.jpg`

### S — primera evolución

- visible aproximadamente 45%;
- cabeza, hombros, torso y parte de la cintura;
- nuevo vestuario, accesorio, armadura o detalle relacionado con su especialidad;
- pose más segura;
- silueta claramente distinta de R;
- iluminación superior.

Archivo:

`assets/waifus/<character_id>--s.jpg`

### SR — evolución avanzada

- visible aproximadamente 70–80%;
- medio cuerpo amplio hasta cintura o muslos;
- arte premium;
- pose de combate o pose icónica;
- efectos y escenario narrativo;
- vestuario de forma avanzada;
- silueta mucho más abierta que S.

Archivo:

`assets/waifus/<character_id>--sr.jpg`

### UR

UR no es una cuarta evolución automática.

UR continúa siendo la clase especial de **fusión de dos cartas base**. Su arte es una composición independiente y puede utilizar cuerpo completo.

## Estadísticas

Todos los personajes comparten una base por clase, pero cada WaifuMon recibe una especialidad.

La jerarquía fundamental es:

`R Lv.10 < S Lv.11 < SR Lv.21`

para las estadísticas generales.

S está diseñado para comenzar por encima de un R al final de su etapa, mientras permanece por debajo de la entrada de SR.

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

Ejemplos:

- aire: velocidad y movilidad;
- tierra: vida máxima y defensa;
- fuego: especial y daño de fuego;
- agua: curación;
- neutro: fuerza bruta y algo de defensa;
- hielo: control y poder especial;
- luz: soporte/curación secundaria;
- oscuridad: crítico;
- rayo: explosión de daño + velocidad;
- mente: precisión + crítico;
- arcano: poder especial.

La asignación por elemento es un valor inicial del sistema y puede evolucionar posteriormente hacia una especialidad explícita por personaje cuando exista suficiente diseño.

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
