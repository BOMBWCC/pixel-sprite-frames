#!/usr/bin/env python3
"""Extract generated action strips into uniform transparent sprite frames."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip()
    if len(value) != 7 or not value.startswith("#"):
        raise SystemExit(f"invalid chroma key color: {value}; expected #RRGGBB")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def color_distance(red: int, green: int, blue: int, key: tuple[int, int, int]) -> float:
    return math.sqrt((red - key[0]) ** 2 + (green - key[1]) ** 2 + (blue - key[2]) ** 2)


def load_request(run_dir: Path) -> dict[str, object]:
    path = run_dir / "sprite_request.json"
    if not path.is_file():
        raise SystemExit(f"sprite request not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def remove_chroma_background(image: Image.Image, chroma_key: tuple[int, int, int], threshold: float) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            if color_distance(red, green, blue, chroma_key) <= threshold:
                pixels[x, y] = (red, green, blue, 0)
    return rgba


def fit_to_cell(image: Image.Image, cell_width: int, cell_height: int, padding: int) -> Image.Image:
    target = Image.new("RGBA", (cell_width, cell_height), (0, 0, 0, 0))
    bbox = image.getbbox()
    if bbox is None:
        return target
    sprite = image.crop(bbox)
    max_width = max(1, cell_width - padding * 2)
    max_height = max(1, cell_height - padding * 2)
    scale = min(max_width / sprite.width, max_height / sprite.height, 1.0)
    if scale != 1.0:
        sprite = sprite.resize((max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale))), Image.Resampling.NEAREST)
    left = (cell_width - sprite.width) // 2
    top = (cell_height - sprite.height) // 2
    target.alpha_composite(sprite, (left, top))
    return target


def extract_slots(strip: Image.Image, frame_count: int, cell_width: int, cell_height: int, padding: int) -> list[Image.Image]:
    slot_width = strip.width / frame_count
    frames = []
    for index in range(frame_count):
        left = round(index * slot_width)
        right = round((index + 1) * slot_width)
        frames.append(fit_to_cell(strip.crop((left, 0, right, strip.height)), cell_width, cell_height, padding))
    return frames


def alpha_nonzero_count(image: Image.Image) -> int:
    return sum(image.getchannel("A").histogram()[1:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--actions", default="all", help="Comma-separated action ids or all.")
    parser.add_argument("--chroma-key")
    parser.add_argument("--key-threshold", type=float, default=96.0)
    parser.add_argument("--padding", type=int, default=6)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    request = load_request(run_dir)
    cell_width = int(request["cell_width"])
    cell_height = int(request["cell_height"])
    chroma_hex = args.chroma_key or request["chroma_key"]["hex"]
    chroma_key = parse_hex_color(chroma_hex)
    wanted = None if args.actions.strip().lower() == "all" else {item.strip() for item in args.actions.split(",") if item.strip()}

    rows = []
    frame_index = 0
    for action in request["actions"]:
        action_id = str(action["id"])
        if wanted is not None and action_id not in wanted:
            continue
        frame_count = int(action["frames"])
        strip_path = run_dir / "decoded" / f"{action_id}.png"
        if not strip_path.is_file():
            raise SystemExit(f"missing generated strip for {action_id}: {strip_path}")
        with Image.open(strip_path) as opened:
            strip = remove_chroma_background(opened, chroma_key, args.key_threshold)
        frames = extract_slots(strip, frame_count, cell_width, cell_height, args.padding)
        action_dir = run_dir / "frames" / action_id
        action_dir.mkdir(parents=True, exist_ok=True)
        outputs = []
        for local_index, frame in enumerate(frames):
            output = action_dir / f"{local_index:02d}.png"
            frame.save(output)
            outputs.append({"path": str(output.relative_to(run_dir)), "index": frame_index, "action_index": local_index, "nontransparent_pixels": alpha_nonzero_count(frame)})
            frame_index += 1
        rows.append({"action": action_id, "frames": outputs})

    manifest = {
        "ok": True,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "chroma_key": {"hex": chroma_hex, "rgb": list(chroma_key), "threshold": args.key_threshold},
        "actions": rows,
    }
    (run_dir / "frames" / "frames-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "run_dir": str(run_dir), "actions": [row["action"] for row in rows]}, indent=2))


if __name__ == "__main__":
    main()
