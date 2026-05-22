#!/usr/bin/env python3
"""Validate a generic pixel spritesheet grid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def alpha_nonzero_count(image: Image.Image) -> int:
    return sum(image.getchannel("A").histogram()[1:])


def used_cells_for_action_rows(request: dict[str, object], columns: int) -> set[int]:
    used: set[int] = set()
    actions = request.get("actions", [])
    if not isinstance(actions, list):
        return used
    for row, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        frames = int(action.get("frames", 0))
        for column in range(min(frames, columns)):
            used.add(row * columns + column)
    return used


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spritesheet")
    parser.add_argument("--run-dir")
    parser.add_argument("--columns", type=int)
    parser.add_argument("--rows", type=int)
    parser.add_argument("--cell-width", type=int)
    parser.add_argument("--cell-height", type=int)
    parser.add_argument("--expected-frames", type=int)
    parser.add_argument("--json-out")
    parser.add_argument("--min-used-pixels", type=int, default=24)
    args = parser.parse_args()

    request = {}
    if args.run_dir:
        request_path = Path(args.run_dir).expanduser().resolve() / "sprite_request.json"
        if request_path.is_file():
            request = json.loads(request_path.read_text(encoding="utf-8"))
    columns = args.columns or int(request.get("grid_columns", 0))
    rows = args.rows or int(request.get("grid_rows", 0))
    cell_width = args.cell_width or int(request.get("cell_width", 0))
    cell_height = args.cell_height or int(request.get("cell_height", 0))
    expected_frames = args.expected_frames or int(request.get("total_frames", columns * rows))
    layout_mode = str(request.get("layout_mode", "packed"))
    row_used_cells = used_cells_for_action_rows(request, columns) if layout_mode == "action-rows" else set()
    if not all([columns, rows, cell_width, cell_height]):
        raise SystemExit("columns, rows, cell width, and cell height are required")

    path = Path(args.spritesheet).expanduser().resolve()
    errors = []
    warnings = []
    cells = []
    try:
        with Image.open(path) as opened:
            source_mode = opened.mode
            source_format = opened.format
            image = opened.convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"could not open spritesheet: {exc}") from exc

    if image.size != (columns * cell_width, rows * cell_height):
        errors.append(f"expected {columns * cell_width}x{rows * cell_height}, got {image.width}x{image.height}")
    if "A" not in source_mode:
        errors.append("spritesheet does not have an alpha channel")

    for index in range(columns * rows):
        column = index % columns
        row = index // columns
        crop = image.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height))
        nontransparent = alpha_nonzero_count(crop)
        used = index in row_used_cells if layout_mode == "action-rows" else index < expected_frames
        cells.append({"index": index, "row": row, "column": column, "used": used, "nontransparent_pixels": nontransparent})
        if used and nontransparent < args.min_used_pixels:
            errors.append(f"frame {index} is empty or too sparse ({nontransparent} pixels)")
        if not used and nontransparent != 0:
            errors.append(f"unused cell {index} is not transparent ({nontransparent} pixels)")
        if used and nontransparent > cell_width * cell_height * 0.95:
            warnings.append(f"frame {index} is nearly opaque; background removal may have failed")

    result = {"ok": not errors, "file": str(path), "format": source_format, "mode": source_mode, "width": image.width, "height": image.height, "errors": errors, "warnings": warnings, "cells": cells}
    if args.json_out:
        Path(args.json_out).expanduser().resolve().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cells"}, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
