# BOT-IA

BOT-IA usa componentes locales y deterministas para router, contexto, agentes,
providers e interfaz Telegram. La memoria persistente es SQLite local, requiere
autorización explícita y no modifica automáticamente el canon.

Las pruebas se ejecutan sin dependencias externas:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
