# Tío Otaku — operador humano del Café Otaku

Fecha de referencia: 2026-09-15

## Concepto

Tío Otaku es un personaje operativo de Ciudad Animals cuyo **contenido visible es escrito manualmente por el operador humano**. El sistema proporciona la infraestructura para recibir, mostrar, organizar y enviar mensajes de Telegram, pero no redacta respuestas automáticas en nombre de Tío Otaku.

## Separación de responsabilidades

| Capa | Responsabilidad |
| --- | --- |
| Telegram | transporte de mensajes, grupos, permisos y eventos disponibles para la cuenta |
| Cliente/interfaz del proyecto | bandeja de entrada, selección de chat, editor de respuesta y estado del operador |
| Sistema central | reglas, estado, historial técnico y herramientas del Café Otaku |
| Operador | interpretar, investigar, decidir y redactar la respuesta |
| IA | opcional; no participa en la respuesta de Tío Otaku por defecto |

## Flujo manual

`Telegram → bandeja → operador lee → operador investiga si hace falta → operador redacta → envío → registro técnico`

## Uso de conocimiento

Cuando Tío Otaku necesite una respuesta factual, el operador puede consultar manualmente fuentes externas y redactar una respuesta propia. El sistema puede conservar posteriormente una ficha local estructurada si el dato merece formar parte del conocimiento estable del Café Otaku.

La IA no es requisito para buscar, comprender o redactar esas respuestas.

## Relación con los otros personajes

Tío Otaku funciona como personal humano del Café Otaku, por ejemplo encargado, barista, tendero u operador del local. Puede convivir con Cari, Sunna, Cami y Chie sin compartir su mecanismo de respuesta.

- Cari: interacción social y anfitriona.
- Sunna: juegos, colección y desafíos.
- Cami: archivo, datos y publicaciones.
- Chie: coordinación y avisos.
- Tío Otaku: intervención humana y operación del café.

## Regla de seguridad del diseño

No se debe activar accidentalmente una ruta de LLM que sustituya al operador. Cualquier automatización futura para Tío Otaku debe ser una característica separada, explícita y desactivada por defecto.

## Implicación para la arquitectura

La futura interfaz de Tío Otaku debe reutilizar el Core, la base de datos, permisos y servicios existentes, pero tener un flujo de operador claramente separado de los compositores authored-only de los personajes automáticos.
