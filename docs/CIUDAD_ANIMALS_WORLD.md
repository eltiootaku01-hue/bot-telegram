# Ciudad Animals — mundo y memoria de observación

Ciudad Animals es el nombre de trabajo del pequeño mundo donde Cari, Sunna, Cami y Chie conservan su identidad propia.

La regla principal es que **el comportamiento cotidiano no depende de una IA generativa**. Cada personaje tiene un trabajo, un libreto, límites, hábitos, relaciones y un repertorio de respuestas. Repetir una respuesta ocasionalmente no es un defecto: puede ser parte del personaje.

## Qué observa el sistema

El proyecto guarda estadísticas agregadas y pequeñas fichas de catálogo para saber qué partes del mundo se usan realmente.

Ejemplos de entradas:

- `topic:hombres_lobo`
- `topic:gatos`
- `action:gacha`
- `action:trivia`
- `scene:cari_no_se`
- `scene:chie_interviene`

Las estadísticas se pueden registrar para todo el mundo o para un usuario concreto. Se guarda la cantidad y las fechas de primera/última aparición; no se necesita conservar el texto libre de la conversación para producir estas métricas.

## Qué puede descubrir una revisión

Una revisión puede producir cuatro señales sencillas:

1. **Caliente:** temas/acciones usados muchas veces recientemente.
2. **Frío:** entradas que existen pero casi no se usan.
3. **Nunca usado:** entradas declaradas en el catálogo que todavía no aparecen en las observaciones.
4. **Preferencias por usuario:** qué acciones o temas repite cada usuario.

Ejemplo conceptual:

```text
Hombres lobo  ██████████  24
Anime         ███████     16
Gatos         ░            0  ← catalogado, todavía sin uso
```

## Intervención de IA: externa al funcionamiento diario

La IA no decide cada respuesta de las chicas. Puede utilizarse como **curadora periódica** de Ciudad Animals:

```text
vida normal del mundo
        ↓
observaciones agregadas
        ↓
revisión diaria pequeña o semanal profunda
        ↓
IA analiza tendencias
        ↓
propone cambios
        ↓
aprobación humana
        ↓
se incorpora nuevo libreto / tema / escena
```

La IA puede sugerir, por ejemplo:

> “Hombres lobo está siendo el tema más usado. Gatos existe en el catálogo pero nadie lo tocó. Podrían añadirse dos escenas de Cari y una intervención de Sunna relacionadas con hombres lobo, sin eliminar gatos.”

La IA **no modifica automáticamente el mundo en esta primera etapa**. Las propuestas deben convertirse en cambios deliberados del catálogo/libreto.

## Memoria ligera

La memoria operacional debe favorecer agregados pequeños sobre registros pesados. Una ficha de usuario puede terminar conceptualmente así:

```text
usuario 42
├─ gacha: 17
├─ trivia: 6
├─ tema:hombres_lobo: 9
├─ tema:gatos: 0
└─ escena:cari_no_se: 3
```

Esto permite detectar costumbres sin ejecutar un modelo de lenguaje.

## Ritmo recomendado

- **Diario:** revisión muy pequeña, centrada en cambios recientes.
- **Semanal:** revisión más completa de tendencias, temas olvidados y oportunidades de expansión del libreto.

Una frecuencia diaria no es necesaria para que el sistema funcione. La observación ocurre durante el uso; la revisión puede esperar.

## Estado de esta primera etapa

Implementado:

- catálogo persistente de elementos del mundo;
- catálogo autoral definido en `app/services/world_catalog.py`;
- carga idempotente del catálogo al arrancar el módulo Core compartido (`SystemModule`);
- contador agregado por bot, ámbito y entrada;
- ámbito global y ámbito por usuario/usuario+chat;
- primera/última observación;
- consulta de entradas más usadas y menos usadas;
- detección de entradas catalogadas todavía no usadas;
- observación de escenas de diálogo y de acciones reales de Cari, Sunna, Cami y Chie;
- consulta de `/mundo` desde el panel privado de Chie para señales agregadas;
- comando privado `/borrar_mi_memoria` para que cada integrante pueda eliminar sus estadísticas de usuario y usuario+chat;
- panel privado de Chie para revisar señales agregadas;
- pruebas de agregación, separación de ámbitos y cobertura del catálogo;
- conversación determinista de las cuatro identidades sin dependencia del LLM;
- sincronización persistente de altas, bajas y restricciones de miembros de Telegram;
- Chie mantiene personalidad operativa sin inventar una biblia narrativa que todavía no existe.

El mundo sigue siendo deliberadamente pequeño y curado: las métricas describen uso real, pero la IA no puede convertir esas métricas en canon automáticamente. La expansión del libreto, nuevas relaciones y hechos narrativos continúan siendo cambios autorales explícitos.
