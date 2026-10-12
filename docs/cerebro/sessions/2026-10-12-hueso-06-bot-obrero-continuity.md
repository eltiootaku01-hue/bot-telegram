# Session Continuity — HUESO-06 / PR #98 / BOT-OBRERO

**Fecha del registro:** 2026-10-12  
**Repositorio:** `eltiootaku01-hue/bot-telegram`  
**Propósito:** conservar únicamente los últimos pasos y el estado conocido para continuar en otro chat sin reiniciar la investigación.

## 1. Regla operativa solicitada para BOT-OBRERO

El usuario exige que BOT-OBRERO actúe como un profesional de informática orientado a resolver problemas y no deje una operación esperando indefinidamente:

- **Límite de espera por operación: 120 segundos.**
- Si una operación supera el límite, detener esa espera, registrar `TIMEOUT / BLOCKED`, conservar la evidencia ya obtenida y elegir una alternativa segura y acotada.
- No repetir indefinidamente la misma consulta ni emitir mensajes de progreso vacíos.
- Preferir una solución concreta y mínima cuando haya evidencia suficiente; si falta evidencia esencial, informar el bloqueo exacto y el dato mínimo necesario.
- No inventar resultados, causa raíz, tests, CI ni acciones completadas para aparentar avance.
- Este requisito queda registrado aquí como instrucción explícita del usuario. **No se ha modificado el contrato general** `docs/cerebro/BOT_OBRERO_OPERATING_CONTRACT.md` en esta tarea.

## 2. Referencias GitHub verificadas en esta sesión

Consulta remota realizada el 2026-10-12:

- `main`: `9b191e578e86a65522cc374bdda24e53d386df37`.
- Mensaje de `main`: `docs: close HUESO-05 after verified merge`.
- PR #98: [docs: clarify historical project checkpoints](https://github.com/eltiootaku01-hue/bot-telegram/pull/98).
- Estado observado de PR #98: `OPEN / DRAFT / UNMERGED`; GitHub informa `mergeable=true`, lo cual no equivale a CI aprobado ni a permiso de merge.
- Rama de PR #98: `docs/hueso-06-current-state-reconciliation-2026-10-09`.
- HEAD de PR #98: `da07a3a213981c25c9228cffef0c3d7a408c48a9`.
- Base SHA registrada en PR #98: `9b191e578e86a65522cc374bdda24e53d386df37`. La consulta de esta sesión confirmó que `main` apuntaba a ese SHA.
- Diff neto reportado por GitHub: exactamente dos archivos, `docs/ROADMAP.md` y `docs/project_memory/CURRENT_STATE.md`; 33 inserciones y 8 eliminaciones.

## 3. HUESO-06 — adjudicación más reciente conocida

**Estado:** `NO-GO — KEEP PR BLOCKED`.  
**Excepción documental:** `PROPOSED / NOT APPROVED`.  
**Merge:** no autorizado.

Según la adjudicación de CI aportada en la conversación, el run candidato [38147167677](https://github.com/eltiootaku01-hue/bot-telegram/actions/runs/38147167677) terminó con ambos jobs fallidos:

- Ubuntu: `921 passed, 1 failed, 9 errors`. Nueve errores con la firma conocida `QWebEngine local page did not load`; un fallo adicional en `test_xp_tracker_producer_race_producer_wins_before_stop`, donde se observó `unfinished_tasks = 0` cuando se esperaba `1`.
- Windows: `922 passed, 9 errors`. Nueve errores `QWebChannel monitor did not become ready: []`.
- Baseline reportado: [run 37651016841](https://github.com/eltiootaku01-hue/bot-telegram/actions/runs/37651016841), asociado a `main@9b191e578e86a65522cc374bdda24e53d386df37`. Ubuntu tenía los nueve errores QWebEngine coincidentes; Windows pasó sin esos errores y el test de carrera de Telegram pasó.
- Clasificación registrada: errores QWebEngine Ubuntu = `MATCHING BASELINE FAILURE`; errores QWebChannel Windows y fallo de carrera Telegram Ubuntu = `ADDITIONAL FAILURE`; causa raíz de los fallos adicionales = `UNKNOWN`; salud global del runtime = `NOT DEMONSTRATED`.

**Límite de frescura:** los estados detallados de los jobs anteriores se conservan de la adjudicación recibida en la conversación; en esta sesión se verificaron el HEAD de `main` y los metadatos de PR #98, pero no se volvió a consultar el resultado actual de Actions.

## 4. Qué se hizo

- Se leyó desde `main` `docs/cerebro/README.md` y `docs/cerebro/BOT_OBRERO_OPERATING_CONTRACT.md`.
- Se consultó la referencia remota de `main`.
- Se consultaron los metadatos actuales de PR #98.
- Se creó la rama de documentación de continuidad `docs/session-continuity-hueso-06-2026-10-12`, basada en `main@9b191e578e86a65522cc374bdda24e53d386df37`.
- Este documento se está registrando en esa rama para no tocar directamente `main` ni ampliar el diff de PR #98.

## 5. Qué NO se hizo

- No se fusionó, cerró ni marcó como lista PR #98.
- No se aprobó la excepción de CI.
- No se cambió `main` ni la rama de PR #98.
- No se modificó código de producción, tests, configuración ni workflows.
- No se relanzó CI ni se ejecutaron pruebas locales.
- No se hicieron experimentos QWebEngine ni se reabrió 2F-8T.
- No se declaró causa raíz para los fallos adicionales.
- No se declaró cerrado HUESO-06.
- No se modificó el porcentaje estimado de HUESO-10 ni se autorizó expansión de WORLD/Café Otaku.

## 6. Próxima acción concreta

1. Guardar este documento mediante un commit en la rama de continuidad y abrir una PR de documentación en draft, separada de PR #98.
2. Después, si se decide retomar HUESO-06, volver a consultar el CI y las referencias actuales; mantener el `NO-GO` hasta que el responsable autorice expresamente una excepción acotada o exista evidencia suficiente para adjudicar los fallos adicionales.
3. No usar esta nota como autorización de merge, reparación, nuevo experimento QWebEngine ni siguiente fase.

## 7. Autoridad y límites

- GitHub es la fuente de verdad; este documento es una nota de continuidad, no reemplaza los contratos ni los gates especializados.
- `2F-8T = VERIFIED BLOCKER / ROOT CAUSE UNKNOWN` permanece congelado.
- `NO EVIDENCE = NO CLAIM`.
- `NO GATE = NO NEXT PHASE`.
- No realizar operaciones destructivas, merge, push forzado ni cambios fuera del alcance autorizado.
