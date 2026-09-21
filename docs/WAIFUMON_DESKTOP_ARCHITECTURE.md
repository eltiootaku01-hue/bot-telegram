# WaifuMon — arquitectura de runtime y cliente

Fecha: 2026-09-21

## Autoridad del gameplay

La autoridad de las reglas de WaifuMon se está migrando a un **motor Java independiente de Telegram**.

La arquitectura oficial es:

```text
Telegram / JavaFX / futuros clientes
              ↓
         Adaptadores
              ↓
      Java WaifuMon Engine
              ↓
        Game Rules
              ↓
   transición de Game State
              ↓
 Python Persistence / SQLite
```

Los clientes no calculan reglas. Los adaptadores tampoco deben duplicarlas.

## Contrato Python ↔ Java

El engine recibe NDJSON por `stdin` y responde NDJSON por `stdout`.

Request versión `1.0`:

```json
{
  "contract_version": "1.0",
  "request_id": "uuid",
  "correlation_id": "uuid",
  "player_id": 123,
  "community_id": -100123,
  "command": "gacha.roll",
  "payload": {},
  "idempotency_key": "..."
}
```

Response:

```json
{
  "request_id": "uuid",
  "success": true,
  "result_type": "gacha_roll",
  "payload": {},
  "state_version": 0,
  "event_ids": [],
  "reward_ids": [],
  "error_code": null,
  "error_message": null
}
```

Los nombres del wire contract usan `snake_case`. La versión es obligatoria.

La idempotencia tiene dos niveles:

1. **Python/SQLite:** autoridad durable para cobros, recompensas, inventario y estado persistente.
2. **Java engine:** evita reutilizar una clave idempotente con un payload diferente dentro de un mismo proceso y puede repetir una respuesta determinista.

Una clave idempotente reutilizada con otra operación devuelve `IDEMPOTENCY_CONFLICT`.

## Reglas ya migradas

El engine Java es actualmente la única autoridad de:

- rareza base del gacha D/C/B/A/S/SS/SSS;
- cálculo determinista de combate;
- cálculo de nivel, experiencia y etapa de evolución.

Python conserva solamente la persistencia y la presentación de esos resultados. La clase `GameEngine` de Python es una **fachada de compatibilidad**, no un segundo calculador.

La progresión Python `add_character_experience()` delega directamente en Java.

## Reglas todavía pendientes de migración

Para completar la autoridad Java sin duplicación deben trasladarse de forma progresiva las reglas puramente de gameplay que todavía viven en Python:

- estadísticas derivadas completas de WaifuMon;
- potencial individual;
- fusiones D→C→B→A→S;
- resolución de encuentros;
- límites de participantes y reclamaciones;
- misiones;
- Detector;
- regalos y absorción;
- evolución visual;
- sistema de cartas cuando incluya reglas y no solamente presentación.

Cada migración debe retirar la fórmula anterior de Python o convertirla en una fachada sin lógica duplicada.

## Persistencia

SQLite sigue siendo la persistencia durable actual de la plataforma Python.

El engine Java no conoce:

- Telegram;
- chats;
- usuarios de Telegram;
- SQLite;
- tokens;
- permisos;
- HTTP;
- LLMs.

Esto permite que el mismo motor sea usado por Telegram, un cliente JavaFX, un simulador o futuras interfaces.

La persistencia Python aplica las garantías de:

- transacción atómica;
- claves únicas;
- ledger;
- referencias idempotentes;
- fencing de jobs;
- rollback;
- recuperación después de reinicios.

## Telegram

Telegram es un adaptador/presentador.

La cadena de ejecución de una acción de juego es:

```text
Callback / Command
      ↓
validación Telegram
      ↓
validación de usuario/chat/estado
      ↓
servicio de juego
      ↓
Java engine
      ↓
resultado tipado
      ↓
transacción Python
      ↓
presentación Telegram
```

El adapter no debe decidir una recompensa, modificar un saldo directamente ni volver a calcular daño.

## JavaFX

JavaFX es un cliente visual.

Puede encargarse de:

- escenas;
- HUD;
- animaciones;
- arte;
- barras HP/EXP;
- selección de equipo;
- navegación;
- inventario;
- presentación de estadísticas;
- accesibilidad.

No debe:

- abrir SQLite;
- escribir el estado de juego directamente;
- recalcular daño;
- otorgar recompensas;
- cambiar rarezas;
- validar permisos de Telegram.

## Game World

El Game World es independiente de las personalidades.

```text
Ciudad Animals
├── Café Otaku
├── WaifuMon
├── eventos
├── misiones
├── misterios
├── encuentros
├── temporadas
├── recompensas
└── estado global
```

Cari, Sunna, Cami y Chie presentan partes de ese mundo.

WorldBot puede presentar eventos sin convertirse en propietario del gameplay ni de una personalidad.

## Seguridad

Los contratos deben fallar de forma cerrada:

- versión desconocida → rechazo;
- comando desconocido → rechazo;
- payload inválido → rechazo;
- clave idempotente reutilizada con otro payload → conflicto;
- estado persistente inválido → rechazo;
- transición concurrente perdida → no se concede recompensa.

La IA no forma parte de ninguna transición crítica.

## Packaging

El repositorio construye:

- `waifumon-engine.jar`;
- un runtime JRE reducido para Windows mediante `jlink`;
- `BotManager.exe`;
- `Cari.exe`;
- `Sunna.exe`;
- `Cami.exe`;
- `Chie.exe`;
- `WorldBot.exe`.

El instalador copia el JAR y el runtime Java junto con los binarios Python.

## Estado actual

**Implementado:**

- proyecto Maven Java 21;
- DTO request/response versión 1.0;
- protocolo NDJSON;
- idempotencia local del engine;
- gacha, combate y progresión migrados;
- bridge persistente Python → Java;
- pruebas JUnit del engine;
- pruebas Python del contrato;
- CI Ubuntu construyendo y probando Java antes de Python;
- packaging Windows con JAR + JRE bundled.

**Pendiente:**

- mover el resto de las reglas puras de gameplay;
- definir eventos/versionado de estado real;
- contrato durable de `state_version`;
- API local autenticada para clientes externos;
- cliente JavaFX;
- sincronización de estado en tiempo real.

## Regla de mantenimiento

No añadir una nueva fórmula de gameplay en Python después de que esa regla haya sido migrada a Java.

La regla válida es:

```text
1 regla → 1 autoridad → muchos presentadores
```
