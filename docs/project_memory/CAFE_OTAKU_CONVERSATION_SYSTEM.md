# Café Otaku — Sistema de conversación, sketches y activación

> Documento de memoria de diseño. No constituye todavía una implementación runtime.
> Fuente principal: decisiones y aclaraciones del usuario durante el diseño del Café Otaku.

## 1. Principio general

Café Otaku no debe tratar a cada mesera como una IA residente permanente.

Las meseras son personajes ficticios con personalidad, conocimientos, estados, relaciones, acciones y lore. La mayor parte de la actividad cotidiana debe poder ejecutarse mediante reglas, estados, plantillas, eventos y libretos. La Web IA se utiliza cuando una interacción necesita flexibilidad, información o improvisación que el sistema local no puede resolver.

Regla conceptual:

**mínima capacidad necesaria para cada acción.**

- conversación sencilla → reglas/respuestas locales;
- sketch o evento preparado → libreto + contexto;
- interacción compleja → Web IA;
- Web IA no necesaria → no se activa.

## 2. Personalidad de las meseras

La personalidad de trabajo es la principal durante la actividad normal del Café.

No debe confundirse con una segunda personalidad artificial.

Ejemplo conceptual de Cari:

- faceta habitual: mesera otaku, profesional, conversadora y con conocimiento de anime adquirido para su trabajo;
- personalidad real: chica activa a la que le gusta moverse y que no necesariamente disfruta todo el anime que debe estudiar;
- de los animes estudiados para mantenerse al día, solo algunos pueden gustarle realmente;
- sus preferencias personales pueden concentrarse, por ejemplo, en ciertos shōnen con los que se identifica.

La personalidad real aparece rara vez como un **gap moe / ruptura aparente del personaje**. Para el usuario puede parecer que la mesera «rompió personaje» y mostró algo auténtico. Internamente es una transición controlada del estado/persona, no una segunda IA.

## 3. Web IA y prompts temporales

La Web IA NO debe conservar permanentemente un prompt gigantesco con toda la identidad de una mesera.

El Café Otaku posee la información persistente.

Antes de cada llamada se construye un contexto temporal específico para la acción:

**personaje + rol + rasgos relevantes + estado + memoria necesaria + sketch + situación + mensaje del usuario + restricciones.**

La Web IA recibe solo lo necesario para resolver el evento.

Después de obtener la respuesta:

1. se valida la respuesta;
2. se conserva únicamente la información que deba entrar en memoria/lore/estado;
3. se descarta el prompt temporal.

### Regla crítica

El prompt temporal debe ser suficientemente completo para evitar huecos como:

- «¿quién es Sunna?»;
- «¿qué relación tiene con Cari?»;
- «¿qué estaba ocurriendo?»;
- «¿por qué Cari reaccionaría así?»;
- «¿qué sabe realmente este personaje?».

No debe obligar a la Web IA a inventar identidad, relaciones o antecedentes.

## 4. Sketches

Los sketches son mini-escenas reutilizables, similares a pequeños capítulos.

Puede existir una biblioteca de miles de sketches sin que miles de procesos estén ejecutándose.

Un sketch puede contener:

- participantes;
- tema;
- contexto;
- antecedentes;
- objetivo de la escena;
- variantes;
- posibles interrupciones;
- posibles respuestas;
- consecuencias;
- recuerdos que deben conservarse;
- estado (pendiente, activo, pausado, terminado).

Los sketches pueden cruzarse entre sí y tocar varios temas.

## 5. Conversaciones entre meseras

Las meseras pueden ejecutar sketches entre ellas aunque ningún cliente esté hablando con ellas.

Ejemplo conceptual:

Cari y otra compañera conversan sobre un anime, un juego, una partida, cartas, rumores del café, acontecimientos anteriores, etc.

No debe ser un diálogo aleatorio sin contexto.

Una referencia a algo anterior solo es válida si el sistema posee ese antecedente.

Ejemplo inválido:

> —Sí, pero el protagonista me cae mal.
>
> —¿Otra vez?

El «otra vez» exige un antecedente que no fue establecido.

Ejemplo válido:

- ayer Cari dijo que le gustaba el protagonista;
- en el episodio nuevo el protagonista hizo algo que la molestó;
- la compañera estuvo presente;
- el sketch actual continúa ese contexto.

Entonces una reacción como «¿otra vez?» sí puede ser coherente.

## 6. Contexto pasado y contexto no presenciado

El Café puede tener continuidad aunque el usuario no haya presenciado una conversación.

Una charla de hoy puede referirse a algo ocurrido ayer.

Un usuario nuevo puede no entender inmediatamente el contexto; eso NO es necesariamente un error si el antecedente existe en la memoria del mundo.

Si el usuario pregunta, el personaje puede recuperar el antecedente real.

No se debe fabricar un recuerdo inexistente para hacer que la escena parezca profunda.

## 7. Interrupción por un cliente

Una mecánica importante:

1. dos meseras ejecutan un sketch;
2. un cliente llama a una de ellas;
3. el sketch se pausa;
4. se guarda el contexto de la escena;
5. la mesera atiende al cliente;
6. el sistema determina si puede responder localmente o necesita Web IA;
7. si usa Web IA, se construye un prompt temporal;
8. la mesera responde como personaje;
9. el sketch puede continuar, quedar pausado o terminar según sus reglas.

Ejemplo de contexto temporal:

- Cari estaba en un sketch con una compañera de trabajo;
- estaban hablando de un tema concreto;
- el cliente interrumpió;
- la compañera se fue a limpiar una mesa;
- el cliente pregunta de qué hablaban.

La Web IA debe recibir ese contexto explícitamente.

## 8. Capacidad variable de respuesta

No todas las interrupciones necesitan Web IA.

Puede haber dos rutas principales:

### Ruta A — contexto suficiente

La Web IA recibe contexto suficiente y genera una respuesta coherente, pudiendo continuar la conversación y generar una pregunta o devolución natural.

### Ruta B — memoria/capacidad insuficiente o momento de alta demanda

El sistema utiliza una respuesta de contingencia diegética.

Ejemplo conceptual:

> —Es... se cre...to... por favor tome esto y no le diga al jefe que nos vio, ¿vale? ¡Bye!

Después puede ocurrir un pequeño evento del Café:

**+5 puntos del Café**

Esto convierte una limitación técnica o falta de contexto en contenido del mundo, en lugar de producir una respuesta incoherente.

## 9. Personalidad específica por personaje

La misma situación no debe producir necesariamente la misma conducta en todas las meseras.

Cada personaje puede tener:

- tolerancia distinta;
- tendencia a guardar secretos;
- franqueza;
- humor;
- paciencia;
- conocimientos;
- gustos;
- forma de reaccionar ante interrupciones;
- relación con cada compañera;
- probabilidad de continuar o revelar un sketch.

Ejemplo conceptual: Cami puede ser mucho menos indulgente y «no perdonar nada», pudiendo corregir o revelar algo que Cari intentaría ocultar.

## 10. Activación y descanso

Las meseras NO necesitan permanecer activas permanentemente.

Estados conceptuales:

- ACTIVA;
- OCIOSA;
- CONVERSANDO;
- JUGANDO;
- TRABAJANDO;
- DESCANSANDO;
- DESACTIVADA;
- PAUSADA por interrupción.

Una escena puede pasar de:

**ACTIVAR → EJECUTAR → PAUSAR/TERMINAR → DESCANSAR**

Esto permite que el Café parezca poblado y activo sin mantener todas las capacidades pesadas funcionando al mismo tiempo.

Miles de sketches almacenados son datos; no equivalen a miles de procesos activos.

## 11. Actividad ambiental

El Café puede aparentar actividad continua mediante eventos discretos:

- una mesera inicia una conversación;
- otra prepara una trivia;
- alguien comienza una partida;
- se realiza un sorteo de cartas;
- una mesera comenta un episodio;
- una actividad termina;
- otra mesera pasa a descansar;
- un nuevo evento se selecciona.

La simulación debe ser episódica y bajo demanda, no un conjunto de IAs residentes.

## 12. Memoria y continuidad

Debe distinguirse:

- contexto inmediato;
- memoria persistente del Café;
- conocimiento del personaje;
- conocimiento profesional adquirido;
- preferencias personales;
- contexto de un sketch;
- eventos del mundo;
- información desconocida.

«Conocer» y «gustar» son atributos diferentes.

Ejemplo: Cari puede conocer diez series porque las estudió para trabajar y realmente disfrutar solo dos.

## 13. Regla de continuidad

**Un personaje no debe hacer referencia a un acontecimiento que el contexto disponible no justifique.**

Si una referencia apunta al pasado:

- el antecedente debe existir;
- debe ser accesible según la memoria del personaje/mundo;
- la escena puede ocultarlo al usuario si eso forma parte del sketch;
- pero el sistema no debe inventarlo retrospectivamente.

## 14. Objetivo futuro del sistema de prompts

Cuando el BOT-IA/Café Otaku llegue a la fase de implementación de personajes y Web IA, los prompts deben diseñarse y probarse como componentes formales.

Cada prompt temporal debe responder como mínimo:

- quién es el personaje;
- cuál es su rol actual;
- con quién está interactuando;
- qué sabe;
- qué no sabe;
- qué ocurrió inmediatamente antes;
- qué recuerdos son relevantes;
- qué sketch/evento está activo;
- qué acaba de decir el usuario;
- qué objetivo tiene la acción;
- qué restricciones debe respetar;
- qué debe hacer si falta contexto.

No asumir identidad, relaciones, memoria o antecedentes que no hayan sido proporcionados por el Context Builder.

## 15. Estado de implementación

Este documento conserva el diseño conceptual acordado.

No afirma que todo lo anterior esté implementado actualmente.

La implementación deberá comprobarse mediante código, pruebas y evidencia de runtime antes de marcar una característica como implementada.
