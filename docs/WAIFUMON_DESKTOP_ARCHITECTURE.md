# WaifuMon — arquitectura del cliente de escritorio

## Objetivo

WaifuMon puede crecer mucho más allá de las limitaciones de una conversación de Telegram: combate visual, selección de equipo, estadísticas completas, animaciones, inventario, colecciones, evolución, escenas y futuros minijuegos.

La decisión arquitectónica es separar:

- **Game/World Core en Python:** autoridad absoluta.
- **Cliente de escritorio JavaFX:** presentación interactiva.
- **Telegram:** interfaz social y puerta de entrada al juego.

## Regla de autoridad

El cliente JavaFX nunca debe escribir directamente en SQLite ni resolver reglas de juego.

La arquitectura objetivo es:

```text
                 GAME WORLD / GAME CORE
                         │
                Game Services / Rules
                         │
                    Persistence
                         │
                  Local Game API
                         │
                  ┌──────┴──────┐
                  │             │
             JavaFX client   Telegram bots
             presentación     presentación
```

El servidor Python es el único que decide:

- estadísticas reales;
- clase D–SSS;
- nivel 1–30;
- experiencia;
- etapas de evolución;
- potencial individual;
- resultados de combate;
- recompensas;
- puntos;
- inventario;
- misiones;
- encuentros;
- estados persistentes.

JavaFX recibe estado ya resuelto y envía **intenciones** de jugador, por ejemplo:

```text
GET /game/profile
GET /game/collection
GET /game/waifumon/{id}

POST /game/combat/start
POST /game/combat/{id}/action
POST /game/encounter/{id}/answer
POST /game/item/{id}/absorb
```

El API real todavía no forma parte de este bloque; estas rutas son contratos objetivo, no endpoints actualmente disponibles.

## Por qué no acceder SQLite desde JavaFX

Un acceso directo del cliente a SQLite rompería varias garantías:

- dos procesos podrían mutar el mismo estado sin pasar por los servicios;
- la política de transacciones quedaría duplicada;
- sería más difícil aplicar fencing e idempotencia;
- la seguridad de permisos se repartiría entre dos runtimes;
- las reglas podrían divergir entre Python y Java;
- futuras plataformas no podrían reutilizar el mismo Game Core.

Por eso SQLite sigue siendo interno al servidor Python.

## Cliente JavaFX

JavaFX debe limitarse a:

- escenas;
- botones;
- animaciones;
- navegación;
- render de estadísticas;
- arte;
- sonido;
- HUD;
- barras de HP/EXP;
- selección de equipos;
- visualización de colección;
- presentación de combates;
- accesibilidad y escalado de ventana.

No debe contener fórmulas de daño ni recompensas.

## Estadísticas

El catálogo/card público muestra únicamente información mínima:

```text
Nombre
Anime
Clase
Elemento
Arte
```

La vista completa aparece al entrar al juego o después de poseer la WaifuMon.

El backend resuelve:

```text
stats = f(
  personaje,
  clase,
  nivel,
  elemento,
  potencial_individual
)
```

El mismo resultado debe ser idéntico en Telegram, JavaFX y futuras interfaces.

## Nivel y clase

Son dimensiones diferentes:

### Clase de combate

D → C → B → A → S → SS → SSS

Determina multiplicadores de base, potencial de combate y disponibilidad de arte de clase.

### Nivel

1 → 30

Determina crecimiento por experiencia.

Subir de nivel **no cambia la clase**.

### Evolución visual por nivel

La evolución de nivel tiene cuatro etapas:

```text
Etapa 1 — Nv. 1–5
Etapa 2 — Nv. 6–10
Etapa 3 — Nv. 11–20
Etapa 4 — Nv. 21–30
```

Por lo tanto, una WaifuMon clase D nivel 20 sigue siendo clase D nivel 20; una clase S nivel 20 sigue siendo clase S nivel 20 y puede tener estadísticas muy superiores.

## Potencial individual

Cada primera adquisición posee un `potential_seed` persistente.

La semilla:

- se genera una sola vez;
- sobrevive reinicios;
- no se recalcula en cada consulta;
- produce variaciones deterministas de las estadísticas;
- no reemplaza el efecto de la clase;
- permite diferenciar ejemplares con la misma clase y nivel en futuras versiones del modelo.

Las filas heredadas de instalaciones antiguas sin semilla usan una semilla de compatibilidad derivada del personaje para no alterar inesperadamente colecciones existentes.

## Arte

Existen tres conceptos distintos:

1. **Arte de carta:** R/S/SR/UR.
2. **Arte de clase:** D/C/B/A/S/SS/SSS.
3. **Arte de evolución:** etapas de nivel 1/2/3/4.

La existencia de un registro de rutas de arte no implica que todas las imágenes finales ya estén producidas. El repositorio debe diferenciar siempre entre:

- ruta declarada;
- asset existente;
- asset pendiente.

## Integración con Telegram

Telegram sigue siendo útil para:

- descubrir una WaifuMon;
- capturar un encuentro;
- consultar colección;
- recibir recompensas;
- iniciar una partida;
- recibir notificaciones;
- compartir resultados.

El cliente JavaFX se reserva la experiencia de juego profunda.

## Futuras extensiones

La misma API local puede soportar:

- cliente JavaFX;
- cliente web local;
- herramientas de administración;
- simulador de combate;
- modo espectador;
- tests de gameplay;
- otros bots presentadores.

La regla central permanece:

```text
múltiples clientes
      ↓
mismo Game Core
      ↓
misma Persistence
      ↓
mismo estado verdadero
```

## Estado de implementación

Implementado en el core:

- separación entre clase y nivel;
- cuatro etapas de evolución;
- potencial persistente;
- estadísticas deterministas;
- carta con información mínima;
- vista detallada tras posesión;
- registros de arte por clase y etapa.

Pendiente como bloque separado:

- API local autenticada;
- proyecto JavaFX;
- sincronización en tiempo real;
- empaquetado del cliente desktop;
- sistema de escenas/combate visual;
- pruebas contractuales Python ↔ Java.
