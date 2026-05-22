#!/usr/bin/env python3
"""Finalize a generic pixel-sprite run into strict grid assets and QA files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_step(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    print("+ " + " ".join(command))
    return subprocess.run(command, check=check)


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def review_failures(review: dict[str, object]) -> list[str]:
    actions = review.get("actions")
    if not isinstance(actions, list):
        return ["review did not contain action-level results"]
    failures = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        errors = action.get("errors")
        if isinstance(errors, list) and errors:
            failures.append(f"{action.get('action')}: {'; '.join(str(error) for error in errors)}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--allow-slot-extraction", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--skip-contact-sheet", action="store_true")
    parser.add_argument("--key-threshold", type=float, default=96.0)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    run_dir = Path(args.run_dir).expanduser().resolve()
    final_png = run_dir / "final" / "spritesheet.png"
    validation_json = run_dir / "final" / "validation.json"
    review_json = run_dir / "qa" / "review.json"
    contact_sheet = run_dir / "qa" / "contact-sheet.png"

    if not args.skip_extract:
        run_step([sys.executable, str(script_dir / "extract_strip_frames.py"), "--run-dir", str(run_dir), "--key-threshold", str(args.key_threshold)])
    review_command = [sys.executable, str(script_dir / "inspect_sprite_frames.py"), "--run-dir", str(run_dir), "--json-out", str(review_json)]
    if not args.allow_slot_extraction:
        review_command.append("--require-components")
    run_step(review_command, check=False)
    review = load_json(review_json)
    if not review.get("ok"):
        print(
            json.dumps(
                {
                    "ok": False,
                    "review": str(review_json),
                    "repair_hint": "Regenerate the smallest failing action strip with $imagegen, record it again, then finalize again. Pass --allow-slot-extraction only after visually accepting slot-sliced frames.",
                    "failures": review_failures(review),
                },
                indent=2,
            )
        )
        raise SystemExit(1)
    run_step([sys.executable, str(script_dir / "compose_spritesheet.py"), "--run-dir", str(run_dir), "--output", str(final_png)])
    run_step([sys.executable, str(script_dir / "validate_spritesheet.py"), str(final_png), "--run-dir", str(run_dir), "--json-out", str(validation_json)])
    if not args.skip_contact_sheet:
        run_step([sys.executable, str(script_dir / "make_contact_sheet.py"), str(final_png), "--run-dir", str(run_dir), "--output", str(contact_sheet)])

    result = {
        "ok": True,
        "spritesheet": str(final_png),
        "manifest": str(run_dir / "final" / "spritesheet-manifest.json"),
        "review": str(review_json),
        "validation": str(validation_json),
        "contact_sheet": str(contact_sheet) if not args.skip_contact_sheet else None,
    }
    (run_dir / "qa" / "run-summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
