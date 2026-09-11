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
