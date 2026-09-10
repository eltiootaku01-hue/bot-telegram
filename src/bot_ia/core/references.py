"""Resolución básica, determinista y aislada por universo."""

from __future__ import annotations

import re

from bot_ia.contracts import Confidence, SessionState

from .models import EntityCandidate, ReferenceResolution

_PRONOUNS = frozenset({"ella", "el", "él", "ellas", "ellos", "esa", "eso", "esta", "este"})


class ReferenceResolver:
    def resolve(
        self,
        normalized_message: str,
        universe_id: str,
        candidates: tuple[EntityCandidate, ...],
        state: SessionState | None,
    ) -> tuple[ReferenceResolution, ...]:
        scoped = tuple(candidate for candidate in candidates if candidate.universe_id == universe_id)
        explicit = self._explicit_matches(normalized_message, scoped)

        resolutions = [
            ReferenceResolution(name, (candidate.entity_id,), candidate.entity_id, Confidence.HIGH)
            for name, candidate in explicit
        ]

        tokens = set(re.findall(r"[\wáéíóúüñ]+", normalized_message, flags=re.UNICODE))
        if tokens & _PRONOUNS:
            mentioned = tuple(dict.fromkeys(candidate for _, candidate in explicit))

            if len(mentioned) > 1:
                resolutions.append(ReferenceResolution("pronoun", tuple(item.entity_id for item in mentioned), None, Confidence.LOW, True))
            elif len(mentioned) == 1:
                resolutions.append(ReferenceResolution("pronoun", (mentioned[0].entity_id,), mentioned[0].entity_id, Confidence.MEDIUM))
            elif state is not None:
                recent_ids = tuple(dict.fromkeys((*state.active_entity_ids, *state.recent_reference_ids)))
                recent = tuple(item for item in scoped if item.entity_id in recent_ids)
                if len(recent) == 1:
                    resolutions.append(ReferenceResolution("pronoun", (recent[0].entity_id,), recent[0].entity_id, Confidence.MEDIUM))
                elif len(recent) > 1:
                    ordered_ids = tuple(item_id for item_id in recent_ids if any(item.entity_id == item_id for item in recent))
                    resolutions.append(ReferenceResolution("pronoun", ordered_ids, None, Confidence.LOW, True))

        return tuple(resolutions)

    @staticmethod
    def _explicit_matches(text: str, candidates: tuple[EntityCandidate, ...]) -> tuple[tuple[str, EntityCandidate], ...]:
        found: list[tuple[str, EntityCandidate]] = []
        seen: set[str] = set()
        for candidate in candidates:
            names: list[str] = [candidate.name]
            for alias in candidate.aliases:
                names.append(alias)
                if "(" in alias:
                    base = alias.split("(", 1)[0].strip()
                    if base:
                        names.append(base)
            for name in names:
                if re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", text.casefold()):
                    if candidate.entity_id not in seen:
                        found.append((name, candidate))
                        seen.add(candidate.entity_id)
                    break
        return tuple(found)
