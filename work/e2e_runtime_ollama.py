from pathlib import Path
import shutil
import time

from bot_ia.runtime import build_runtime
from bot_ia.contracts import (
    AuthorityLevel,
    CanonStatus,
    SourceStatus,
    UniverseDefinition,
    UniverseRegistry,
)
from bot_ia.core import LocalBrain, Router
from bot_ia.core.application import (
    ApplicationRequest,
    BotApplication,
    InMemorySessionStore,
)
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.librarian import SourceInventory, SourceMetadata, SourceType
from bot_ia.memory import MemoryStore


root = Path(".").resolve()

runtime = build_runtime(root)
ollama_config = runtime.config.provider("ollama")

print("OLLAMA_CONFIG:")
print("  provider:", ollama_config.provider_id)
print("  model:", ollama_config.model)
print("  max_output_tokens:", ollama_config.max_output_tokens)
print("  timeout_seconds:", ollama_config.timeout_seconds)

test_root = root / "work" / "e2e_runtime_test"

if test_root.exists():
    shutil.rmtree(test_root)

test_root.mkdir(parents=True)

universe_folder = test_root / "alpha_world"
universe_folder.mkdir()

registry = UniverseRegistry()

registry.register(
    UniverseDefinition(
        "alpha_world",
        "Alpha",
        universe_folder,
    )
)

(universe_folder / "fact.md").write_text(
    "Kuro protege Alpha.",
    encoding="utf-8",
)

entries = {
    "alpha_world": SourceInventory(universe_folder).discover(
        "alpha_world",
        {
            "fact.md": SourceMetadata(
                "alpha_fact",
                SourceType.CHAPTER,
                AuthorityLevel.PRIMARY,
                SourceStatus.VALIDATED,
                CanonStatus.CANON,
            )
        },
    )
}

memory = MemoryStore(test_root, registry)

workflow = LocalWorkflow(
    entries,
    memory_store=memory,
    provider_manager=runtime.provider_manager,
    provider_config=ollama_config,
)

app = BotApplication(
    LocalBrain(registry),
    Router(),
    InMemorySessionStore(),
    default_universe_id="alpha_world",
    executor=workflow,
)

start = time.monotonic()

response = app.handle(
    ApplicationRequest(
        "u1",
        "c1",
        "Escribe una escena muy breve en la que Kuro protege Alpha. Responde en una sola frase.",
    )
)

provider_response = response.execution.provider_response

print()
print("RESULT:")
print("  total_seconds:", round(time.monotonic() - start, 2))
print("  text:", repr(response.text))
print("  provider:", provider_response.provider if provider_response else None)
print("  model:", provider_response.model if provider_response else None)
print("  status:", provider_response.status if provider_response else None)
print("  error_type:", provider_response.error_type if provider_response else None)
print("  output:", repr(provider_response.output_text) if provider_response else None)
print("  usage:", provider_response.usage if provider_response else None)

memory.close()
