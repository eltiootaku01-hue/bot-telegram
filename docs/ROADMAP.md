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

## Checkpoint de continuidad — 2026-09-30

El punto operativo actual es `main@78d5fa6d0b539991aba1ee700121404678c21e59`. 2F-8R tiene evidencia CI verde (`857 passed` en Ubuntu y Windows, CI `36611033279`). 2F-8S/D3 está implementado y la suite S01-S13 existe en el estado actual, pero la evidencia cross-platform de `78d5` fue parcial: Windows `872 passed`; Ubuntu `863 passed, 9 errors` por carga de QWebEngine local. El provider real y la autenticación real siguen UNKNOWN/BLOCKED.

La memoria D3 se conserva en `603266...` y `b6265...`; el punto de continuidad permanece en `main@78d5...`.
