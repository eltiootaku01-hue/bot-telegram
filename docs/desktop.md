# BOT-IA Desktop

BOT-IA tiene una interfaz gráfica de Windows que utiliza el mismo runtime que la consola, Telegram y la API HTTP.

## Uso normal

Para el usuario final, el punto de entrada es `BOT-IA.exe`. No hace falta abrir Python, PowerShell ni una terminal.

En una instalación nueva, `BOT-IA.exe` abre un asistente de primera configuración. Desde ahí se elige la biblioteca de ONE NEKO PUNCH y el proveedor IA, se introduce la clave y se guarda la configuración local. Después el mismo acceso directo abre la interfaz normal.

## Qué incluye la interfaz

- Ventana de conversación.
- Menú visual para novela, biblioteca, continuidad, ideas e investigación.
- Ayuda para destrabar escenas.
- Selección y exportación controlada de contexto.
- Estado de API y progreso local.
- Botón para iniciar Telegram en un proceso separado.
- Autorización de API externa por consulta, desactivada por defecto.

## Seguridad

La GUI no crea un segundo cerebro ni una segunda base de conocimiento. Utiliza `BotApplication`, por lo que conserva las mismas reglas de evidencia, routing, memoria y providers.

La autorización externa es explícita por consulta. Los resultados externos no se convierten automáticamente en canon.

Los porcentajes del panel son indicadores locales de documentación/configuración; no representan cuotas reales del proveedor.

## Paquete Windows

El proyecto genera dos ejecutables:

- `BOT-IA.exe`: lanzador y asistente de primera configuración.
- `BOT-IA-Core.exe`: interfaz principal y runtime.

También genera `BOT-IA-Setup.exe`, un instalador de Windows sin necesidad de privilegios de administrador. El acceso directo del escritorio apunta al lanzador.

El paquete se construye automáticamente mediante GitHub Actions y se publica como artefacto de Windows. Las claves reales nunca se almacenan en Git.

## Desarrollo

`desktop.py`, `launcher.py` y `build_desktop.ps1` siguen disponibles para desarrollo y mantenimiento. Las instrucciones con Python y `PYTHONPATH` del README están destinadas al entorno de desarrollo, no al uso normal del programa.
