# Conversaciones humanas como fuente de mejora

El proyecto puede mejorar sus respuestas usando conversaciones reales, pero esas
conversaciones deben entrar como material revisado, no como memoria automática.

## Formato recomendado

Un ejemplo anonimizado puede representarse así:

```json
{
  "identity": "cari",
  "intent": "reassurance",
  "user_text": "¿estás bien?",
  "approved_response": "Sí, estoy bien. Gracias por preguntar. ¿Vos cómo estás?",
  "notes": "tono cercano; una pregunta de seguimiento"
}
```

No se deben incluir nombres reales, teléfonos, identificadores de Telegram, direcciones,
tokens ni otros datos que no sean necesarios para aprender el patrón de conversación.

## Flujo

```
chat autorizado/exportado
        ↓
anonimización
        ↓
clasificación de intención
        ↓
revisión humana
        ↓
respuesta aprobada
        ↓
KnowledgeArticle / escena de repertorio
        ↓
prueba de regresión
        ↓
runtime
```

El objetivo es aprender **cómo responder**, no conservar una copia permanente del chat.

## Qué conviene extraer

- formas reales de preguntar;
- sinónimos y expresiones coloquiales;
- secuencias de conversación que el router actual no detecta;
- respuestas que funcionaron bien;
- casos que deben derivarse a una persona;
- límites donde el bot debe decir "no lo sé".

## Qué no se debe extraer automáticamente

No convertir una conversación privada en:

- hecho canónico del mundo;
- perfil psicológico de una persona;
- diagnóstico;
- permiso para contactar a terceros;
- información personal persistente.

## Referencia de ingeniería conversacional

Rasa describe Conversation-Driven Development como un ciclo de revisar conversaciones,
anotar fallos, convertir los aprendizajes en datos y comprobar que el asistente se comporte
como se espera. El proyecto toma esa idea de proceso, pero mantiene su propia implementación
determinista.

Fuente:
https://legacy-docs-oss.rasa.com/docs/rasa/conversation-driven-development/
