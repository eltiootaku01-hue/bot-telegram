# Roadmap

## Estado actual

BOT-IA tiene el runtime central, bibliotecario local, EvidenceGate, providers con fallback, memoria persistente, Telegram, API HTTP y una interfaz gráfica de Windows que comparte el mismo backend.

## Entregado

- Núcleo local determinista y routing.
- Librarian/RAG con recuperación y ranking de evidencia.
- Separación de canon y referencias externas.
- EvidenceGate y contrato de salida anti-invención.
- Provider manager con múltiples cuentas, prioridad, fallback, health y cooldown.
- OpenAI como provider principal; Groq y OpenRouter disponibles; Coze configurable.
- Ollama opcional y bajo demanda, sin modelo residente por defecto.
- Memoria persistente local.
- Telegram con menú visual, callbacks, reintentos y división de mensajes largos.
- API HTTP local con protección para exposición externa.
- Interfaz de escritorio Tkinter con menú, chat, estado, progreso, compartir contexto y Telegram.
- Lanzador `BOT-IA.exe` con asistente de primera configuración.
- `BOT-IA-Core.exe` como runtime de escritorio.
- Instalador `BOT-IA-Setup.exe` para Windows sin privilegios de administrador.
- CI para tests y superficie Windows.
- Limpieza de ramas para mantener `main` como rama canónica.
- Documentación de instalación para usuario final.

## Mantenimiento futuro

Las mejoras posteriores deben entrar mediante commits directos sobre `main` y conservar estas restricciones: diseño ligero, no procesos residentes pesados, separación de evidencia y generación, y prohibición de convertir suposiciones en hechos.

## Checkpoint de continuidad — 2026-09-30 (HISTORICAL)

> **HISTORICAL — NOT CURRENT MAIN STATE.** Este checkpoint conserva la evidencia disponible el 30 de septiembre de 2026. Los recuentos de tests, resultados de CI y estados de provider/autenticación que siguen a continuación son históricos; no describen una ejecución actual.

> En el checkpoint, el HEAD observado de `main` era `1763974f4dc27fb5ea5f66452c0f9b57297aaa76`. Ese SHA no es el HEAD actual de `main`. `78d5fa6d0b539991aba1ee700121404678c21e59` sigue siendo el `LAST FUNCTIONAL BASELINE` histórico de la línea funcional descrita por el checkpoint, no la referencia actual de `main`.

> **CURRENT MAIN REFERENCE — VERIFIED 2026-10-09 (before this documentation patch):** `main@9b191e578e86a65522cc374bdda24e53d386df37`. Esta referencia se registra por separado y no convierte los resultados históricos en resultados actuales.

En el checkpoint, `1763974f4dc27fb5ea5f66452c0f9b57297aaa76` tenía como parent inmediato y baseline funcional `78d5fa6d0b539991aba1ee700121404678c21e59`. 2F-8R tenía evidencia CI verde (`857 passed` en Ubuntu y Windows, CI `36611033279`). 2F-8S/D3 estaba registrado como implementado y la suite S01-S13 existía en el estado descrito entonces, pero la evidencia cross-platform de `78d5` era parcial: Windows `872 passed`; Ubuntu `863 passed, 9 errors` por carga de QWebEngine local. El provider real y la autenticación real seguían UNKNOWN/BLOCKED en aquel checkpoint.

La memoria D3 se conserva en `603266...` y `b6265...`; aquellos objetos se describieron como accesibles por SHA mientras los archive refs declarados históricamente permanecían ausentes/no resolubles. El punto de continuidad de ese checkpoint era `main@1763974...`; `78d5...` era y sigue siendo el `LAST FUNCTIONAL BASELINE` histórico.

## Registro posterior verificado: HUESO-05 (referencia main@9b191e5, 2026-10-09)

PR #96 fue integrada en `94757b257e9df0be3886fbaf11d66dd421c2c4e3`. El registro arquitectónico actualizado se encuentra en `main@9b191e578e86a65522cc374bdda24e53d386df37` y clasifica HUESO-05 como `CLOSED / VERIFIED REPAIR + PASS` para las líneas H05-L02..L09 y los escenarios efectivamente validados. No implica despliegue en producción ni el cierre de todas las superficies SQLite; HUESO-10 mantiene un estado independiente.
