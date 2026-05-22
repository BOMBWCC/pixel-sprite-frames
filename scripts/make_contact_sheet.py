#!/usr/bin/env python3
"""Create a contact sheet preview for a generic pixel spritesheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LABEL_HEIGHT = 18


def checker(size: tuple[int, int], square: int = 12) -> Image.Image:
    image = Image.new("RGB", size, "#ffffff")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], square):
        for x in range(0, size[0], square):
            if (x // square + y // square) % 2:
                draw.rectangle((x, y, x + square - 1, y + square - 1), fill="#e6e6e6")
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spritesheet")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    request = json.loads((run_dir / "sprite_request.json").read_text(encoding="utf-8"))
    manifest_path = run_dir / "final" / "spritesheet-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    columns = int(request["grid_columns"])
    rows = int(request["grid_rows"])
    cell_width = int(request["cell_width"])
    cell_height = int(request["cell_height"])
    frame_count = int(request["total_frames"])
    layout_mode = str(request.get("layout_mode", "packed"))
    used_indices = {int(cell["index"]) for cell in manifest.get("cells", []) if isinstance(cell, dict) and "index" in cell}
    scaled_w = max(1, round(cell_width * args.scale))
    scaled_h = max(1, round(cell_height * args.scale))
    sheet_width = columns * scaled_w
    sheet_height = rows * (scaled_h + LABEL_HEIGHT)

    with Image.open(Path(args.spritesheet).expanduser().resolve()) as opened:
        spritesheet = opened.convert("RGBA")
    output_sheet = Image.new("RGB", (sheet_width, sheet_height), "#f7f7f7")
    draw = ImageDraw.Draw(output_sheet)
    font = ImageFont.load_default()
    cells = {int(cell["index"]): cell for cell in manifest.get("cells", []) if isinstance(cell, dict) and "index" in cell}

    for row in range(rows):
        for column in range(columns):
            index = row * columns + column
            x = column * scaled_w
            y = row * (scaled_h + LABEL_HEIGHT)
            label = f"{index}"
            if index in cells:
                label = f"{index} {cells[index].get('action', '')}".strip()
            used = index in used_indices if layout_mode == "action-rows" else index < frame_count
            draw.rectangle((x, y, x + scaled_w - 1, y + LABEL_HEIGHT - 1), fill="#111111" if used else "#555555")
            draw.text((x + 4, y + 4), label, fill="#ffffff", font=font)
            crop = spritesheet.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height))
            crop = crop.resize((scaled_w, scaled_h), Image.Resampling.NEAREST)
            bg = checker((scaled_w, scaled_h))
            bg.paste(crop, (0, 0), crop)
            output_sheet.paste(bg, (x, y + LABEL_HEIGHT))
            outline = "#18a058" if used else "#cc3344"
            draw.rectangle((x, y + LABEL_HEIGHT, x + scaled_w - 1, y + LABEL_HEIGHT + scaled_h - 1), outline=outline)

    output = Path(args.output).expanduser().resolve() if args.output else run_dir / "qa" / "contact-sheet.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output_sheet.save(output)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
