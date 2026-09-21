from __future__ import annotations

import json
import sys
from pathlib import Path


ART_MANIFEST = Path("assets/waifus/art_manifest.json")
QA_MANIFEST = Path("assets/waifus/card_art_qa_manifest.json")
PRODUCTION_ROOT = Path("assets/production/cards/")
SUPPORTED_VARIANTS = {"normal", "shiny", "ur-alt-holo"}


def _required_variant_checks(qa: dict, variant: dict) -> tuple[str, ...]:
    if variant["variant_id"] == "ur-alt-holo":
        return tuple(qa["ur_variants"]["required_checks"])
    return tuple(qa["required_checks"])


def _validate_variant(
    *,
    qa: dict,
    item: dict,
    variant: dict,
    failures: list[str],
) -> None:
    variant_id = variant.get("variant_id")
    character_id = item["character_id"]
    if variant_id not in SUPPORTED_VARIANTS:
        failures.append(f"{character_id}: unsupported variant {variant_id!r}")
        return

    tier = item["art_tier"]
    if variant_id == "ur-alt-holo" and tier != "UR":
        failures.append(f"{character_id}: UR_ALT_HOLO variant declared outside UR")
    if variant_id == "ur-alt-holo" and variant.get("adult_gate_required") is not True:
        failures.append(f"{character_id}: UR_ALT_HOLO must require adult gate")
    if variant_id == "ur-alt-holo" and variant.get("adult_eligible") is not True:
        if variant.get("approved"):
            failures.append(f"{character_id}: UR_ALT_HOLO approved without adult_eligible=true")

    if variant.get("approved"):
        checks = variant.get("checks") or (
            item.get("checks", {}) if variant_id == "normal" else {}
        )
        for key in _required_variant_checks(qa, variant):
            if checks.get(key) is not True:
                failures.append(f"{character_id}/{variant_id}: approved without {key}")
        if not variant.get("reviewer"):
            failures.append(f"{character_id}/{variant_id}: approved without primary reviewer")
        if tier == "UR" and not variant.get("second_reviewer"):
            failures.append(f"{character_id}/{variant_id}: UR requires second_reviewer")
        production_file = Path(variant["production_file"])
        if not production_file.is_file():
            failures.append(
                f"{character_id}/{variant_id}: approved asset does not exist: {production_file}"
            )
    elif variant.get("reviewer") or variant.get("reviewed_at") or variant.get("second_reviewer"):
        failures.append(f"{character_id}/{variant_id}: unapproved variant contains review metadata")


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

    if qa.get("matrix_version") != "2026-09-card-art-matrix-v2":
        failures.append("QA manifest must use card-art matrix v2")
    if art.get("matrix_version") != "2026-09-card-art-matrix-v2":
        failures.append("Art manifest must use card-art matrix v2")

    required = tuple(qa["required_checks"])
    for character_id, item in qa_items.items():
        if item["art_tier"] == "UR":
            expected_variants = {"normal", "ur-alt-holo"}
        else:
            expected_variants = {"normal"}

        declared = set(item.get("variant_support", []))
        if declared != expected_variants:
            failures.append(
                f"{character_id}: variant_support {sorted(declared)} != {sorted(expected_variants)}"
            )

        variants = item.get("variants")
        if not isinstance(variants, list):
            failures.append(f"{character_id}: variants must be a list")
            variants = []

        variant_ids = {variant.get("variant_id") for variant in variants}
        if variant_ids != expected_variants:
            failures.append(f"{character_id}: variant list does not match supported variants")

        for variant in variants:
            _validate_variant(qa=qa, item=item, variant=variant, failures=failures)

        checks = item["checks"]
        if item["approved"]:
            if any(checks.get(key) is not True for key in required):
                failures.append(f"{character_id}: approved without all required checks")
            if not item.get("reviewer"):
                failures.append(f"{character_id}: approved without primary reviewer")
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
    approved_variants = sum(
        1
        for item in qa_items.values()
        for variant in item.get("variants", [])
        if variant.get("approved")
    )
    print(
        f"Card visual QA contract validated: {len(qa_items)} cards tracked, "
        f"{approved} canonical cards approved, {approved_variants} variants approved."
    )
    if approved == 0 and approved_variants == 0:
        print("No card or variant has been visually approved yet; this is valid pre-production state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
