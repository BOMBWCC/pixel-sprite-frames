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


def image_bbox_from_mask(image: Image.Image, predicate) -> tuple[int, int, int, int] | None:
    pixels = image.convert("RGBA").load()
    min_x = image.width
    min_y = image.height
    max_x = -1
    max_y = -1
    count = 0
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 16 and predicate(red, green, blue):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                count += 1
    if count == 0:
        return None
    return (min_x, min_y, max_x + 1, max_y + 1)


def core_body_predicate(subject: str):
    lowered = subject.lower()
    if any(term in lowered for term in ("black", "dark", "shadow", "charcoal")):
        return lambda red, green, blue: max(red, green, blue) <= 120 and (red + green + blue) <= 270
    return lambda red, green, blue: True


def compute_bbox_area(bbox: tuple[int, int, int, int] | None) -> int:
    if bbox is None:
        return 0
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


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
    size_target = action.get("size_target") if isinstance(action.get("size_target"), dict) else None
    subject = str(args.subject)
    core_predicate = core_body_predicate(subject)
    expected_size = (int(args.cell_width), int(args.cell_height))
    manifest_action = manifest_by_action.get(action_id, {})
    method = manifest_action.get("method")
    files = frame_files(run_dir / "frames" / action_id)
    errors: list[str] = []
    warnings: list[str] = []
    frames: list[dict[str, object]] = []
    areas: list[int] = []
    bbox_areas: list[int] = []
    ground_ys: list[int] = []
    core_areas: list[int] = []

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
        visible_bbox_area = compute_bbox_area(bbox)
        core_bbox = image_bbox_from_mask(frame, core_predicate)
        core_body_area = compute_bbox_area(core_bbox)
        core_body_pixels = 0
        if core_bbox is not None:
            data = frame.convert("RGBA").tobytes()
            core_body_pixels = sum(
                1
                for index in range(0, len(data), 4)
                for red, green, blue, alpha in (data[index : index + 4],)
                if alpha > 16 and core_predicate(red, green, blue)
            )
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
                "ground_anchor_y": bbox[3] if bbox else None,
                "bbox_area": visible_bbox_area,
                "core_body_pixels": core_body_pixels,
                "core_body_bbox": list(core_bbox) if core_bbox else None,
                "core_body_bbox_area": core_body_area,
                "edge_pixels": edge_pixels,
                "chroma_adjacent_pixels": chroma_adjacent_pixels,
            }
        )
        areas.append(nontransparent)
        bbox_areas.append(visible_bbox_area)
        if bbox:
            ground_ys.append(bbox[3])
        core_areas.append(core_body_area)
        if frame.size != expected_size:
            errors.append(f"{action_id} frame {index:02d} is {frame.width}x{frame.height}; expected {expected_size[0]}x{expected_size[1]}")
        if nontransparent < args.min_used_pixels:
            errors.append(f"{action_id} frame {index:02d} is empty or too sparse ({nontransparent} pixels)")
        if edge_pixels > args.edge_pixel_threshold:
            warnings.append(f"{action_id} frame {index:02d} has {edge_pixels} non-transparent pixels near the cell edge")
        if chroma_adjacent_pixels > args.chroma_adjacent_pixel_threshold:
            errors.append(f"{action_id} frame {index:02d} has {chroma_adjacent_pixels} non-transparent pixels close to the chroma key")
        if bbox and size_target:
            bbox_width = bbox[2] - bbox[0]
            bbox_height = bbox[3] - bbox[1]
            width_min, width_max = size_target.get("bbox_width_px", [0, 10**9])
            height_min, height_max = size_target.get("bbox_height_px", [0, 10**9])
            if bbox_width < int(width_min) or bbox_width > int(width_max):
                warnings.append(f"{action_id} frame {index:02d} visible bbox width {bbox_width}px is outside suggested {width_min}-{width_max}px")
            if bbox_height < int(height_min) or bbox_height > int(height_max):
                warnings.append(f"{action_id} frame {index:02d} visible bbox height {bbox_height}px is outside suggested {height_min}-{height_max}px")
            ground_target = size_target.get("ground_anchor_y_px")
            if isinstance(ground_target, list) and len(ground_target) == 2:
                ground_min, ground_max = ground_target
                ground_y = bbox[3]
                if ground_y < int(ground_min) or ground_y > int(ground_max):
                    warnings.append(f"{action_id} frame {index:02d} ground anchor y {ground_y}px is outside suggested {ground_min}-{ground_max}px")

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
    if ground_ys:
        ground_median = median(ground_ys)
        for index, ground_y in enumerate(ground_ys[:expected_count]):
            if abs(ground_y - ground_median) > args.ground_anchor_tolerance_px:
                warnings.append(f"{action_id} frame {index:02d} ground anchor y {ground_y}px differs from the action median {ground_median:.0f}px by more than {args.ground_anchor_tolerance_px}px")
    if core_areas:
        core_median = median(core_areas)
        for index, core_area in enumerate(core_areas[:expected_count]):
            if core_median > 0 and core_area < core_median * args.small_core_body_outlier_ratio:
                warnings.append(f"{action_id} frame {index:02d} has a much smaller core body color bbox than the action median ({core_area} vs {core_median:.0f})")
            if core_median > 0 and core_area > core_median * args.large_core_body_outlier_ratio:
                warnings.append(f"{action_id} frame {index:02d} has a much larger core body color bbox than the action median ({core_area} vs {core_median:.0f})")

    return {
        "action": action_id,
        "expected_frames": expected_count,
        "actual_frames": len(files),
        "size_target": size_target,
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
    parser.add_argument("--small-core-body-outlier-ratio", type=float, default=0.65)
    parser.add_argument("--large-core-body-outlier-ratio", type=float, default=1.40)
    parser.add_argument("--ground-anchor-tolerance-px", type=int, default=6)
    parser.add_argument("--require-components", action="store_true", help="Fail actions that fell back to equal-slot extraction.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    request = load_json(run_dir / "sprite_request.json")
    frames_manifest = load_json(run_dir / "frames" / "frames-manifest.json")
    args.cell_width = int(request["cell_width"])
    args.cell_height = int(request["cell_height"])
    args.subject = str(request.get("subject", ""))
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
