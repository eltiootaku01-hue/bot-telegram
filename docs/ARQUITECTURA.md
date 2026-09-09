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
