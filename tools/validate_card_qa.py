from __future__ import annotations

import json
import sys
from pathlib import Path


ART_MANIFEST = Path("assets/waifus/art_manifest.json")
QA_MANIFEST = Path("assets/waifus/card_art_qa_manifest.json")
PRODUCTION_ROOT = Path("assets/production/cards")


def main() -> int:
    art = json.loads(ART_MANIFEST.read_text(encoding="utf-8"))
    qa = json.loads(QA_MANIFEST.read_text(encoding="utf-8"))

    art_items = {item["character_id"]: item for item in art["items"]}
    qa_items = {item["character_id"]: item for item in qa["items"]}

    failures: list[str] = []
    if art["matrix_version"] != qa["matrix_version"]:
        failures.append("QA manifest matrix_version does not match art manifest")
    if set(art_items) != set(qa_items):
        failures.append("QA manifest character set does not match art manifest")

    required = tuple(qa["required_checks"])
    for character_id, item in qa_items.items():
        checks = item["checks"]
        if item["approved"]:
            if any(checks.get(key) is not True for key in required):
                failures.append(f"{character_id}: approved without all required checks")
            if not item.get("reviewer"):
                failures.append(f"{character_id}: approved without primary reviewer")
            if not item.get("reviewed_at"):
                failures.append(f"{character_id}: approved without reviewed_at")
            if item["art_tier"] == "UR":
                if checks.get("second_review") is not True:
                    failures.append(f"{character_id}: UR approved without second_review")
                if not item.get("second_reviewer"):
                    failures.append(f"{character_id}: UR approved without second_reviewer")
            production_file = Path(item["production_file"])
            if not production_file.is_file():
                failures.append(f"{character_id}: approved asset does not exist: {production_file}")
        elif item["reviewer"] or item["reviewed_at"]:
            failures.append(f"{character_id}: unapproved item contains review metadata")

    if failures:
        print("Card visual QA contract FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    approved = sum(1 for item in qa_items.values() if item["approved"])
    print(
        f"Card visual QA contract validated: {len(qa_items)} cards tracked, "
        f"{approved} approved."
    )
    if approved == 0:
        print(
            "No card has been visually approved yet; this is valid pre-production state."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
