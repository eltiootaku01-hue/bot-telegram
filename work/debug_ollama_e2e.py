from pathlib import Path
import tempfile
import time

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
from bot_ia.providers import OllamaProvider, ProviderManager
from bot_ia.providers.adapters import _stdlib_transport


root = Path(tempfile.mkdtemp())

registry = UniverseRegistry()
registry.register(
    UniverseDefinition(
        "alpha_world",
        "Alpha",
        root / "alpha_world",
    )
)

folder = root / "alpha_world"
folder.mkdir()

(folder / "fact.md").write_text(
    "Kuro protege Alpha.",
    encoding="utf-8",
)

entries = {
    "alpha_world": SourceInventory(folder).discover(
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

memory = MemoryStore(root, registry)


def transport(url, headers, payload, timeout):
    print("TRANSPORT_START")
    print("URL:", url)
    print("TIMEOUT:", timeout)
    print("PAYLOAD:", payload)

    start = time.monotonic()

    result = _stdlib_transport(
        url,
        headers,
        payload,
        timeout,
    )

    print(
        "TRANSPORT_SECONDS:",
        round(time.monotonic() - start, 2),
    )

    return result


provider = OllamaProvider(
    transport=transport,
)

workflow = LocalWorkflow(
    entries,
    memory_store=memory,
    provider_manager=ProviderManager((provider,)),
    provider_id="ollama",
    provider_model="qwen3:1.7b-q4_K_M",
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

print(
    "TOTAL_SECONDS:",
    round(time.monotonic() - start, 2),
)

provider_response = response.execution.provider_response

print(
    "STATUS:",
    provider_response.status,
)

print(
    "ERROR:",
    provider_response.error_type,
)

print(
    "OUTPUT:",
    repr(provider_response.output_text),
)

memory.close()
