# Release readiness — 2026-09-19

## Estado de Git

- Rama de entrega: `main`
- El árbol incluye el endurecimiento de concurrencia de Sunna/WaifuMon.
- El árbol incluye catálogo persistente de Ciudad Animals y su inicialización desde el módulo Core.
- El árbol incluye ranking comunitario de puntos para Sunna.
- El árbol incluye autorización específica del canal configurado como media vault.
- El árbol incluye selección ponderada del repertorio authored.

## Validación esperada

CI debe ejecutar Ruff y toda la suite Pytest.

Windows Build debe ejecutar las pruebas nativas, compilar los cinco ejecutables, verificar BotManager, crear el instalador Inno Setup, generar el ZIP portable y producir SHA256.

No se considera una entrega completa hasta que ambas canalizaciones terminen correctamente sobre el mismo SHA.
