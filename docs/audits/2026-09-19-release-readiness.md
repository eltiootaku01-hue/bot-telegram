# Release readiness — 2026-09-19

## Estado actual

- Rama de entrega: `main`
- SHA validado: `578f0ba9144331b91b89dffdff6049b9899ff489`
- CI #1028: **SUCCESS**
- Windows Build #669: **SUCCESS**
- Las dos canalizaciones terminaron correctamente sobre el mismo SHA.

## Incluido en este estado

- endurecimiento de concurrencia de Sunna/WaifuMon;
- control de acceso central y autenticación correcta de callbacks;
- allowlist aplicada también a envíos automáticos;
- publicaciones de Cami con claim atómico + `BEGIN IMMEDIATE`;
- catálogo persistente de Ciudad Animals;
- catálogo local de anime/manga + importador JSON;
- interacciones authored-only por parejas de personajes;
- repertorio authored-only y nuevas rutas de interacción;
- Misterio diario de Sunna con persistencia, recuperación e idempotencia;
- prueba de carrera con dos conexiones SQLite para demostrar un único ganador/recompensa;
- paquete Windows completo.

## Paquete Windows comprobado

El workflow #669 verificó:
- los cuatro bots;
- BotManager;
- instalador Inno Setup;
- ZIP portable;
- checksums SHA-256;
- subida de ambos artefactos.

El paquete queda listo para instalación/uso desde los artefactos de GitHub Actions. Una publicación de GitHub Release requiere un tag `v<version>` coherente con `pyproject.toml`.

## Estado de producto

Este estado representa una base funcional y empaquetada, no el 100% de la hoja de ruta narrativa. Continúan pendientes áreas de expansión como volumen de repertorio, biblias canónicas completas para personajes sin material equivalente, mayor profundidad de Ciudad Animals/Café Otaku, GUI completa, catálogo documental consultable y herramientas avanzadas del operador humano Tío Otaku.
