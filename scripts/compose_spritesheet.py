#!/usr/bin/env python3
"""Compose uniform frames into a strict transparent spritesheet grid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def alpha_nonzero_count(image: Image.Image) -> int:
    return sum(image.getchannel("A").histogram()[1:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--webp-output")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    request = load_json(run_dir / "sprite_request.json")
    frames_manifest = load_json(run_dir / "frames" / "frames-manifest.json")
    cell_width = int(request["cell_width"])
    cell_height = int(request["cell_height"])
    columns = int(request["grid_columns"])
    rows = int(request["grid_rows"])
    layout_mode = str(request.get("layout_mode", "packed"))
    sheet = Image.new("RGBA", (columns * cell_width, rows * cell_height), (0, 0, 0, 0))

    cells = []
    frame_index = 0
    for action_row, action in enumerate(frames_manifest["actions"]):
        if layout_mode == "action-rows" and action_row >= rows:
            raise SystemExit(f"not enough rows for action {action['action']}; grid has {rows} rows")
        for frame_info in action["frames"]:
            if layout_mode == "action-rows":
                column = int(frame_info["action_index"])
                row = action_row
                if column >= columns:
                    raise SystemExit(f"action {action['action']} has more frames than the {columns}-cell row can hold")
                cell_index = row * columns + column
            else:
                if frame_index >= columns * rows:
                    raise SystemExit(f"too many frames for {columns}x{rows} grid")
                column = frame_index % columns
                row = frame_index // columns
                cell_index = frame_index
            frame_path = run_dir / frame_info["path"]
            with Image.open(frame_path) as opened:
                frame = opened.convert("RGBA")
            if frame.size != (cell_width, cell_height):
                frame = frame.resize((cell_width, cell_height), Image.Resampling.NEAREST)
            left = column * cell_width
            top = row * cell_height
            sheet.alpha_composite(frame, (left, top))
            cells.append({
                "index": cell_index,
                "action": action["action"],
                "action_index": frame_info["action_index"],
                "row": row,
                "column": column,
                "x": left,
                "y": top,
                "width": cell_width,
                "height": cell_height,
                "nontransparent_pixels": alpha_nonzero_count(frame),
            })
            frame_index += 1

    output = Path(args.output).expanduser().resolve() if args.output else run_dir / "final" / "spritesheet.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    if args.webp_output:
        webp = Path(args.webp_output).expanduser().resolve()
        webp.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(webp, format="WEBP", lossless=True, quality=100, method=6)

    manifest = {
        "ok": True,
        "spritesheet": str(output),
        "width": sheet.width,
        "height": sheet.height,
        "columns": columns,
        "rows": rows,
        "layout_mode": layout_mode,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "frame_duration_ms": request.get("frame_duration_ms", 100),
        "frame_count": frame_index,
        "cells": cells,
    }
    (run_dir / "final" / "spritesheet-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "spritesheet": str(output), "frames": frame_index, "size": [sheet.width, sheet.height]}, indent=2))


if __name__ == "__main__":
    main()
