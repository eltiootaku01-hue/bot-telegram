from __future__ import annotations

from app.services.startup_sequence import StartupSequence


def test_startup_stops_on_first_failure() -> None:
    events: list[str] = []

    def launch(identity: str) -> object:
        events.append(f"launch:{identity}")
        if identity == "sunna":
            raise RuntimeError("boom")
        return identity

    def health(identity: str, process: object) -> bool:
        events.append(f"health:{identity}")
        return True

    def stop(identity: str, process: object) -> None:
        events.append(f"stop:{identity}")

    result = StartupSequence(("cari", "sunna", "cami"), launch, health, stop).run()

    assert result.started == ("cari",)
    assert result.failure is not None
    assert result.failure.identity == "sunna"
    assert events == ["launch:cari", "health:cari", "launch:sunna", "stop:cari"]


def test_failed_health_stops_already_started_processes() -> None:
    stopped: list[str] = []

    def launch(identity: str) -> object:
        return identity

    def health(identity: str, process: object) -> bool:
        return identity != "cami"

    def stop(identity: str, process: object) -> None:
        stopped.append(identity)

    result = StartupSequence(("cari", "sunna", "cami"), launch, health, stop).run()

    assert result.started == ("cari", "sunna")
    assert result.failure is not None
    assert result.failure.identity == "cami"
    assert stopped == ["sunna", "cari"]
