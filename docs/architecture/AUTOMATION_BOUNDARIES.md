# Límites de automatización de la plataforma

## Automático y local

El bot puede funcionar sin un LLM para:

- comandos;
- permisos y autorización;
- conversación de repertorio;
- preguntas cubiertas por el conocimiento local;
- WaifuMon;
- trivia;
- puntos;
- colección y evolución;
- catalogación y publicación;
- tareas durables y recuperación;
- observación agregada de Ciudad Animals.

## Opcional con IA

La IA solo se usa cuando la configuración la habilita y cuando la petición entra en la superficie explícitamente diseñada para lenguaje natural.

La IA no decide:

- canon del personaje;
- permisos;
- puntos;
- resultado de un juego;
- captura;
- publicación durable;
- identidad de otro personaje;
- una decisión humana de Tío Otaku.

## Automatización externa

WhatsApp y Messenger pueden recibir mensajes salientes desde el adaptador Meta cuando existen las credenciales y permisos necesarios.

Eso no significa que el programa pueda escribir arbitrariamente a cualquier persona.

La plataforma externa controla:

- quién puede recibir mensajes;
- qué identificador de destinatario es válido;
- qué ventana/regla de mensajería aplica;
- qué permisos tiene el token;
- si el contenido o la acción están permitidos.

El adaptador debe considerarse una herramienta de transporte, no una autorización para contactar personas sin permiso.

## Tío Otaku

Tío Otaku sigue siendo una persona. El sistema puede transportar una solicitud y, mediante los flujos existentes, enviar el texto exacto que el operador decide.

No se genera una respuesta fingiendo ser la persona.

## Principio

```text
datos locales
   ↓
reglas deterministas
   ↓
acción autorizada
   ├── Telegram
   ├── WhatsApp
   └── Messenger
```

Los proveedores externos no se convierten en parte de la autoridad del mundo de Ciudad Animals. El Core conserva la lógica y los estados propios del proyecto.