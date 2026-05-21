---
name: pixel-sprite-frames
description: Generate reusable pixel-art sprites, transparent cutouts, action-frame strips, and simple animated spritesheets from text concepts or reference images. Use when the user wants pixel art, game sprites, chibi/mascot action frames, idle/walk/run/jump/attack/hurt animations, frame-by-frame strips, or small movable pixel assets without Codex pet packaging.
---

# Pixel Sprite Frames

## Purpose

Create small reusable pixel-style assets: a single character/object sprite, a canonical reference sprite, one or more action-frame strips, or a simple transparent spritesheet. This skill extracts the reusable visual-generation workflow from `hatch-pet` while removing Codex pet-specific packaging, fixed 8x9 atlas rules, `pet.json`, and app state names.

Use `$imagegen` for visual generation. Load and follow:

```text
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md
```

Do not locally draw, tile, or synthesize missing sprite poses as a substitute for image generation. Local scripts may only perform deterministic cleanup, chroma-key removal, cropping, contact sheets, resizing, validation, or spritesheet assembly from already-generated images.

## Runtime Dependencies

The deterministic scripts require Python and Pillow.

Before running any script in `scripts/`, the agent must ensure dependencies are available in the active Python environment. Prefer checking first:

```text
python -c "import PIL; print(PIL.__version__)"
```

If Pillow is missing, install from this skill's dependency file:

```text
python -m pip install -r <skill-dir>/scripts/requirements.txt
```

`<skill-dir>` is the directory containing this `SKILL.md`, for example `${CODEX_HOME:-$HOME/.codex}/skills/pixel-sprite-frames`.

Do not skip deterministic processing because Pillow is missing. Install the dependency when the environment allows it, then continue. If installation fails, report that the blocker is the missing `pillow` package and stop before pretending a spritesheet has been validated.

## Required User Choices

For pixel animation and spritesheet requests, ask the user for these choices before generation unless they already supplied them:

- `pixel/cell size`: width and height of each animation cell, for example `64x64`, `96x96`, `128x128`, or `192x192`.
- `frame count`: total frames and, when there are multiple actions, frames per action.
- `actions`: the animation beats or named actions, for example `idle`, `walk-right`, `punch`, `hit-reaction`, `dizzy`.
- `layout`: strip or grid, including columns and rows for spritesheets, for example `4x4`.
- `direction/facing`: left, right, front, or preserved from reference.
- `target use`: Pixelorama, Godot, Unity, web/canvas, sticker, UI mascot, prototype, etc.
- `reference role`: identity reference, style reference, pose reference, or edit target.
- `effect/text policy`: exact uppercase text when comic effects or labels are requested, and whether text is allowed at all.

If the user asks for a simple preview-only single sprite, only ask for details that materially change the output. For animation assets, do not skip the cell size, frame count, actions, and layout questions.

Frame-count guidance:

- 1 frame: single sprite or icon.
- 4 frames: simple loops, small reactions, single animation beat.
- 6 frames: expressive loops, walk cycles, short attacks.
- 8 frames: upper limit for one generated action strip.
- More than 8 frames: split into multiple action strips, then assemble deterministically. For example, a 16-frame punch reaction should become four 4-frame strips such as `approach`, `impact`, `recoil`, and `dizzy`.

When the requested frame count is over 8 for one continuous generated strip, warn the user and recommend a split plan before generating.

## Deterministic Assembly

Do not rely on an image model to create final spritesheet geometry. Generated images may look like a grid while still having uneven row heights, inconsistent gutters, or no real alpha channel.

For project-bound animation outputs, use the scripts in `scripts/`:

```text
python scripts/prepare_sprite_run.py --subject "<subject>" --action "<id>:<frames>:<description>" --cell-width <W> --cell-height <H> --grid-columns <C> --grid-rows <R>
python scripts/record_sprite_result.py --run-dir <run> --job-id <job-id> --source <generated-imagegen-output.png>
python scripts/finalize_sprite_run.py --run-dir <run>
```

The normal pipeline is:

1. Prepare a run folder with `sprite_request.json`, prompt files, `imagegen-jobs.json`, and layout guides.
2. Generate a canonical base sprite with `$imagegen`.
3. Record the selected base image with `record_sprite_result.py`; this creates `references/canonical-base.png`.
4. Generate each action strip with `$imagegen`, attaching the canonical base, user references, and the matching layout guide.
5. Record each selected strip with `record_sprite_result.py`.
6. Finalize the run. `finalize_sprite_run.py` removes chroma key, extracts uniform cells, composes the strict grid, validates alpha/grid geometry, and creates a contact sheet.

The final spritesheet must have exact dimensions:

```text
width = grid_columns * cell_width
height = grid_rows * cell_height
```

Every used cell must contain one centered frame. Every unused cell must be fully transparent.

## Layout Guides

For every generated action strip, attach the matching `references/layout-guides/<action>.png` from `prepare_sprite_run.py` as a layout-only input.

The guide tells the image model:

- exact frame count
- equal slot spacing
- safe padding
- center alignment
- no slot crossing

The final generated strip must not visibly include guide boxes, guide colors, center marks, labels, grid lines, or frame numbers. Reject and regenerate strips that copy the guide.

## Default Style

Unless the user specifies another style, use compact pixel-art-adjacent game sprite style:

- small readable silhouette, whole body visible
- chunky proportions or chibi proportions when character-like
- crisp stepped/pixel edges and dark 1-2 px outline
- limited palette, flat cel shading, at most one highlight and one shadow step
- simple readable face or key feature
- no painterly rendering, glossy icon polish, realistic material texture, soft gradients, heavy antialiasing, tiny details, text, watermark, scenery, or UI

When using references, simplify them into the sprite style instead of preserving excessive detail.

## Output Defaults

Ask only when the missing choice materially changes the output. Otherwise choose pragmatic defaults:

- `single sprite`: one transparent PNG or WebP
- `action strip`: one horizontal strip per action
- `spritesheet`: grid of generated frames with a manifest
- `cell size`: 64x64 for tiny game assets, 96x96 for readable character sprites, 128x128 for detailed mascots, or user-specified
- `frame count`: 4 frames for simple loops, 6 frames for expressive loops, 8 frames for locomotion or combat actions
- `background`: flat chroma-key background first, then remove to alpha with deterministic local processing

Keep project-bound final files in the current workspace unless the user names a destination.

## Workflow

1. Establish the asset brief:
   - subject, role, mood/personality
   - target use, if known: game, sticker, UI mascot, prototype, etc.
   - output type: single sprite, action strip, or spritesheet
   - cell size, frame count, and actions if provided
   - reference image roles, if any

2. Create or select a canonical base sprite:
   - For text-only requests, generate a base sprite first.
   - For reference-driven requests, generate a simplified pixel-style base from the reference.
   - Treat the accepted base as the identity lock for all action frames.

3. Generate action strips:
   - Attach the canonical base and relevant references whenever supported.
   - Attach the matching layout guide for every action strip.
   - Prompt each action as a row of evenly spaced full-body frames in identical cell slots.
   - Keep the same silhouette, proportions, palette, face, markings, outfit, prop design, outline weight, and facing logic.
   - Do not accept a strip where frames look like different characters or where the model copied visible grid lines into the art.

4. Remove chroma key and assemble:
   - Use chroma-key generation for transparent assets. Do not rely on model-native transparency in the built-in path.
   - Assemble strips or sheets only from generated outputs using deterministic scripts.
   - Preserve transparent unused cells if a grid contains blank slots.
   - Write a small manifest with `cell_width`, `cell_height`, `actions`, frame counts, and durations when producing animation assets.

5. Review before delivery:
   - Inspect the final PNG/WebP and any contact sheet or preview.
   - Reject identity drift, cropped limbs, slot-crossing poses, repeated identical frames, opaque rectangular backgrounds, key-color residue, shadows/glows/dust trails that break extraction, and detached effects that should be part of the sprite.

## Prompt Template: Base Sprite

```text
Create a single pixel-art game sprite of <subject>.
Style: compact readable sprite, chunky silhouette, crisp stepped edges, dark 1-2 px outline, limited palette, flat cel shading, no soft gradients.
Pose: neutral standing pose, whole body visible, centered with generous padding.
Background: perfectly flat solid <chroma-key> for background removal; do not use <chroma-key> or colors close to it in the sprite.
Avoid: text, labels, watermark, scenery, floor shadow, contact shadow, glow, blur, painterly detail, realistic texture, antialiased high-detail edges.
```

## Prompt Template: Action Strip

```text
Create a horizontal pixel-art animation strip for <action>.
Frame layout: exactly <N> separate full-body frames, evenly spaced left to right, each fitting inside a <W>x<H> cell with generous padding.
Identity lock: preserve the same character/object as the canonical base: silhouette, proportions, face, palette, markings, outfit, props, and outline weight.
Animation: <action-specific pose progression>.
Style: crisp pixel-art sprite, chunky silhouette, dark 1-2 px outline, limited palette, flat cel shading.
Background: perfectly flat solid <chroma-key> for background removal; no shadows, gradients, floor plane, texture, grid, labels, frame numbers, or guide marks.
Avoid: cropped body parts, overlapping frames, poses crossing into neighboring slots, repeated identical frames, detached effects, motion blur, speed lines, dust trails, glow, text, UI, watermark.
```

## Script Reference

- `scripts/prepare_sprite_run.py`: creates a generic sprite run, layout guides, prompts, and imagegen job manifest.
- `scripts/record_sprite_result.py`: records selected `$imagegen` outputs into the run and stores the canonical base.
- `scripts/extract_strip_frames.py`: removes chroma-key background, cuts each action strip into uniform transparent frame cells, and writes `frames/frames-manifest.json`.
- `scripts/compose_spritesheet.py`: composes uniform frames into an exact grid PNG/WebP with `final/spritesheet-manifest.json`.
- `scripts/validate_spritesheet.py`: checks exact dimensions, alpha channel, used/unused cells, and likely opaque-background failures.
- `scripts/make_contact_sheet.py`: creates a checkerboard QA contact sheet for visual review.
- `scripts/finalize_sprite_run.py`: runs extraction, composition, validation, and contact-sheet generation.

## Common Actions

- `idle`: 4-6 frames. Gentle breathing, blink, tiny bob, first and last frame close for a clean loop.
- `walk-right` / `walk-left`: 6-8 frames. Directional locomotion through legs/body/props only; avoid speed lines, dust, floor shadows.
- `run-right` / `run-left`: 6-8 frames. Stronger directional gait; avoid motion trails and effects.
- `jump`: 5-6 frames. Anticipation, lift, peak, descent, settle; no landing marks or shadows.
- `attack`: 4-6 frames. Windup, strike, follow-through, recover; effects only if attached to weapon/body and hard-edged.
- `hurt`: 3-5 frames. Flinch, recoil, recover; no floating icons or detached symbols unless explicitly requested.
- `happy` / `sad`: 4-6 frames. Expression and pose changes, no speech bubbles or punctuation.
- `interact`: 4-8 frames. Use only existing props unless the user asks for a new prop.

## Transparency And Effects Rules

Prefer pose, expression, and silhouette changes over decorative effects.

Allowed effects must be:

- state-relevant
- opaque and hard-edged
- inside the same frame slot
- physically touching or overlapping the sprite silhouette
- not using the chroma-key color or adjacent colors

Avoid by default:

- wave marks, motion arcs, speed lines, afterimages, smears, blur
- detached stars, sparkles, punctuation, icons, smoke, dust, drops, or debris
- cast shadows, contact shadows, floor patches, glows, halos, auras
- text, labels, frame numbers, visible grids, UI panels, checkerboard transparency, white/black backgrounds, scenery

## QA Checklist

Do not call the asset complete until these pass:

- Each requested frame/action exists.
- Every frame fits inside its cell with no clipping.
- Transparent output has clean alpha and no visible chroma-key fringe.
- Character identity is consistent across frames and actions.
- The animation progression is readable and not just repeated copies.
- First/last frames loop acceptably for looping actions.
- No forbidden effects, text, shadows, guide marks, or opaque cell backgrounds remain.
- Final assets and manifest are saved in the workspace or requested destination.

## When To Use Hatch Pet Instead

Use `hatch-pet` instead of this skill only when the user specifically wants a Codex pet package compatible with the Codex app, including the fixed 8x9 atlas, 192x208 cells, `pet.json`, QA videos, and `${CODEX_HOME:-$HOME/.codex}/pets/<pet-name>/` output.
