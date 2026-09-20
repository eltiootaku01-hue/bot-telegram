# Investigación técnica — conversación local y canales externos

Fecha: 2026-09-20

## Diseño conversacional

Rasa sigue siendo una referencia útil para dos ideas de ingeniería:

1. separar comprensión de lenguaje, reglas y manejo de diálogo;
2. revisar conversaciones reales, anotar fallos y convertirlos en casos de prueba.

El repositorio oficial de Rasa Open Source indica actualmente que el proyecto está en maintenance mode y presenta CALM/Hello Rasa como la dirección nueva. Por eso no se añade Rasa como dependencia del bot: solo se reutiliza la idea metodológica de revisar conversaciones.

Fuente: https://github.com/RasaHQ/rasa

Concepto CDD: https://legacy-docs-oss.rasa.com/docs/rasa/conversation-driven-development/

## Microsoft Bot Framework

El repositorio oficial de Bot Framework Python indica que el SDK está en proceso de archivado y que su ciclo de soporte terminó. No se incorpora como dependencia.

Fuente: https://github.com/microsoft/botbuilder-python

Esto refuerza la decisión de mantener el núcleo con aiogram y pequeños adaptadores propios, en vez de introducir un framework conversacional antiguo.

## WhatsApp

La colección oficial de Meta documenta WhatsApp Cloud API como la API de WhatsApp Business para mensajería programática. El flujo requiere activos de Meta Business y un número de negocio; el envío usa el Phone Number ID y el endpoint de mensajes.

Fuente: https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api

## Messenger / Facebook

La colección oficial de Meta para Messenger documenta el Send API para texto y attachments, incluyendo imágenes. El envío usa el Page ID, un Page Access Token y el identificador del destinatario correspondiente.

Fuente: https://www.postman.com/meta/messenger-platform-api/documentation/iyp204x/messenger-platform-api

## Psychological First Aid

Para la parte de conversación empática de Cari se adopta únicamente un subconjunto no clínico y seguro del marco de Psychological First Aid de la OMS:

- escuchar sin presionar;
- comprobar necesidades y seguridad;
- conectar con apoyos sociales/servicios;
- proteger frente a daños adicionales.

La aplicación del bot no diagnostica ni sustituye profesionales.

Fuente: https://www.who.int/publications/i/item/9789241548205

## Aplicación al proyecto

```text
conversación Telegram
        ↓
router determinista
        ↓
conocimiento local
        ↓
repertorio de personaje
        ↓
reglas / servicios
        ↓
IA opcional
```

y, cuando se requiera contacto externo:

```text
acción explícita autorizada
        ↓
MetaMessagingClient
        ├─ WhatsApp Cloud API
        └─ Messenger Send API
```

La IA sigue siendo una mejora opcional y no la autoridad del personaje.