# Instalación de BOT-IA en Windows

## Método recomendado

BOT-IA está preparado para usarse como aplicación de escritorio. El usuario final no necesita instalar Python ni ejecutar PowerShell para iniciar el programa.

El paquete de Windows contiene:

- `BOT-IA-Setup.exe`: instalador normal de Windows.
- `BOT-IA.exe`: punto de entrada que se ejecuta con doble clic.
- `BOT-IA-Core.exe`: núcleo interno de la interfaz.
- `config/`: configuración de runtime.
- `biblioteca/`: biblioteca empaquetada cuando existe en el repositorio.

## Instalación

1. Ejecuta `BOT-IA-Setup.exe`.
2. Acepta la carpeta propuesta o elige otra. No requiere privilegios de administrador.
3. Deja marcada la opción para iniciar BOT-IA al terminar.
4. En el primer inicio, BOT-IA pide la ruta de la biblioteca y la clave del proveedor IA.
5. Guarda la configuración y BOT-IA se abre normalmente.

A partir de entonces, el usuario puede iniciar BOT-IA desde el acceso directo del escritorio o del menú Inicio. El programa no necesita una terminal abierta.

## Primera configuración

La primera ejecución solicita:

- Biblioteca de ONE NEKO PUNCH.
- Proveedor principal: OpenAI, Groq u OpenRouter.
- Clave API del proveedor elegido.
- Token de Telegram, de forma opcional.

La configuración se guarda en `.env` local junto al programa. Este archivo nunca debe subirse a GitHub.

## Seguridad y privacidad

BOT-IA conserva la regla de no convertir suposiciones del modelo en hechos. La biblioteca local, la memoria y las reglas de evidencia siguen siendo gestionadas por el mismo runtime que usa la consola, Telegram y la API.

La autorización de API externa de la interfaz principal es por consulta y está desactivada por defecto. Una consulta externa no se convierte automáticamente en canon.

## Si se mueve la biblioteca

Vuelve a ejecutar `BOT-IA.exe`. Si la ruta guardada ya no existe o no contiene documentos `.md`, el asistente de configuración volverá a aparecer.

## Desarrollo

El flujo de desarrollo sigue siendo independiente del uso normal. Los comandos de Python, `PYTHONPATH` y PowerShell del README son para desarrolladores, no para el usuario final.
