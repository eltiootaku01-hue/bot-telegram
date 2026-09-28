# Project Memory — Discoveries

## [TESTED] Observation Core

PR #62 implementa un Observation Core mínimo con modelos de observación/evidencia, observers de repositorio/archivos/comandos, verificación, almacenamiento local y auditoría. La validación FASE 2F-1V confirmó el alcance esperado en el HEAD `298748830af133079946f4d1eb8c87dedb8f4ea4`.

Limitación: esto no demuestra la implementación de las fases posteriores del Supervisor.

## [TESTED] Protección contra almacenamiento dentro del repositorio observado

La implementación actual rechaza la configuración en la que el almacenamiento de evidencia quedaría dentro del repositorio observado. Existe una prueba específica para este contrato.

Limitación: el formato y backend definitivos del Evidence Store futuro siguen abiertos.

## [OBSERVED] BOT-IA moderno

El README describe un Knowledge Engine con backend común para uso normal, Telegram y API web, con biblioteca, memoria y EvidenceGate. También documenta Chat Web y providers.

Limitación: esta memoria no interpreta esos elementos como autorización para modificar sus runtimes.

## [OBSERVED] Runtimes y componentes existentes

Las auditorías previas identificaron Telegram moderno, TaskEngine, TaskScheduler y WebQueue como componentes existentes. La FASE 2E estableció que el Supervisor debe observarlos y coordinarlos sin sustituir sus autoridades operativas.

## [INFERRED] TCG/TMA como dominio diferenciado

Las auditorías FASE 2B–2D encontraron separación funcional entre BOT-IA moderno y TCG/TMA, pero no evidencia suficiente para fijar una decisión histórica permanente sobre su destino arquitectónico.

## [OBSERVED] Documentación previa

Antes de esta persistencia existían documentos de arquitectura, auditorías y roadmaps, pero no se había identificado una carpeta canónica `docs/project_memory/` equivalente.

## [UNKNOWN] Investigación de mercado como fuente persistente

La investigación externa del ecosistema Café Otaku fue realizada en fases anteriores, pero no se identificó una fuente documental persistente completa dentro del repositorio que permita tratar todo su contenido como evidencia archivada.

## [UNKNOWN] Especificación final de personajes vivos

El concepto de personajes vivos, afinidad, percepción y reacción aparece como diseño conceptual/propuesto en las fases previas. No existe en esta memoria evidencia suficiente para describirlo como implementación.

## [OBSERVED] Disciplina de fases

Las fases 2F-1 y 2F-1V impusieron alcance estricto, verificación de diff y protección de runtimes. La persistencia actual conserva esa disciplina documentalmente.
