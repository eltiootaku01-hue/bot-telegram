# Investigación de flujos profesionales por identidad

Fecha: 2026-09-20

## Objetivo

Convertir las cuatro identidades del proyecto y el puente humano de Tío Otaku en unidades de trabajo especializadas, con:

- entrada clara;
- decisión local;
- estado persistente;
- salida observable;
- recuperación ante errores;
- métricas;
- posibilidad de ampliar el sistema sin convertir todo en una IA.

La arquitectura de referencia mantiene una regla: el runtime debe funcionar aunque la IA esté apagada.

## Cari — comunidad y anfitriona

### Trabajo

Cari recibe conversaciones sociales, presenta el Café Otaku, acompaña a la comunidad, deriva consultas y ejecuta herramientas explícitas de moderación.

### Método profesional

```text
mensaje humano
    ↓
detectar intención
    ↓
responder con repertorio authored
    ↓
observar uso agregado
    ↓
derivar si corresponde
    ↓
no interrumpir si hay conversación humana activa
```

La capa social debe tratar el silencio como una salida válida. Las herramientas de moderación deben ser explícitas, auditables y basadas en permisos reales de Telegram.

### Evolución

- calendario social;
- rutinas authored por horario;
- panel de actividad del Café;
- reportes diarios de comunidad;
- detección de picos de actividad para retrasar intervenciones;
- futuras sugerencias IA únicamente como apoyo al operador.

### Métricas

- mensajes respondidos;
- intervenciones evitadas por conversación activa;
- escenas de repertorio utilizadas;
- acciones de moderación;
- errores de permisos;
- tiempo entre intervención y última actividad humana.

## Sunna — juego, colección y economía

### Trabajo

Sunna ejecuta reglas deterministas de WaifuMon: gacha, encuentros, intentos, captura, colección, evolución, puntos, combate, trivia y misterios.

### Método profesional

```text
acción Telegram
    ↓
validar identidad / comunidad
    ↓
leer estado durable
    ↓
transacción atómica
    ↓
recompensa idempotente
    ↓
respuesta corta
    ↓
telemetría agregada
```

El sistema nunca debe confiar en que un callback solo ocurre una vez. Debe aceptar reintentos y carreras de procesos como comportamiento normal.

Un patrón útil de proyectos de juegos de Telegram es limitar trabajo concurrente por jugador y procesar operaciones en orden; esto reduce carreras sobre el saldo y conserva un estado predecible.

### Evolución

- colas por jugador para acciones que realmente necesiten procesamiento;
- límites de operaciones simultáneas;
- historial visible de partidas;
- estadísticas de colección;
- eventos estacionales;
- pity/garantías solo si se documentan como reglas locales;
- workers separados para cálculos pesados.

### Métricas

- tiradas;
- capturas;
- intentos fallidos;
- recompensas entregadas;
- colisiones/idempotencias;
- partidas concurrentes;
- tiempo de resolución;
- rarezas obtenidas;
- uso de cada personaje.

## Cami — archivo y media operations

### Trabajo

Cami recibe medios, identifica assets, clasifica, etiqueta, asocia pedidos, programa publicaciones, publica, detecta entregas ambiguas y mantiene el catálogo.

### Método profesional

```text
INGESTA
  ↓
IDENTIDAD DEL MEDIO
(file_id + file_unique_id)
  ↓
BANDEJA
  ↓
TRIAGE
  ↓
ETIQUETADO
  ↓
DESTINO
  ↓
COLA DURABLE
  ↓
CLAIM
  ↓
PUBLICACIÓN
  ↓
CONFIRMACIÓN
  ↓
RECUPERACIÓN SI RESULTADO AMBIGUO
  ↓
CATÁLOGO
```

La API de Telegram permite reutilizar `file_id` sin volver a cargar un archivo y expone `file_unique_id` como identificador estable para la misma identidad de archivo. La estrategia local guarda ambos.

Los proyectos de media bots comparados emplean caché por `file_id`, límites de concurrencia, colas y limpieza de temporales. Ese patrón es preferible a ejecutar toda la transformación dentro del handler de Telegram.

### Evolución

- selección múltiple y lotes;
- `sendMediaGroup` para publicaciones agrupadas;
- workers locales de FFmpeg;
- generación de miniaturas;
- control de calidad de resolución;
- extracción de metadatos;
- OCR opcional;
- clasificación local;
- colas con concurrencia global y por operación;
- vista de cola con SLA y antigüedad.

### Métricas

- ingestiones;
- duplicados evitados;
- tiempo ingestión → tags;
- tiempo tags → publicación;
- reintentos;
- entregas ambiguas;
- publicaciones por destino;
- errores Telegram;
- profundidad máxima de cola;
- antigüedad del trabajo más viejo.

## Chie — coordinación y workspace

### Trabajo

Chie configura comunidades, comprueba permisos directamente en Telegram, crea topics, muestra ayudas, coordina reglas y notificaciones y dispara el flujo de pedidos.

### Método profesional

```text
usuario/admin
    ↓
verificación Telegram
    ↓
workspace autorizado
    ↓
procedimiento
    ↓
estado persistente
    ↓
notificación
    ↓
diagnóstico / recuperación
```

Los sistemas de soporte basados en Telegram que mejor escalan conceptualmente utilizan un workspace de foro: un caso/ticket se mantiene en su propio topic, el estado persiste y el histórico puede archivarse. Esto evita depender de cadenas de replies frágiles y facilita la operación humana.

### Evolución

- tablero de pedidos y comunidad;
- SLA configurables;
- Quick Replies solo para comunicaciones operativas preaprobadas;
- historial de configuración;
- health checks;
- reportes diarios;
- recuperación de topics eliminados;
- tareas administrativas en batch.

### Métricas

- comunidades activas;
- fallos de permisos;
- topics creados/reutilizados;
- pedidos abiertos;
- pedidos vencidos;
- tiempo medio hasta primera toma;
- tiempo medio hasta resolución;
- acciones administrativas.

## Tío Otaku — operador humano

### Trabajo

Tío Otaku representa una persona, no una IA autónoma. El sistema solo captura vocativos explícitos, crea una bandeja, entrega contexto, permite responder manualmente y registra el resultado.

### Método profesional

```text
mensaje dirigido a Tío
    ↓
captura
    ↓
ticket persistente
    ↓
contexto
    ↓
claim por operador
    ↓
respuesta humana exacta
    ↓
entrega
    ↓
resolución
```

El sistema no debe generar ni parafrasear automáticamente la voz de Tío Otaku.

### Evolución

- respuestas rápidas del operador, no IA;
- búsqueda histórica;
- filtros por estado;
- SLA;
- agrupación por comunidad;
- soporte de media y documentos;
- exportación de historial para el operador.

## Método transversal nuevo

La arquitectura evoluciona hacia una regla común:

```text
CAPTURAR
→ VALIDAR
→ CLASIFICAR
→ ENCOLAR
→ EJECUTAR
→ CONFIRMAR
→ OBSERVAR
→ RECUPERAR
```

No todas las operaciones necesitan los ocho pasos explícitos, pero todas las operaciones con efectos externos deben poder responder a estas preguntas:

1. ¿Quién pidió la acción?
2. ¿Está autorizado?
3. ¿Cuál es la fuente de verdad?
4. ¿Qué estado tenía antes?
5. ¿Qué transición produjo la acción?
6. ¿Puede repetirse sin duplicar efectos?
7. ¿Cómo se recupera si Telegram responde de forma ambigua?
8. ¿Qué métrica demuestra que el sistema está funcionando?

## Patrones que adoptamos y anti-patrones

### Adoptados

- SQLite durable para estado pequeño y local.
- WAL y transacciones explícitas.
- workers durables para trabajo diferido.
- claves idempotentes.
- callbacks verificados contra actor real.
- allowlist central.
- caché de `file_id`.
- `file_unique_id` para detección de identidad estable.
- topics para workspaces y soporte.
- métricas agregadas.
- recuperación manual cuando una operación externa es ambigua.
- IA fuera de los límites que definen permisos, canon e identidad.

### Evitados

- trabajo pesado dentro del handler de Telegram;
- estado exclusivamente en memoria;
- mensajes públicos con información privada de usuario;
- aceptar que el usuario "dice ser admin" como prueba;
- enviar dos veces una acción por un retry;
- usar un único `file_id` como identidad conceptual del contenido;
- resolver errores ambiguos con un reintento automático ciego;
- generar personalidad o canon con IA en tiempo real.

## Resultado esperado

La evolución buscada no es "más funciones porque sí".

Es transformar cada identidad en una pequeña unidad operativa especializada que:

- conoce su responsabilidad;
- conserva su estado;
- mide su trabajo;
- falla de forma recuperable;
- escala con workers cuando haga falta;
- puede incorporar IA después sin depender de ella.

Las herramientas externas comparadas sirven como patrones arquitectónicos, no como dependencia del proyecto.
