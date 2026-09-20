# Mensajería externa: WhatsApp y Messenger/Facebook

El proyecto puede enviar mensajes desde una cuenta de WhatsApp Business o una Página de
Facebook mediante adaptadores aislados.

## WhatsApp Business

El adaptador usa WhatsApp Cloud API y el endpoint de mensajes asociado al Phone Number ID.

Requiere:

- un Meta Business Portfolio;
- una cuenta de WhatsApp Business;
- un número de negocio;
- el access token correspondiente;
- el Phone Number ID.

Para mensajes salientes se usa el recurso `/{Phone-Number-ID}/messages`.
El cliente implementado soporta texto e imágenes mediante URL.

Fuente de Meta:
https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api

## Messenger / Facebook Page

El adaptador usa Messenger Send API.

Requiere:

- una Página de Facebook;
- Page Access Token;
- `pages_messaging`;
- el identificador de la persona receptora (PSID);
- que la conversación cumpla las reglas de mensajería aplicables de Meta.

El Send API usa `/{PAGE-ID}/messages` y permite texto y attachments de imagen.

Fuente de Meta:
https://www.postman.com/meta/messenger-platform-api/documentation/iyp204x/messenger-platform-api

## Versión de Graph API

La configuración predeterminada del proyecto es `v26.0`, publicada el 29 de julio de
2026 según el changelog de versiones de Graph API. Se mantiene configurable en
`META_GRAPH_API_VERSION` para evitar acoplar el código a una versión futura.

## Seguridad

Los tokens nunca deben entrar en el repositorio.
Se cargan mediante `.env`/Pydantic Settings y el cliente no imprime el token en errores.

El adaptador es saliente. Para recibir mensajes y eventos desde WhatsApp o Messenger
hará falta añadir webhooks públicos de Meta y vincularlos al sistema de entrada.

## Flujo recomendado

```
Cari/Cami/Chie
      ↓
servicio de contacto
      ↓
MetaMessagingClient
      ↓
WhatsApp Cloud API / Messenger Send API
      ↓
persona receptora
```

La capa de personaje no conoce los detalles HTTP de Meta; eso permite cambiar de proveedor
sin reescribir las identidades.
