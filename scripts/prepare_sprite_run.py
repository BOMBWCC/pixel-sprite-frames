#!/usr/bin/env python3
"""Create a generic pixel-sprite run folder, prompts, layout guides, and jobs."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

CHROMA_KEY_CANDIDATES = [
    ("cyan", "#00FFFF"),
    ("yellow", "#FFFF00"),
    ("magenta", "#FF00FF"),
    ("blue", "#0000FF"),
    ("orange", "#FF7F00"),
    ("green", "#00FF00"),
]
MAX_FRAMES_PER_STRIP = 8
DEFAULT_CELL_WIDTH = 128
DEFAULT_CELL_HEIGHT = 128
LAYOUT_PACKED = "packed"
LAYOUT_ACTION_ROWS = "action-rows"


ACTION_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "pixel-sprite"


def normalize_action_id(value: str) -> str:
    raw = value.strip()
    if not ACTION_ID_RE.fullmatch(raw):
        raise SystemExit(
            "action id must be an English ASCII identifier starting with a letter "
            "and using only letters, digits, hyphens, or underscores; "
            "examples: idle, walk-right, punch, hit-reaction"
        )
    return raw.lower().replace("_", "-")


def parse_action(raw: str) -> dict[str, object]:
    parts = [part.strip() for part in raw.split(":", 2)]
    action_id = normalize_action_id(parts[0])
    frames = int(parts[1]) if len(parts) >= 2 and parts[1] else 4
    description = parts[2] if len(parts) >= 3 else parts[0].strip()
    if frames <= 0:
        raise SystemExit(f"action {action_id} must have at least 1 frame")
    return {"id": action_id, "frames": frames, "description": description}


def parse_hex_color(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise SystemExit(f"invalid chroma key color: {value}; expected #RRGGBB")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def sampled_reference_pixels(paths: list[Path]) -> list[tuple[int, int, int]]:
    pixels: list[tuple[int, int, int]] = []
    for path in paths:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            for red, green, blue, alpha in image.getdata():
                if alpha > 16 and not (red > 244 and green > 244 and blue > 244):
                    pixels.append((red, green, blue))
    return pixels


def choose_chroma_key(reference_paths: list[Path], requested: str) -> dict[str, object]:
    if requested.lower() != "auto":
        rgb = parse_hex_color(requested)
        return {"hex": rgb_to_hex(rgb), "rgb": list(rgb), "name": "user-selected", "selection": "manual"}

    pixels = sampled_reference_pixels(reference_paths)
    if not pixels:
        rgb = parse_hex_color("#FF00FF")
        return {"hex": "#FF00FF", "rgb": list(rgb), "name": "magenta", "selection": "fallback"}

    scored: list[tuple[float, int, str, tuple[int, int, int]]] = []
    for preference_index, (name, hex_color) in enumerate(CHROMA_KEY_CANDIDATES):
        rgb = parse_hex_color(hex_color)
        distances = sorted(color_distance(rgb, pixel) for pixel in pixels)
        percentile_index = max(0, min(len(distances) - 1, int(len(distances) * 0.01)))
        scored.append((distances[percentile_index], -preference_index, name, rgb))
    score, _preference, name, rgb = max(scored)
    return {"hex": rgb_to_hex(rgb), "rgb": list(rgb), "name": name, "selection": "auto", "score": round(score, 2)}


def image_metadata(path: Path) -> dict[str, object]:
    with Image.open(path) as image:
        return {"path": str(path), "width": image.width, "height": image.height, "mode": image.mode, "format": image.format}


def rel(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def draw_dashed_line(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill: str) -> None:
    x1, y1 = start
    x2, y2 = end
    dash = 8
    gap = 6
    if x1 == x2:
        for y in range(min(y1, y2), max(y1, y2), dash + gap):
            draw.line((x1, y, x2, min(y + dash, max(y1, y2))), fill=fill)
        return
    for x in range(min(x1, x2), max(x1, x2), dash + gap):
        draw.line((x, y1, min(x + dash, max(x1, x2)), y2), fill=fill)


def create_layout_guide(path: Path, frames: int, cell_width: int, cell_height: int) -> dict[str, object]:
    width = frames * cell_width
    height = cell_height
    image = Image.new("RGB", (width, height), "#f7f7f7")
    draw = ImageDraw.Draw(image)
    margin_x = max(8, round(cell_width * 0.10))
    margin_y = max(8, round(cell_height * 0.10))
    for index in range(frames):
        left = index * cell_width
        right = left + cell_width - 1
        draw.rectangle((left, 0, right, height - 1), outline="#111111", width=2)
        safe = (left + margin_x, margin_y, right - margin_x, height - 1 - margin_y)
        draw.rectangle(safe, outline="#2f80ed", width=2)
        center_x = left + cell_width // 2
        center_y = height // 2
        draw_dashed_line(draw, (center_x, safe[1]), (center_x, safe[3]), "#b8b8b8")
        draw_dashed_line(draw, (safe[0], center_y), (safe[2], center_y), "#b8b8b8")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "frames": frames,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "safe_margin_x": margin_x,
        "safe_margin_y": margin_y,
        "usage": "layout guide input only; do not copy visible guide lines into generated sprite strips",
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def base_prompt(subject: str, style_notes: str, chroma_key: dict[str, object], cell_width: int, cell_height: int) -> str:
    return f"""Create one canonical pixel-art game sprite reference for: {subject}.

Style: compact readable pixel-art-adjacent sprite, chunky silhouette, crisp stepped edges, dark 1-2 px outline, limited palette, flat cel shading, no soft gradients, no painterly detail.
Pose: neutral pose, whole subject visible, centered with generous padding, suitable for a {cell_width}x{cell_height} animation cell.
Additional style notes: {style_notes or "none"}.
Background: perfectly flat solid {chroma_key["name"]} {chroma_key["hex"]} chroma-key background. Do not use {chroma_key["hex"]} or colors close to it in the sprite.
Avoid: scenery, floor plane, cast shadow, contact shadow, glow, text, labels, watermark, checkerboard transparency, frame numbers, visible grid, cropped body parts."""


def strip_prompt(
    action: dict[str, object],
    subject: str,
    style_notes: str,
    chroma_key: dict[str, object],
    cell_width: int,
    cell_height: int,
    grid_columns: int,
    layout_mode: str,
) -> str:
    frames = int(action["frames"])
    row_note = ""
    if layout_mode == LAYOUT_ACTION_ROWS:
        empty = grid_columns - frames
        row_note = (
            f"\nFinal spritesheet row plan: this action will occupy one full {grid_columns}-cell row; "
            f"generate only the first {frames} poses for this action. The remaining {empty} final row cells "
            "will be transparent and must not be represented in the generated strip."
        )
    return f"""Create one horizontal pixel-art animation strip for action `{action["id"]}`.

Use the attached canonical base sprite and any user reference images as the identity lock. Use the attached layout guide only for frame count, equal slot spacing, centering, and safe padding. Do not copy any visible guide lines, labels, colors, boxes, or marks.

Subject: {subject}.
Action progression: {action["description"]}.
Frame layout: exactly {frames} full-body frames, left to right, one complete pose per invisible {cell_width}x{cell_height} cell. Keep each pose centered inside its cell with safe transparent padding. Keep the visible sprite size and bounding box consistent from frame to frame; do not let one pose become noticeably larger or smaller than the others. No pose may cross into a neighboring slot.{row_note}
Identity lock: preserve the same silhouette, proportions, face, palette, markings, outfit, props, outline weight, and facing logic from the canonical base.
Style: compact readable pixel-art-adjacent game sprite, chunky silhouette, crisp stepped edges, dark 1-2 px outline, limited palette, flat cel shading, no soft gradients.
Additional style notes: {style_notes or "none"}.
Background: perfectly flat solid {chroma_key["name"]} {chroma_key["hex"]} chroma-key background across the whole strip. Do not use {chroma_key["hex"]} or colors close to it in the sprite, props, effects, highlights, or shadows.
Effects: allowed only if action-relevant, opaque, hard-edged, pixel-style, inside the same cell, and touching or overlapping the sprite silhouette.
Avoid: cropped body parts, blank slots, repeated identical frames, visible grid lines, guide marks, labels, frame numbers, scenery, floor plane, shadows, glows, dust, detached effects, motion blur, speed lines, text unless explicitly requested, UI, watermark."""


def make_jobs(run_dir: Path, copied_refs: list[dict[str, object]], actions: list[dict[str, object]]) -> list[dict[str, object]]:
    reference_inputs = [{"path": rel(Path(str(ref["copied_path"])), run_dir), "role": "user reference"} for ref in copied_refs]
    jobs: list[dict[str, object]] = [
        {
            "id": "base",
            "kind": "base-sprite",
            "status": "pending",
            "prompt_file": "prompts/base-sprite.md",
            "input_images": reference_inputs,
            "output_path": "decoded/base.png",
            "depends_on": [],
            "generation_skill": "$imagegen",
            "allow_prompt_only_generation": not reference_inputs,
        }
    ]
    for action in actions:
        action_id = str(action["id"])
        jobs.append(
            {
                "id": action_id,
                "kind": "action-strip",
                "status": "pending",
                "prompt_file": f"prompts/actions/{action_id}.md",
                "input_images": [
                    *reference_inputs,
                    {"path": f"references/layout-guides/{action_id}.png", "role": "layout guide; spacing only, do not copy lines"},
                    {"path": "references/canonical-base.png", "role": "canonical identity reference"},
                    {"path": "decoded/base.png", "role": "approved base sprite"},
                ],
                "output_path": f"decoded/{action_id}.png",
                "depends_on": ["base"],
                "generation_skill": "$imagegen",
                "allow_prompt_only_generation": False,
            }
        )
    return jobs


def default_output_dir(name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / "output" / "pixel-sprite-frames" / f"{slugify(name)}-{timestamp}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="pixel-sprite")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--action", action="append", default=[], help="Format: id:frames:description. Repeat for multiple strips.")
    parser.add_argument("--grid-columns", type=int, default=4)
    parser.add_argument("--grid-rows", type=int, default=0, help="Defaults to enough rows for all frames.")
    parser.add_argument("--layout-mode", choices=[LAYOUT_ACTION_ROWS, LAYOUT_PACKED], default=LAYOUT_ACTION_ROWS, help="action-rows keeps one action per row with transparent unused cells; packed fills cells sequentially.")
    parser.add_argument("--cell-width", type=int, default=DEFAULT_CELL_WIDTH)
    parser.add_argument("--cell-height", type=int, default=DEFAULT_CELL_HEIGHT)
    parser.add_argument("--frame-duration-ms", type=int, default=100)
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--style-notes", default="")
    parser.add_argument("--chroma-key", default="auto")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    actions = [parse_action(raw) for raw in args.action] or [parse_action("animation:4:basic readable animation loop")]
    action_ids = [str(action["id"]) for action in actions]
    duplicate_ids = sorted({action_id for action_id in action_ids if action_ids.count(action_id) > 1})
    if duplicate_ids:
        raise SystemExit(f"duplicate action ids are not allowed: {', '.join(duplicate_ids)}")
    total_frames = sum(int(action["frames"]) for action in actions)
    if args.layout_mode == LAYOUT_ACTION_ROWS:
        too_wide = [f"{action['id']}:{action['frames']}" for action in actions if int(action["frames"]) > args.grid_columns]
        if too_wide:
            raise SystemExit(
                f"layout-mode {LAYOUT_ACTION_ROWS} requires each action to fit in one row of {args.grid_columns} cells; "
                f"split these actions or increase --grid-columns: {', '.join(too_wide)}"
            )
        grid_rows = args.grid_rows or len(actions)
        if grid_rows < len(actions):
            raise SystemExit(f"layout-mode {LAYOUT_ACTION_ROWS} needs at least one row per action ({len(actions)} rows)")
    else:
        grid_rows = args.grid_rows or math.ceil(total_frames / args.grid_columns)
    if args.grid_columns <= 0 or grid_rows <= 0:
        raise SystemExit("grid columns and rows must be positive")
    if total_frames > args.grid_columns * grid_rows:
        raise SystemExit(f"grid {args.grid_columns}x{grid_rows} cannot hold {total_frames} frames")

    reference_sources = [Path(raw).expanduser().resolve() for raw in args.reference]
    run_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_output_dir(args.name).resolve()
    if run_dir.exists() and any(run_dir.iterdir()) and not args.force:
        raise SystemExit(f"{run_dir} already exists and is not empty; pass --force to reuse it")
    for directory in [run_dir / "references", run_dir / "references/layout-guides", run_dir / "prompts/actions", run_dir / "decoded", run_dir / "frames", run_dir / "final", run_dir / "qa"]:
        directory.mkdir(parents=True, exist_ok=True)

    copied_refs: list[dict[str, object]] = []
    copied_ref_paths: list[Path] = []
    for index, source in enumerate(reference_sources, start=1):
        if not source.is_file():
            raise SystemExit(f"reference not found: {source}")
        copied = run_dir / "references" / f"reference-{index:02d}{source.suffix.lower() or '.png'}"
        shutil.copy2(source, copied)
        meta = image_metadata(copied)
        meta["source_path"] = str(source)
        meta["copied_path"] = str(copied)
        copied_refs.append(meta)
        copied_ref_paths.append(copied)

    chroma_key = choose_chroma_key(copied_ref_paths, args.chroma_key)
    layout_guides = []
    warnings = []
    for action in actions:
        if int(action["frames"]) > MAX_FRAMES_PER_STRIP:
            warnings.append(f"action {action['id']} has {action['frames']} frames; split into <= {MAX_FRAMES_PER_STRIP} frame strips for better generation reliability")
        guide = create_layout_guide(run_dir / "references/layout-guides" / f"{action['id']}.png", int(action["frames"]), args.cell_width, args.cell_height)
        layout_guides.append({**guide, "action": action["id"], "path": rel(Path(str(guide["path"])), run_dir)})

    request = {
        "schema_version": 1,
        "name": args.name,
        "subject": args.subject,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cell_width": args.cell_width,
        "cell_height": args.cell_height,
        "grid_columns": args.grid_columns,
        "grid_rows": grid_rows,
        "layout_mode": args.layout_mode,
        "total_frames": total_frames,
        "frame_duration_ms": args.frame_duration_ms,
        "actions": actions,
        "references": copied_refs,
        "layout_guides": layout_guides,
        "chroma_key": chroma_key,
        "style_notes": args.style_notes,
        "warnings": warnings,
    }
    (run_dir / "sprite_request.json").write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    write_text(run_dir / "prompts/base-sprite.md", base_prompt(args.subject, args.style_notes, chroma_key, args.cell_width, args.cell_height))
    for action in actions:
        write_text(
            run_dir / "prompts/actions" / f"{action['id']}.md",
            strip_prompt(action, args.subject, args.style_notes, chroma_key, args.cell_width, args.cell_height, args.grid_columns, args.layout_mode),
        )

    jobs = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "run_dir": str(run_dir), "primary_generation_skill": "$imagegen", "jobs": make_jobs(run_dir, copied_refs, actions)}
    (run_dir / "imagegen-jobs.json").write_text(json.dumps(jobs, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "run_dir": str(run_dir), "ready_jobs": ["base"], "warnings": warnings}, indent=2))


if __name__ == "__main__":
    main()
