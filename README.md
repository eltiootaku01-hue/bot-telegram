# BOT-IA

BOT-IA usa componentes locales y deterministas para router, contexto, agentes,
providers e interfaz Telegram. La memoria persistente es SQLite local, requiere
autorización explícita y no modifica automáticamente el canon.

## Configuración mínima

El universo `one_neko_punch` se carga desde una ruta externa mediante la variable
de entorno `BOT_IA_ONE_NEKO_PUNCH_ROOT`. Esto evita rutas específicas de una
máquina dentro del repositorio.

En PowerShell:

```powershell
$env:BOT_IA_ONE_NEKO_PUNCH_ROOT = "C:\ruta\a\one-neko-punch"
$env:BOT_IA_PROVIDER = "ollama"
```

`BOT_IA_PROVIDER` es opcional y por defecto usa `ollama`. También puede usarse
`BOT_IA_UNIVERSE` para seleccionar el universo por defecto.

Las credenciales de providers se leen exclusivamente desde variables de
entorno; no deben guardarse en el repositorio.

## Pruebas

Las pruebas se ejecutan sin dependencias externas:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
