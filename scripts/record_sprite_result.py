#!/usr/bin/env python3
"""Record a selected image generation output for a generic pixel-sprite job."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

CANONICAL_BASE_PATH = "references/canonical-base.png"


def load_manifest(run_dir: Path) -> dict[str, object]:
    path = run_dir / "imagegen-jobs.json"
    if not path.is_file():
        raise SystemExit(f"job manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def job_list(manifest: dict[str, object]) -> list[dict[str, object]]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise SystemExit("invalid imagegen-jobs.json: jobs must be a list")
    return [job for job in jobs if isinstance(job, dict)]


def find_job(manifest: dict[str, object], job_id: str) -> dict[str, object]:
    for job in job_list(manifest):
        if job.get("id") == job_id:
            return job
    raise SystemExit(f"unknown job id: {job_id}")


def completed_job_ids(manifest: dict[str, object]) -> set[str]:
    return {str(job["id"]) for job in job_list(manifest) if job.get("status") == "complete" and isinstance(job.get("id"), str)}


def image_metadata(path: Path) -> dict[str, object]:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return {"width": image.width, "height": image.height, "mode": image.mode, "format": image.format}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def generated_images_root() -> Path:
    return Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser().resolve() / "generated_images"


def validate_source(source: Path, run_dir: Path, allow_any_source: bool) -> str:
    if allow_any_source:
        return "allowed-local-source"
    if is_relative_to(source, run_dir):
        raise SystemExit("source image is inside the run directory; record the original imagegen output instead")
    root = generated_images_root()
    if not is_relative_to(source, root) or not source.name.startswith("ig_"):
        raise SystemExit(f"expected a built-in $imagegen output under {root}\\...\\ig_*.png; pass --allow-any-source for tests/manual migration")
    return "built-in-imagegen"


def manifest_relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-any-source", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"source image not found: {source}")
    provenance = validate_source(source, run_dir, args.allow_any_source)
    manifest = load_manifest(run_dir)
    job = find_job(manifest, args.job_id)
    missing_deps = [dep for dep in job.get("depends_on", []) if isinstance(dep, str) and dep not in completed_job_ids(manifest)]
    if missing_deps:
        raise SystemExit(f"job {args.job_id} is not ready; missing dependencies: {', '.join(missing_deps)}")
    output_raw = job.get("output_path")
    if not isinstance(output_raw, str):
        raise SystemExit(f"job {args.job_id} has no output_path")
    output = run_dir / output_raw
    if output.exists() and not args.force:
        raise SystemExit(f"{output} already exists; pass --force to replace it")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    metadata = image_metadata(output)

    job["status"] = "complete"
    job["source_path"] = str(source)
    job["source_provenance"] = provenance
    job["source_sha256"] = file_sha256(source)
    job["output_sha256"] = file_sha256(output)
    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    job["metadata"] = metadata
    if args.job_id == "base":
        canonical = run_dir / CANONICAL_BASE_PATH
        canonical.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, canonical)
        job["canonical_reference_path"] = manifest_relative(canonical, run_dir)
        request_path = run_dir / "sprite_request.json"
        if request_path.is_file():
            request = json.loads(request_path.read_text(encoding="utf-8"))
            request["canonical_identity_reference"] = {"path": job["canonical_reference_path"], "source_job": "base", "sha256": file_sha256(canonical)}
            request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")

    (run_dir / "imagegen-jobs.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "job_id": args.job_id, "output": str(output), "metadata": metadata}, indent=2))


if __name__ == "__main__":
    main()
