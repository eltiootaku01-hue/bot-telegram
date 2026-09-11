# Experimento Ollama local

Este experimento queda separado del núcleo hasta medirlo en el PC real.

## Objetivo

Probar BOT-IA con Ollama y `qwen3:1.7b` sin una API remota. Ollama expone un endpoint local en `http://127.0.0.1:11434`; para uso local no hace falta una clave de API. La implementación principal de BOT-IA ya contiene un adaptador Ollama sin autenticación y con `keep_alive = 0`, por lo que el modelo puede descargarse de la RAM después de cada petición.

## Prueba

1. Instalar Ollama.
2. Ejecutar `ollama pull qwen3:1.7b`.
3. Mantener Ollama disponible sólo durante la prueba.
4. Ejecutar `python experimental/ollama/probe.py`.

El modelo oficial `qwen3:1.7b` ocupa aproximadamente 1.4 GB en Q4_K_M. En el PC de BOT-IA se debe considerar una prueba CPU/RAM, no una promesa de velocidad.

## Criterio para integrarlo

Se integrará al flujo principal sólo si responde de forma estable, no bloquea la interfaz, respeta la regla anti-invención y el consumo de memoria/latencia resulta razonable para 16 GB de RAM y gráficos integrados.
