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

Before running any script in `scripts/`, the agent must choose an available Python interpreter for the current environment:

- On macOS and Linux, prefer `python3`.
- On Windows, prefer `python`.
- If the preferred command is unavailable, probe common alternatives such as `python`, `python3`, or the Codex bundled Python runtime.

Use the selected interpreter consistently as `<python>` for dependency checks and script commands. Prefer checking first:

```text
<python> -c "import PIL; print(PIL.__version__)"
```

If Pillow is missing, install from this skill's dependency file:

```text
<python> -m pip install -r <skill-dir>/scripts/requirements.txt
```

`<skill-dir>` is the directory containing this `SKILL.md`, for example `${CODEX_HOME:-$HOME/.codex}/skills/pixel-sprite-frames`.

Do not skip deterministic processing because Pillow is missing. Install the dependency when the environment allows it, then continue. If installation fails, report that the blocker is the missing `pillow` package and stop before pretending a spritesheet has been validated.

## Required User Choices

For pixel animation and spritesheet requests, ask the user for these choices before generation unless they already supplied them:

- `pixel/cell size`: width and height of each animation cell, for example `64x64`, `96x96`, `128x128`, or `192x192`.
- `frame count`: total frames and, when there are multiple actions, frames per action.
- `actions`: the animation beats or named actions, for example `idle`, `walk-right`, `punch`, `hit-reaction`, `dizzy`. Action ids must be English ASCII identifiers using letters, digits, hyphens, or underscores, and must start with a letter. Put non-English detail in the action description, not the id.
- `layout`: strip or grid, including columns and rows for spritesheets, for example `4x4`.
- `direction/facing`: left, right, front, or preserved from reference.
- `target use`: Pixelorama, Godot, Unity, web/canvas, sticker, UI mascot, prototype, etc.
- `reference role`: identity reference, style reference, pose reference, or edit target.
- `effect/text policy`: exact uppercase text when comic effects or labels are requested, and whether text is allowed at all.

If the user asks for a simple preview-only single sprite, only ask for details that materially change the output. For animation assets, do not skip the cell size, frame count, actions, and layout questions.

## Mandatory Pre-Generation Proposal

For any animation, action strip, or spritesheet request, do not generate images immediately. First present a concrete design proposal and stop for explicit user confirmation. This is required even when enough defaults can be inferred.

The proposal must include:

- subject and style summary
- target use
- cell size
- action ids, descriptions, direction/facing, and frame counts
- spritesheet layout mode, columns/rows, and transparent unused cells per row
- inferred visible bbox targets per action
- inferred invisible ground-anchor range per action
- background/chroma-key choice
- effect/text policy
- whether action keyframes will be generated before full strips

Only proceed after an explicit approval such as "可以", "确认", "go ahead", or equivalent. Do not treat the original generation request as approval.

Frame-count guidance:

- 1 frame: single sprite or icon.
- 4 frames: simple loops, small reactions, single animation beat.
- 6 frames: expressive loops, walk cycles, short attacks.
- 8 frames: upper limit for one generated action strip.
- More than 8 frames: split into multiple action strips, then assemble deterministically. For example, a 16-frame punch reaction should become four 4-frame strips such as `approach`, `impact`, `recoil`, and `dizzy`.

When the requested frame count is over 8 for one continuous generated strip, warn the user and recommend a split plan before generating.

Spritesheet layout guidance:

- Default spritesheet layout is `action-rows`: one action per row, with `grid_columns` cells available for every action.
- Recommend `grid_columns` as the maximum frame count of any action, normally 8. If an action uses fewer frames than `grid_columns`, the remaining cells in that row are transparent.
- In the initial plan, describe row allocation explicitly, for example: `sleep-snore: 4 frames + 4 transparent cells`, `walk-left: 8 frames`, `sit-breathe: 4 frames + 4 transparent cells`, `groom: 6 frames + 2 transparent cells`.
- If any action needs more than `grid_columns` frames, split it into multiple actions/rows before generation instead of letting it wrap into the next row.
- Use packed sequential layout only when the user explicitly asks to minimize sheet area or requests a packed grid.

Size consistency guidance:

- Do not ask ordinary users to provide pixel bbox ranges. Infer suggested visible bbox ranges from the action type and cell size, then state them in the plan.
- Default action targets for a `96x96` cell are approximately: lying/sleeping `72-86px` wide and `34-53px` tall; walking/running `67-84px` wide and `62-82px` tall; sitting/idle/grooming `53-84px` wide and `67-86px` tall.
- Infer an invisible ground-anchor range from the action type and cell size, then state it in the plan. For a `96x96` cell: lying/sleeping bottom contact around `67-76px`; walking/running around `80-90px`; sitting/grooming around `88-94px`.
- Treat these as QA guidance, not hard creative constraints. Pose changes can alter width/height, but same-action frames should not visibly scale up or shrink.
- The scripts write inferred `size_target` data into each action in `sprite_request.json`; `inspect_sprite_frames.py` reports visible bbox, ground-anchor y, and core body-color bbox metrics and warns on outliers.

Action reference guidance:

- For high-consistency animation assets, recommend generating one action keyframe or first-frame reference per action after the canonical base is approved and before full action strips.
- Use action keyframes to lock direction, approximate pose scale, anchor, and body/head proportions. They are especially useful for locomotion, crouching, lying, attacks, and actions where the silhouette changes a lot.
- Do not require action keyframes for quick drafts. Offer the tradeoff: fewer generations and faster output versus better scale/identity consistency.

## Deterministic Assembly

Do not rely on an image model to create final spritesheet geometry. Generated images may look like a grid while still having uneven row heights, inconsistent gutters, or no real alpha channel.

For project-bound animation outputs, use the scripts in `scripts/`:

```text
<python> scripts/prepare_sprite_run.py --subject "<subject>" --action "<english-id>:<frames>:<description>" --cell-width <W> --cell-height <H> --grid-columns <C> --grid-rows <R>
<python> scripts/record_sprite_result.py --run-dir <run> --job-id <job-id> --source <generated-imagegen-output.png>
<python> scripts/finalize_sprite_run.py --run-dir <run>
```

The normal pipeline is:

1. Prepare a run folder with `sprite_request.json`, prompt files, `imagegen-jobs.json`, and layout guides.
2. Generate a canonical base sprite with `$imagegen`.
3. Record the selected base image with `record_sprite_result.py`; this creates `references/canonical-base.png`.
4. For high-consistency runs, generate and approve one action keyframe/first-frame reference per action. Use these as pose/scale references for the full strip.
5. Generate each action strip with `$imagegen`, attaching the canonical base, user references, action keyframe references when available, and the matching layout guide.
6. Record each selected strip with `record_sprite_result.py`.
7. Finalize the run. `finalize_sprite_run.py` removes chroma key with soft matte + despill, extracts uniform cells, writes `qa/review.json`, composes the strict grid, validates alpha/grid geometry, and creates a contact sheet.

The final spritesheet must have exact dimensions:

```text
width = grid_columns * cell_width
height = grid_rows * cell_height
```

Every used cell must contain one centered frame. Every unused cell must be fully transparent.

For the default `action-rows` layout, used cells are determined per row, not by a continuous global frame count. For example, in an `8x4` sheet with four actions of `4, 8, 4, 6` frames, row 0 columns 4-7, row 2 columns 4-7, and row 3 columns 6-7 must be transparent.

## Layout Guides

For every generated action strip, attach the matching `references/layout-guides/<action>.png` from `prepare_sprite_run.py` as a layout-only input.

The guide tells the image model:

- exact frame count
- equal slot spacing
- safe padding
- center alignment
- no slot crossing

The final generated strip must not visibly include guide boxes, guide colors, center marks, labels, grid lines, or frame numbers. Reject and regenerate strips that copy the guide.

Chroma-key backgrounds must be pure, flat key color. Reject strips where the sprite uses key-colored or key-adjacent outlines/highlights, because those pixels either become transparent or survive as colored spill.

The layout guide should prevent slot-crossing in normal outputs. Finalization still treats generated strips as untrusted input: extraction uses connected sprite components first when possible, falls back to equal slots only when component extraction cannot identify the requested frame count, and the contact sheet must be visually reviewed before acceptance. By default, finalization fails if an action falls back to slot extraction; rerun with `--allow-slot-extraction` only after visually accepting the contact sheet. If the contact sheet shows copied guide pixels, cropped poses, repeated tiles, edge slivers, or partial neighboring sprites, regenerate the smallest failing action strip.

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
- `spritesheet`: one action per row with transparent unused cells and a manifest, unless packed layout is explicitly requested
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
   - inferred size and ground-anchor targets per action, unless the user provides explicit ranges
   - Present the mandatory pre-generation proposal and wait for explicit approval before creating the run folder or calling `$imagegen`.

2. Create or select a canonical base sprite:
   - For text-only requests, generate a base sprite first.
   - For reference-driven requests, generate a simplified pixel-style base from the reference.
   - Treat the accepted base as the identity lock for all action frames.
   - Stop after generating and recording the canonical base sprite. Show the base image to the user and wait for explicit approval before generating any action strips. Do not proceed from base to action generation on implied approval.

3. Optionally generate action keyframes:
   - Use this for high-consistency or production-bound outputs, or when actions differ strongly in silhouette.
   - Generate one first-frame/key-pose reference per action using the canonical base and inferred size target.
   - Show the keyframes for approval before full strips when the user cares about scale/pose consistency.

4. Generate action strips:
   - Attach the canonical base and relevant references whenever supported.
   - Attach approved action keyframes when available as pose/scale references.
   - Attach the matching layout guide for every action strip.
   - Prompt each action as a row of evenly spaced full-body frames in identical cell slots.
   - Include the inferred target visible bbox range, invisible ground-anchor range, and core body-color consistency requirement in the prompt.
   - Keep the same silhouette, proportions, palette, face, markings, outfit, prop design, outline weight, and facing logic.
   - Do not accept a strip where frames look like different characters or where the model copied visible grid lines into the art.

5. Remove chroma key and assemble:
   - Use chroma-key generation for transparent assets. Do not rely on model-native transparency in the built-in path.
   - Prefer a key color far from the subject palette. If the subject is black/dark, avoid magenta unless the user requests it; magenta often leaks into dark outlines as purple spill.
   - Assemble strips or sheets only from generated outputs using deterministic scripts.
   - Preserve transparent unused cells if a grid contains blank slots.
   - Write a small manifest with `cell_width`, `cell_height`, `layout_mode`, `actions`, frame counts, row/column cells, transparent unused cells, and durations when producing animation assets.

6. Review before delivery:
   - Inspect the final PNG/WebP and any contact sheet or preview.
   - Check visible bbox, ground-anchor, and core body-color bbox warnings in `qa/review.json`; regenerate the smallest failing action when a frame visibly changes scale or jumps vertically.
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
Frame layout: exactly <N> separate full-body frames, evenly spaced left to right, each fitting inside a <W>x<H> cell with generous padding. Keep the visible sprite size and bounding box consistent between frames.
Target visible bbox: keep the sprite roughly <minW>-<maxW> px wide and <minH>-<maxH> px tall inside each cell, based on the inferred action size target.
Ground anchor: use an invisible ground line and keep the bottom of the paws/body/contact point around y=<minY>-<maxY> px in every frame. Do not draw the ground line, floor, or shadow.
Core body color region: keep the main body/head mass similar in size and position between frames; limbs, tail, small effects, tongue, and highlights may vary.
Identity lock: preserve the same character/object as the canonical base: silhouette, proportions, face, palette, markings, outfit, props, and outline weight.
Animation: <action-specific pose progression>.
Style: crisp pixel-art sprite, chunky silhouette, dark 1-2 px outline, limited palette, flat cel shading.
Background: perfectly flat pure <chroma-key> for background removal; no shadows, gradients, floor plane, texture, darker/lighter key-colored patches, grid, labels, frame numbers, or guide marks. Do not use <chroma-key>, pure key color, or key-adjacent colors in the sprite, outlines, highlights, shadows, props, or effects.
Avoid: cropped body parts, overlapping frames, poses crossing into neighboring slots, repeated identical frames, detached effects, motion blur, speed lines, dust trails, glow, text, UI, watermark.
```

## Script Reference

- `scripts/prepare_sprite_run.py`: creates a generic sprite run, layout guides, prompts, and imagegen job manifest.
- `scripts/record_sprite_result.py`: records selected `$imagegen` outputs into the run and stores the canonical base.
- `scripts/extract_strip_frames.py`: removes chroma-key background with soft matte + despill, extracts each action strip into uniform transparent frame cells using connected components first and equal slots as fallback, and writes `frames/frames-manifest.json`.
- `scripts/compose_spritesheet.py`: composes uniform frames into an exact grid PNG/WebP with `final/spritesheet-manifest.json`.
- `scripts/validate_spritesheet.py`: checks exact dimensions, alpha channel, used/unused cells, and likely opaque-background failures.
- `scripts/inspect_sprite_frames.py`: writes `qa/review.json` with per-action frame counts, extraction method, edge-pixel warnings, chroma-key residue checks, visible bbox checks, ground-anchor checks, and core body-color bbox checks.
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
- `qa/review.json` has no errors.
- Component extraction was used, unless slot extraction was explicitly allowed after visual review.
- Every frame fits inside its cell with no clipping.
- No frame is noticeably larger or smaller than adjacent frames in the same action unless the action explicitly calls for scale change.
- Visible bbox, ground-anchor, and core body-color bbox warnings have been reviewed; scale or vertical-jump outliers are repaired or intentionally accepted.
- Transparent output has clean alpha and no visible chroma-key fringe.
- Character identity is consistent across frames and actions.
- The animation progression is readable and not just repeated copies.
- First/last frames loop acceptably for looping actions.
- No forbidden effects, text, shadows, guide marks, or opaque cell backgrounds remain.
- Contact sheet has been visually reviewed; visible layout guide pixels, cropped references, repeated tiles, edge slivers, or partial neighboring sprites are blockers.
- Final assets and manifest are saved in the workspace or requested destination.

## When To Use Hatch Pet Instead

Use `hatch-pet` instead of this skill only when the user specifically wants a Codex pet package compatible with the Codex app, including the fixed 8x9 atlas, 192x208 cells, `pet.json`, QA videos, and `${CODEX_HOME:-$HOME/.codex}/pets/<pet-name>/` output.
