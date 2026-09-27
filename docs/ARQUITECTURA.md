# Arquitectura BOT-IA / Knowledge Engine

```text
Fuentes / Canon
      ↓
Librarian + Retrieval
      ↓
Context Engine
      ↓
Brain / Router
      ↓
Agents / Output Contracts
      ↓
Provider Manager
   ├─ cuenta 1
   ├─ cuenta 2
   ├─ fallback provider
   └─ health + cooldown
      ↓
API del Knowledge Engine
   ├─ Web UI
   ├─ Telegram
   └─ integraciones explícitas (MCP / otras)
```

Principio central: conocimiento, canon, evidencia y reglas de dominio son independientes del modelo. Los providers son adaptadores intercambiables.


## Café Otaku — Character Engine + WebChat compartido (PROPUESTA)

Esta sección describe el diseño aprobado conceptualmente en la auditoría de 2026-09-27. No representa una implementación existente.

    Telegram / Discord / GUI
              ↓
          BOT-IA Core
       ┌──────┼───────────┐
     Identity State      Rules
        │       │           │
     Memory  Economy    Permissions
        │       │           │
        └──────┴────── Events
                        ↓
                 Character Engine
              ┌─────────┴─────────┐
          ROLEPLAY              ANALYSIS
              │                     │
              └──────────┬──────────┘
                         ↓
                 Shared WebChat
               Controller + Queue
                         ↓
              Persistent browser/session
                         ↓
                     Web Chat
                         ↓
                     lenguaje
                         ↓
                 BOT-IA valida
                         ↓
           estado / eventos / publicación

### Principios

- WebChat es un recurso compartido, no propiedad permanente de una personalidad.
- No crear un WebChat separado por personaje o por tarea.
- Las prioridades ordenan tareas pendientes, pero nunca saltan el cooldown del recurso.
- El cooldown es una restricción independiente de prioridad.
- Los estados técnicos no deben aparecer como mensajes visibles al usuario.
- Una interacción directa con Cari debe controlar una intervención pendiente por usuario/personaje, sin bloquear al resto del grupo.
- El Character Engine prepara el contexto; WebChat genera lenguaje.
- BOT-IA conserva autoridad sobre identidad, emociones, relaciones, economía, permisos, inventarios, sesiones, mesas y eventos.
- El modelo no modifica directamente el estado persistente.
- Memoria relevante, mensajes recientes, identidad y contexto de mesa deben mantenerse separados.
- La salida pública debe ser únicamente la voz del personaje; cualquier metadata posterior debe viajar por un contrato separado y no visible.

### Estado actual frente a la propuesta

- src/services/web_queue.py: existe y está conectado al runtime Qt; implementa FIFO y exclusión mutua.
- src/gui/task_orchestrator.py: contiene prioridades HIGH/MEDIUM/LOW, pero no es actualmente la política global del WebChat.
- src/bot_ia/providers/prompt_builder.py: construye roleplay para Tavern, pero todavía no es el Character Engine completo.
- Estado emocional estructurado y actitud operacional: faltantes.
- Selección de memoria relevante para el personaje: faltante.
- Interacción grupal controlada “Hablarle a Cari”: faltante.
- Contrato de metadata emocional posterior: pendiente de diseño.
- Continuidad E2E de sesión compartida: no verificada.

Esta propuesta debe implementarse mediante extensión de infraestructura existente y no mediante un segundo WebChat, una segunda memoria o un segundo sistema de colas sin justificación.
