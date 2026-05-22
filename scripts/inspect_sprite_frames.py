#!/usr/bin/env python3
"""Inspect extracted pixel-sprite frames before spritesheet composition."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median

from PIL import Image

IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}


def alpha_nonzero_count(image: Image.Image) -> int:
    alpha = image if image.mode == "L" else image.getchannel("A")
    return sum(alpha.histogram()[1:])


def edge_alpha_count(image: Image.Image, margin: int) -> int:
    alpha = image.getchannel("A")
    width, height = alpha.size
    total = 0
    for box in (
        (0, 0, width, margin),
        (0, height - margin, width, height),
        (0, 0, margin, height),
        (width - margin, 0, width, height),
    ):
        total += alpha_nonzero_count(alpha.crop(box))
    return total


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def chroma_adjacent_count(image: Image.Image, chroma_key: tuple[int, int, int] | None, threshold: float) -> int:
    if chroma_key is None:
        return 0
    data = image.convert("RGBA").tobytes()
    count = 0
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index : index + 4]
        if alpha > 16 and color_distance((red, green, blue), chroma_key) <= threshold:
            count += 1
    return count


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def frame_files(action_dir: Path) -> list[Path]:
    if not action_dir.is_dir():
        return []
    return sorted(path for path in action_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)


def load_chroma_key(frames_manifest: dict[str, object]) -> tuple[int, int, int] | None:
    chroma_key = frames_manifest.get("chroma_key")
    if not isinstance(chroma_key, dict):
        return None
    rgb = chroma_key.get("rgb")
    if not isinstance(rgb, list) or len(rgb) != 3 or not all(isinstance(value, int) for value in rgb):
        return None
    return (rgb[0], rgb[1], rgb[2])


def manifest_actions(frames_manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    actions = frames_manifest.get("actions")
    if not isinstance(actions, list):
        return {}
    return {
        action["action"]: action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("action"), str)
    }


def inspect_action(
    run_dir: Path,
    action: dict[str, object],
    manifest_by_action: dict[str, dict[str, object]],
    chroma_key: tuple[int, int, int] | None,
    args: argparse.Namespace,
) -> dict[str, object]:
    action_id = str(action["id"])
    expected_count = int(action["frames"])
    expected_size = (int(args.cell_width), int(args.cell_height))
    manifest_action = manifest_by_action.get(action_id, {})
    method = manifest_action.get("method")
    files = frame_files(run_dir / "frames" / action_id)
    errors: list[str] = []
    warnings: list[str] = []
    frames: list[dict[str, object]] = []
    areas: list[int] = []
    bbox_areas: list[int] = []

    if len(files) != expected_count:
        errors.append(f"expected {expected_count} frame files for {action_id}, found {len(files)}")
    if args.require_components and method and method != "components":
        errors.append(f"{action_id} used extraction method {method}; regenerate or explicitly allow slot extraction")
    elif method and method != "components":
        warnings.append(f"{action_id} used extraction method {method}; component extraction is preferred")

    for index, frame_path in enumerate(files[:expected_count]):
        with Image.open(frame_path) as opened:
            frame = opened.convert("RGBA")
        nontransparent = alpha_nonzero_count(frame)
        bbox = frame.getbbox()
        bbox_area = 0
        if bbox:
            bbox_area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
        edge_pixels = edge_alpha_count(frame, args.edge_margin)
        chroma_adjacent_pixels = chroma_adjacent_count(frame, chroma_key, args.chroma_adjacent_threshold)
        frames.append(
            {
                "index": index,
                "file": str(frame_path),
                "width": frame.width,
                "height": frame.height,
                "nontransparent_pixels": nontransparent,
                "bbox": list(bbox) if bbox else None,
                "bbox_area": bbox_area,
                "edge_pixels": edge_pixels,
                "chroma_adjacent_pixels": chroma_adjacent_pixels,
            }
        )
        areas.append(nontransparent)
        bbox_areas.append(bbox_area)
        if frame.size != expected_size:
            errors.append(f"{action_id} frame {index:02d} is {frame.width}x{frame.height}; expected {expected_size[0]}x{expected_size[1]}")
        if nontransparent < args.min_used_pixels:
            errors.append(f"{action_id} frame {index:02d} is empty or too sparse ({nontransparent} pixels)")
        if edge_pixels > args.edge_pixel_threshold:
            warnings.append(f"{action_id} frame {index:02d} has {edge_pixels} non-transparent pixels near the cell edge")
        if chroma_adjacent_pixels > args.chroma_adjacent_pixel_threshold:
            errors.append(f"{action_id} frame {index:02d} has {chroma_adjacent_pixels} non-transparent pixels close to the chroma key")

    if areas:
        row_median = median(areas)
        for index, area in enumerate(areas[:expected_count]):
            if row_median > 0 and area < row_median * args.small_outlier_ratio:
                warnings.append(f"{action_id} frame {index:02d} is much smaller than the action median ({area} vs {row_median:.0f})")
            if row_median > 0 and area > row_median * args.large_outlier_ratio:
                warnings.append(f"{action_id} frame {index:02d} is much larger than the action median ({area} vs {row_median:.0f})")
    if bbox_areas:
        bbox_median = median(bbox_areas)
        for index, bbox_area in enumerate(bbox_areas[:expected_count]):
            if bbox_median > 0 and bbox_area < bbox_median * args.small_bbox_outlier_ratio:
                warnings.append(f"{action_id} frame {index:02d} has a much smaller visible bounding box than the action median ({bbox_area} vs {bbox_median:.0f})")
            if bbox_median > 0 and bbox_area > bbox_median * args.large_bbox_outlier_ratio:
                warnings.append(f"{action_id} frame {index:02d} has a much larger visible bounding box than the action median ({bbox_area} vs {bbox_median:.0f})")

    return {
        "action": action_id,
        "expected_frames": expected_count,
        "actual_frames": len(files),
        "extraction_method": method,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "frames": frames,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--min-used-pixels", type=int, default=24)
    parser.add_argument("--edge-margin", type=int, default=2)
    parser.add_argument("--edge-pixel-threshold", type=int, default=24)
    parser.add_argument("--chroma-adjacent-threshold", type=float, default=150.0)
    parser.add_argument("--chroma-adjacent-pixel-threshold", type=int, default=800)
    parser.add_argument("--small-outlier-ratio", type=float, default=0.35)
    parser.add_argument("--large-outlier-ratio", type=float, default=2.75)
    parser.add_argument("--small-bbox-outlier-ratio", type=float, default=0.60)
    parser.add_argument("--large-bbox-outlier-ratio", type=float, default=1.45)
    parser.add_argument("--require-components", action="store_true", help="Fail actions that fell back to equal-slot extraction.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    request = load_json(run_dir / "sprite_request.json")
    frames_manifest = load_json(run_dir / "frames" / "frames-manifest.json")
    args.cell_width = int(request["cell_width"])
    args.cell_height = int(request["cell_height"])
    actions = request.get("actions")
    if not isinstance(actions, list):
        raise SystemExit("sprite_request.json actions must be a list")

    by_action = manifest_actions(frames_manifest)
    chroma_key = load_chroma_key(frames_manifest)
    rows = [
        inspect_action(run_dir, action, by_action, chroma_key, args)
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    ]
    errors = [error for row in rows for error in row["errors"]]
    warnings = [warning for row in rows for warning in row["warnings"]]
    result = {
        "ok": not errors,
        "run_dir": str(run_dir),
        "errors": errors,
        "warnings": warnings,
        "actions": rows,
    }
    output = Path(args.json_out).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "actions"}, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
