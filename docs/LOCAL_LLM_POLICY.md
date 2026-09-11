# Política de modelos locales

BOT-IA puede usar Ollama como capacidad local opcional, pero no como sustituto automático de la biblioteca ni de la evidencia.

## Orden de decisión

1. Biblioteca / evidencia local.
2. Modelo local, si la tarea admite generación local y está habilitado.
3. API externa sólo con autorización explícita.
4. Si ninguna ruta ofrece evidencia suficiente, BOT-IA debe reconocer la limitación.

Un modelo local puede redactar, transformar o proponer; no obtiene autoridad de canon por el mero hecho de generar una respuesta.

## Perfil inicial del equipo objetivo

El equipo actual dispone de 16 GB de RAM y una Radeon integrada con memoria gráfica limitada. Por ello, la política inicial es:

- modelos pequeños primero;
- una solicitud paralela por modelo;
- contexto moderado;
- modelo descargado sólo cuando sea necesario;
- sin proceso LLM residente obligatorio;
- sin vector DB obligatoria;
- sin embeddings obligatorios.

Esta política puede relajarse después de medir el consumo real, pero no debe endurecerse mediante suposiciones.
