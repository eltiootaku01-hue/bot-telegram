# Modelo operativo de los cuatro bots

Fecha: 2026-09-20

Este documento define cómo debe evolucionar cada identidad sin convertirlas en cuatro copias del mismo bot.

## Principio común

Cada identidad sigue:

1. entrada de Telegram;
2. validación de identidad, chat y permisos;
3. decisión determinista sobre una capacidad existente;
4. operación local y durable;
5. observación agregada del mundo;
6. respuesta o entrega;
7. recuperación si un efecto externo quedó ambiguo.

La IA puede asistir una capacidad explícitamente marcada como requires_ai, pero no crea permisos, estados, personajes, canon ni acciones ejecutables.

## Cari — anfitriona y comunidad

### Trabajo primario

Cari mantiene presencia comunitaria, atiende el Café Otaku, conversa dentro de límites reconocidos y ejecuta herramientas explícitas de moderación.

### Método operativo

- conversación cotidiana: router determinista + repertorio authored;
- presencia: wake → observe → decide → turn → respuesta authored;
- Café: servicios deterministas por fecha, estado y comunidad;
- moderación: solo por administrador real de Telegram, con registro persistente;
- derivación: cuando otra identidad posee la capacidad, Cari puede abrir una interacción authored en vez de fingir que sabe hacerlo todo.

### Evolución recomendada

El siguiente salto de calidad no es darle más respuestas aleatorias. Es ampliar contextos authored:

- bienvenida;
- actividad baja;
- celebración;
- recomendación;
- incidentes comunitarios;
- acompañamiento entre personajes;
- microeventos del Café.

Cada nueva escena debe tener clave única, intención explícita y cobertura de tests.

## Sunna — juego y progresión

### Trabajo primario

Sunna administra WaifuMon, gacha, encuentros, colección, evolución, combate, trivia y misterios.

### Método operativo

- toda recompensa importante necesita referencia idempotente;
- los estados de juego avanzan mediante transiciones condicionales;
- un encuentro activo por comunidad;
- una oportunidad por jugador y encuentro;
- un ganador por ronda;
- el ledger de puntos es la fuente de verdad económica;
- los errores de publicación no deben crear recompensas duplicadas.

### Evolución recomendada

Priorizar sistemas que aumenten profundidad sin aumentar dependencia de IA:

- misiones diarias/semanales;
- logros;
- afinidad con personajes;
- temporadas;
- tablas de clasificación con ventanas temporales;
- eventos cooperativos;
- protección antifraude de recompensas;
- cartas con habilidades deterministas;
- reglas de pity/garantía explícitas para gacha cuando el diseño lo defina.

La IA puede ser una herramienta de explicación o curatoría, nunca el motor de economía.

## Cami — archivo y producción de contenido

### Trabajo primario

Cami recibe material, organiza álbumes, etiqueta, valida destinos, programa publicaciones, publica, recupera entregas ambiguas, mantiene el catálogo y acompaña pedidos.

### Método operativo recomendado

ingesta → identidad del medio → bandeja → clasificación → tablero → programación → claim → envío → confirmación → recuperación → catálogo

### Controles

- guardar file_id para reutilización operacional;
- guardar file_unique_id como señal estable de identidad;
- tratar media_group_id como unidad lógica para álbumes;
- no publicar automáticamente material que todavía no pasó clasificación;
- usar cola durable para trabajo diferido;
- limitar procesamiento pesado en workers;
- marcar entrega ambigua en vez de adivinar el resultado;
- separar revisión privada de publicación pública.

### Tablero de trabajo

/tablero combina pedidos y materiales pendientes en una sola vista priorizada por:

1. entrega ambigua;
2. SLA vencido;
3. estados que bloquean el flujo;
4. trabajo normal;
5. programación futura.

El tablero es una vista de routing para el operador. No reemplaza las tablas persistentes ni ejecuta automáticamente una acción peligrosa.

### Evolución recomendada

Añadir workers especializados, siempre separados del receptor Telegram:

- normalización de imágenes;
- generación de miniaturas;
- detección de duplicados;
- validación de dimensiones/formato;
- extracción controlada de metadatos;
- clasificación asistida opcional por IA;
- publicación de álbumes como lote cuando el destino lo requiera.

Cada worker debe tener límite de concurrencia, timeout, estado durable y recuperación.

## Chie — coordinación y gobernanza operativa

### Trabajo primario

Chie configura la comunidad, comprueba permisos, crea temas, presenta reglas, recibe solicitudes, muestra estados y mantiene paneles de salud/mundo.

### Método operativo

- comprobar permisos directamente con Telegram;
- mantener una comunidad explícitamente autorizada;
- no confundir configurado en base con autorizado actualmente;
- persistir solicitudes y eventos;
- mostrar solo la información del usuario que corresponde;
- exponer health checks agregados al administrador;
- tratar Ciudad Animals como observación + revisión, no como canon automático.

### Evolución recomendada

- checklist de configuración reanudable;
- detector de permisos perdidos;
- avisos de cola vencida;
- resumen diario del estado del sistema;
- auditoría compacta de cambios;
- políticas de retención y privacidad;
- revisión de mundo diaria/semanal con aprobación humana.

## Tío Otaku — operador humano

Tío Otaku no es una quinta IA autónoma.

El sistema debe:

- identificar mensajes dirigidos al operador;
- crear una entrada durable;
- conservar el contexto mínimo necesario;
- ofrecer historial paginado;
- entregar la respuesta humana al chat correcto;
- registrar el resultado.

La decisión y redacción final pertenecen a la persona que opera Tío Otaku.

## Criterio de promoción

Una función experimental sale de experiments/local_first y pasa a app/ únicamente cuando tiene:

- contrato claro;
- autoridad/permiso definido;
- estado persistente;
- comportamiento idempotente cuando produce efectos;
- tests;
- CI verde;
- empaquetado compatible cuando corresponda.

No se crean implementaciones duplicadas en ramas experimentales ni dentro de la aplicación.
