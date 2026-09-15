# Base de comportamiento: maid y tiendas japonesas

Fecha de referencia: 2026-09-15

Este documento es una **base de diseño conductual para Ciudad Animals y el Café Otaku**. No pretende copiar diálogos de anime, manga, novelas visuales o wikis. Las descripciones son redacción original y deben usarse como reglas de comportamiento, ambientación y repertorio.

## Objetivo

Dar al sistema una biblioteca de comportamientos reutilizables para:

- maids de café y personal de atención;
- tiendas japonesas temáticas;
- protocolos de bienvenida, servicio y despedida;
- pequeños gestos y rutinas que hagan que el mundo parezca vivo;
- ambientación que Cari, Chie y Tío Otaku puedan usar sin necesitar IA generativa.

## Principios de actuación

| ID | Patrón | Comportamiento base |
| --- | --- | --- |
| maid-welcome | bienvenida | saluda, reconoce la llegada y ofrece ayuda sin interrogar demasiado |
| maid-seat | asignación de mesa | indica una mesa o zona y comprueba si falta algo |
| maid-menu | menú | presenta opciones de forma clara y amable |
| maid-order | pedido | repite el pedido para confirmar y evita inventar artículos inexistentes |
| maid-check | verificación | comprueba disponibilidad antes de prometer un producto |
| maid-service | servicio | prioriza pedidos pendientes y mantiene un tono cordial |
| maid-thanks | agradecimiento | agradece la visita y cierra la interacción de forma breve |
| maid-farewell | despedida | invita a volver sin presión |
| maid-clean | orden | después de un servicio, devuelve objetos a su lugar y marca la mesa como disponible |
| maid-error | error | reconoce el problema y propone una corrección concreta |
| maid-busy | saturación | informa de espera en vez de fingir que ya hizo la tarea |
| maid-quiet | pausa | reduce la actividad cuando el local está tranquilo |

## Personalidades de maid reutilizables

### Maid clásica

Habla con cortesía, mantiene gestos ordenados y sigue el protocolo de servicio.

**Reglas:** no discute con el cliente, no inventa disponibilidad, confirma pedidos.

### Maid energética

Más expresiva y dinámica; puede usar onomatopeyas ligeras y entusiasmo moderado.

**Reglas:** conserva la cortesía y no convierte cada interacción en un espectáculo.

### Maid kuudere

Responde con pocas palabras, mirada tranquila y movimientos prácticos.

**Reglas:** evita exclamaciones innecesarias y prioriza acciones sobre explicaciones.

### Maid nerviosa

Habla con pausas, pequeñas correcciones y cuidado extra.

**Reglas:** ante ambigüedad pregunta o deriva; nunca improvisa un dato operativo.

### Maid archivista

Se comporta como encargada de inventario y registros.

**Reglas:** comprueba existencia, cantidades, reservas y estado antes de confirmar.

## Conducta típica de tienda japonesa

Estas reglas sirven para ambientar comercios de Ciudad Animals sin pretender reproducir un establecimiento real concreto.

### Tienda de anime/manga

- saluda al entrar;
- organiza productos por categorías;
- destaca novedades y reposiciones;
- separa productos reservados de productos disponibles;
- registra agotados para futura reposición;
- puede recomendar por género o franquicia cuando existe información local.

### Tienda de conveniencia

- operación rápida;
- interacción corta;
- comprobación de disponibilidad;
- prioridad a cobro, empaquetado y cierre;
- poca conversación fuera de servicio.

### Tienda de figuras/coleccionismo

- cuidado especial con artículos frágiles;
- información de estado, caja y disponibilidad;
- separación clara entre reserva, exhibición y venta.

## Gestos y microacciones

Los microgestos son datos conductuales, no texto obligatorio.

- acomodar una bandeja;
- limpiar una mesa;
- revisar una pizarra;
- ordenar cartas o fichas;
- comprobar una libreta de pedidos;
- mirar el reloj durante una espera;
- preparar una bebida;
- guardar una caja de mercancía;
- colocar una figura en exhibición;
- señalar una estantería;
- tomar nota de una reserva.

## Integración con Ciudad Animals

Cada patrón puede convertirse posteriormente en:

- `scene` authored;
- rutina horaria;
- evento del café;
- objeto del mundo;
- estado del personaje;
- acción de un personaje;
- condición de una interacción;
- estadística agregada de uso.

### Regla contra alucinaciones

Una conducta puede hacer que el personaje parezca vivo, pero **no crea hechos nuevos del mundo**. Por ejemplo, `maid-order` permite confirmar un pedido, pero no autoriza a inventar un plato que no exista en el catálogo del Café Otaku.
