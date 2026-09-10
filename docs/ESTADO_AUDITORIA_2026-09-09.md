# Estado de auditoría y reparación — 2026-09-09/10

## Verificación
- CI ejecutado mediante GitHub Actions sobre la rama de auditoría.
- La primera ejecución posterior al cambio de providers falló únicamente por tests/documentación que todavía referenciaban Gemini y por dos pruebas nuevas que requerían ajustes.
- Esas regresiones están siendo reparadas antes de considerar el cambio terminado.
- La suite base previa a este cambio estaba en verde con 247 tests.

## Reparaciones de esta auditoría
1. Gemini deja de ser provider de runtime, configuración y documentación.
2. OpenAI pasa a ser provider predeterminado.
3. Groq queda habilitado como fallback.
4. Coze queda integrado como provider de agentes/API v3 y tercer fallback configurable, desactivado hasta aportar sus credenciales.
5. Se conserva soporte para múltiples cuentas/API keys por provider.
6. ProviderManager sigue la cadena de fallback declarada por configuración y evita ciclos.
7. Ollama permanece desactivado y limitado a `qwen3:1b` cuando se habilita explícitamente.
8. Tests de integración, secretos, factory y bootstrap se migran a los providers activos.
9. Se mantiene la separación entre recuperación factual del bibliotecario y generación por LLM: una ruta factual/search no llama al provider.
10. La respuesta factual continúa pasando por EvidenceGate y el contrato de salida.

## Bibliotecario y preguntas simples
El bibliotecario sigue siendo la fuente autoritativa para consultas factuales. Para una pregunta simple que se clasifica como búsqueda factual:

`usuario → Brain/Router → LocalLibrarian → EvidencePack → ContextBuilder → EvidenceGate → respuesta`

El provider remoto no se llama en esa ruta. Esto evita gastar API para preguntas que pueden resolverse directamente con evidencia local y evita que el LLM pueda reemplazar o elevar la evidencia.

Para tareas creativas o de razonamiento que sí requieren LLM, el contexto preparado por el bibliotecario llega al agente/provider con reglas explícitas de no invención y separación entre hechos, inferencias y propuestas.

## Estado
No se marca como terminado hasta que la suite completa vuelva a estar en verde después de la migración y se complete una prueba real con credenciales suministradas localmente por el usuario, sin guardar secretos en Git.
