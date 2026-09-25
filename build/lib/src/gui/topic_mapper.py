from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from src.service.topic_mapper import DynamicTopicMapper


IDENTITIES = ("cari", "sunna", "cami", "chie")


@dataclass(slots=True)
class TopicBinding:
    key: str
    thread_id: int
    assigned_bot: str
    zone: str
    x: float
    y: float

    @classmethod
    def from_dict(cls, key: str, value: dict) -> "TopicBinding":
        identity = str(value.get("assigned_bot", "")).casefold()
        if identity not in IDENTITIES:
            raise ValueError(f"unknown bot identity: {identity}")
        thread_id = int(value["thread_id"])
        x, y = value.get("zone_coords", [0, 0])
        return cls(key, thread_id, identity, str(value.get("zone", key)), float(x), float(y))

    def to_dict(self) -> dict:
        return {
            "thread_id": self.thread_id,
            "assigned_bot": self.assigned_bot,
            "zone": self.zone,
            "zone_coords": [self.x, self.y],
        }


class TopicMapper:
    """Validated, deterministic binding between Telegram forum threads and café zones."""

    def __init__(self, path: str | Path = "config/forum_topics.json") -> None:
        self.path = Path(path)
        self._topics: dict[str, TopicBinding] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._topics = {}
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        raw = data.get("topics", {}) if isinstance(data, dict) else {}
        if not isinstance(raw, dict):
            raise ValueError("forum topic mapping must contain an object named 'topics'")
        topics = {str(key): TopicBinding.from_dict(str(key), value) for key, value in raw.items()}
        self._validate(topics)
        self._topics = topics

    def _validate(self, topics: dict[str, TopicBinding]) -> None:
        thread_ids = [item.thread_id for item in topics.values()]
        if len(thread_ids) != len(set(thread_ids)):
            raise ValueError("message_thread_id values must be unique")
        assignments: dict[str, str] = {}
        for item in topics.values():
            previous = assignments.get(item.assigned_bot)
            if previous is not None:
                raise ValueError(
                    f"bot {item.assigned_bot} is assigned to both {previous} and {item.key}"
                )
            assignments[item.assigned_bot] = item.key

    def load_dynamic(self, chat_id: int, db_path: str = "data/command_center_events.db") -> int:
        """Overlay persisted Telegram thread IDs for a bootstrapped chat."""
        dynamic = DynamicTopicMapper(db_path, self.path).for_chat(chat_id)
        if not dynamic:
            return 0
        changed = 0
        by_key = {binding.key: binding for binding in self._topics.values()}
        for topic_name, mapping in dynamic.items():
            target = by_key.get(topic_name)
            if target is None:
                target = next(
                    (item for item in self._topics.values()
                     if item.zone.casefold() == topic_name.casefold()),
                    None,
                )
            if target is not None and target.thread_id != mapping.message_thread_id:
                target.thread_id = mapping.message_thread_id
                changed += 1
        self._validate(self._topics)
        return changed

    def bindings(self) -> tuple[TopicBinding, ...]:
        return tuple(self._topics.values())

    def for_bot(self, identity: str) -> TopicBinding | None:
        identity = identity.casefold()
        return next((item for item in self._topics.values() if item.assigned_bot == identity), None)

    def assign(self, identity: str, thread_id: int, key: str, zone: str, x: float, y: float) -> TopicBinding:
        identity = identity.casefold()
        if identity not in IDENTITIES:
            raise ValueError(f"unknown bot identity: {identity}")
        if any(item.thread_id == thread_id and item.assigned_bot != identity for item in self._topics.values()):
            raise ValueError(f"thread_id {thread_id} is already assigned")
        for old_key, item in list(self._topics.items()):
            if item.assigned_bot == identity:
                del self._topics[old_key]
        binding = TopicBinding(key, int(thread_id), identity, zone, float(x), float(y))
        candidate = dict(self._topics)
        candidate[key] = binding
        self._validate(candidate)
        self._topics = candidate
        return binding

    def reassign_thread(self, identity: str, thread_id: int) -> TopicBinding:
        """Rebind an existing bot to a new Telegram forum thread without changing its zone."""
        binding = self.for_bot(identity)
        if binding is None:
            raise ValueError(f"no mapping exists for {identity}")
        thread_id = int(thread_id)
        if thread_id <= 0:
            raise ValueError("thread_id must be positive")
        for item in self._topics.values():
            if item.thread_id == thread_id and item.assigned_bot != identity.casefold():
                raise ValueError(f"thread_id {thread_id} is already assigned")
        binding.thread_id = thread_id
        self._validate(self._topics)
        return binding

    def save(self) -> None:
        self._validate(self._topics)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"topics": {key: binding.to_dict() for key, binding in self._topics.items()}}
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def export(self) -> dict:
        return {"topics": {key: binding.to_dict() for key, binding in self._topics.items()}}
