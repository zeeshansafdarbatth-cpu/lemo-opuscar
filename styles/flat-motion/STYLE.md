# Flat Illustration Motion — Style Prompt

> Contemporary studio flat illustration, animated at 12 drawings a second: four inks and no outlines, texture made of thousands of thin marks instead of gradients, chunky simple people, and a camera that travels through scale, where one shape turns into the next shot's shape.
> References (grammar only): contemporary studio brand spots in flat editorial illustration, two of which were measured frame by frame in [STUDY.md](STUDY.md) (credited to Lobster Studio); editorial illustration of the 2015–2025 era (flat colour, grain, simplified figures); scale-travel films in the *Powers of Ten* tradition for the dive. Learn the grammar only. Never copy their characters, props, shots, lettering or music, and never name them in a film.

## 1. Essence, and what it is not

One glance tells it by five traits:

1. **Drawn at 12 fps, everything included.** Characters, camera, wipes and particles all step on twos. In both references, 80 % of output frames repeat the previous one.
2. **Flat fills, no silhouette outlines.** Form comes from shape against shape. Details (fingers, nose, smile, folds, knob edges) are thin lines drawn *inside* a shape, in a darker ink of the same family.
3. **Texture is made of marks**, never gradients, blur or glow: dense thin strokes that follow a flow (hair, record grooves, a halo, snow shadows, wood grain).
4. **Four inks and one light**, with one ground colour per film covering a third or more of most frames.
5. **Transitions are made of things.** A shape becomes the next shot's shape; a subject passes the lens; a frame forms inside the frame; the camera dives through scale. No dissolves.

Not a vector explainer: no smooth 60 fps tweens, gradients, drop shadows or perfect geometry. Not Mid-century Cartoon: no off-register cels, colour-plane rooms or classroom narrator; proportions are modern. Not Game Show Flat or Sci-Fi Sitcom Toon: no outlines, boiling or not. Not a picture book: the camera is restless and the cutting is musical.

## 2. Materials & rendering

- **Canvas 2D, painted back to front.** Every shape is a smooth closed path (Catmull-Rom) from a seeded blob with 2–7 % radial wobble. Only graphic things (orbits, rings, wheels) are true circles. Hard polygons are for crisp graphic cuts (wedges, zig-zags, planks).
- **Detail lines** are tapered ribbons with pointed ends, 3–6 px at 1080p (characters ≈ 1.2–1.6 % of head height). Colour: a darker shade of the fill (skin line on skin, deep orange on orange) or the darkest ink.
- **Marks** (`hatch`, `arcs`, `rays`): 1.3–3 px strokes, 4–90 px long, 2–3 colours, batched per colour. They are seeded **once per object** and move with it, so they never re-roll on a hold. Only speed streaks are re-seeded per drawing.
- **Soft edges without gradients:** a halo is concentric arcs whose density falls with the radius (`density = (1−q)^1.6…2`), mixing the accent, its dark shade and the light. A glow, a planet's atmosphere, a vignette or dusk are all built this way.
- **Colour changes by marks.** To turn one colour into another (a fruit becoming a hill), lay marks of the new colour over it, more each drawing, then swap to solid. A 50 % mix of two inks is mud.
- **People:** small heads on chunky bodies; dot or oval eyes (an ink pupil on a light sclera), closed eyes as arches; the nose is one line, the smile one line, the ear a C. Hair is one mass in the darkest ink, textured with mid-ink strands from the crown. Limbs are **noodles** (one tapered tube with round ends, no elbow seam). Hands are big (≥ ½ head height), with sausage fingers split by detail lines and a clear thumb. Perspective is exaggerated: boots and hands near the lens get huge.
- **Speech bubbles are the one outlined shape**: an ink outline about 4 px, a paper fill.
- **Lens:** wide low angles bow the horizon and planks (fisheye). Heroes are shot from below.
- **Grain:** none or very light (`mux.sh … 0`–`1`). The texture lives in the marks.

## 3. Colour logic

- **Four inks plus one light** (white, cream or snow). Shades one step lighter or darker of an existing ink are allowed for marks and shadow shapes, never as new hues.
- **One ground per film**, saturated (vermilion, cobalt) or light (snow, cream). It covers 30–45 % of most frames and doubles as sky, table or space, so that worlds can turn into each other.
- **The darkest ink is a coloured near-black** (aubergine, indigo, teal-black), never `#000`.
- **The warmest ink belongs to the story object**, the thing that travels from shot to shot (the record, the orange). It is not used for random props.
- **Every silhouette reads at one bit**: subject against ground must survive a black-and-white threshold.
- **Never:** gradients (one exception per film at most: a flat sky glow at a horizon), colour crossfades, pure black, more than one ground at once.
- Example palette (from a reference): ground vermilion `#F14120`, ink aubergine `#1F0E35`, violet `#5039B8`, peach `#FDD5C2`, light cream `#FFF5EE`.

## 4. Type & subtitles

- **Every word in the picture is hand-lettered**: signs, bubbles, titles. Use an OFL hand font (Gochi Hand for speech, Caveat Brush for signs), drawn letter by letter with a fixed per-letter tilt of ±3–4° and a ±4 % baseline wobble (`writeOn`). It is revealed at the drawing rate, one letter per drawing, with a pen-scratch sound for each.
- **Bubbles** pop in over 3 drawings with overshoot, the tail pointing at the speaker. Text is 70–100 px at 1080p, 1–3 words, and holds ≥ letters ÷ 15 + 1.5 s.
- **Subtitles** (only with a voice): a rounded cream plate with dark text at 44–52 px, low in the frame, never over the subject's face or hands. Hold ≥ max(1.8 s, speech + 0.6 s).
- **Titles**: hand-lettered, written on, held ≥ 4 s.

## 5. Motion quality

- **12 drawings per second, each held for two frames at 24 fps**: `t = step(t)` before anything is computed. The camera steps too. This is the style's hand-made feel; smooth tweening ruins it.
- Because the camera steps, **camera moves are bold**: whips, dives and passes change a lot per drawing. A slow drift must move big shapes, not thin high-contrast lines (they judder).
- **Easing:** ease-out for arrivals; a back overshoot (s ≈ 2) over 3 drawings for pop-ins; exponential zoom for dives (constant ratio per second); 1–2 drawings of anticipation before big actions.
- **Holds** may be fully still up to about 0.6 s. Longer holds need secondary motion: breathing, sway, a blink, hair settling, a wobbling prop. No line boil.
- **Things appear** by popping in, by entering from a frame edge, by being wiped in by an object, or by *becoming*. **Things disappear** by leaving frame or being covered. Never fades.
- **Smears:** thin tapered light arcs trailing fast hands, boards and wheels; speed streaks re-seeded each drawing.
- **What never moves:** the marks relative to their object; the palette within a world.

## 6. Camera grammar

| Move | What it expresses | Can serve |
|---|---|---|
| Scale dive (exponential zoom, often with a slow spin) | small becomes vast, or vast becomes personal | an idea's reach; one customer → a network; a seed → a forest |
| Tilt-to-become (top-down ↔ low angle: a circle squashes to an ellipse and gains a horizon) | the same thing seen anew | a map becoming a place; a logo becoming a building |
| Crane-over (front → top-down round a spinning subject) | release, joy, dizziness | a win; a dance; a decision made |
| Subject passes the lens | speed, a wipe made of the subject | arrivals; sport; a delivery; an exit |
| Frame within a frame (hands, window, viewfinder) whose inside changes | point of view; choice; a list | options; memories; previews |
| Low-angle fisheye hero | swagger, group identity | a team; a cast; a product family |
| Locked frame with secondary motion | a breath; reading time | a punchline; a silence; a title |
| Orbit round an object, redrawn as it turns | showcase | a product; a vehicle; a building |

- At key moments the subject fills **at least a third of the frame height**.
- **One shape carries across every join** (circle → circle, curve → curve, colour field → colour field).
- **Hard cuts only on a beat or bar line**, at most about two per 15 s. No dissolves, crossfades or fades to black (the last frame excepted).
- Square, vertical and 16:9 all work. Lay out from `innerWidth` × `innerHeight`.

## 7. Sound palette

- **Instruments:** soft, rounded timbres: kalimba or marimba plucks, an FM electric piano, a round bass with 2nd and 3rd harmonics, soft drums (kick, rim, shaker, snaps). Under a voice-over: a mid-tempo hip-hop or funk groove (around 90–100 BPM). Avoid generic piano and strings.
- **The music lives in the world.** It switches with objects: a needle lifted silences it, a knob raises it, a door muffles it (low-pass), a pop opens it. This is the style's sound signature.
- **One real near-silence of 2–3 s**, at least 18 dB under the groove, before the turn. The first sound after it is one of the film's key sounds.
- **Cuts and pop-ins land on the grid** (bar lines for cuts, beats for pops).
- **Foley is close, small and tactile:** paper, fruit, fabric, rubber, wood, plastic. Every pop-in gets a tiny sound, and lettering scratches once per drawing.
- **Ambience:** one bed per world, cut with the picture, never crossfaded across a cut.
- **Voice** (optional): conversational, warm, rhythmic; or none at all.
- **Mix:** −14 LUFS. Limit transients in the mix before mastering. Low end (20–120 Hz) about −3 dB against the mids.

## 8. Native moves

- **Becomes.** A shape in one shot is the next shot's shape at another scale or meaning. Keep the geometry identical across the join, swap the meaning on one drawing during fast motion, and change colour with marks. *Fits content like:* an ingredient becoming the field it grew in; a city map becoming a circuit board; a coin becoming a planet; a cell becoming a city.
- **Scale dive.** An exponential zoom, often spinning, through two or more worlds. The world is redrawn at each scale (new details pop in) rather than scaled up. *Fits content like:* one message reaching millions; a pixel to a screen to a stadium; a raindrop to an ocean.
- **Object as landscape.** In macro, an object's surface becomes terrain the camera travels over. *Fits content like:* fabric weave as fields; a chip as a city; a page's letters as a skyline.
- **Subject passes the lens.** The subject rushes the camera until its body covers the frame, and that cover is the cut. *Fits content like:* a delivery van; a sprinter; a paper plane; a skateboard.
- **Frame within a frame.** Hands, a window or a phone form a shape over the shot, and the scene inside it changes 2–3 times. *Fits content like:* three product options; memories; "what you'll see".
- **Diegetic music switch.** An on-screen action turns the score off, up or muffled. *Fits content like:* headphones going on; a car door; a radio dial; a party behind a door.
- **Pop-in cast.** Characters rise from a frame edge in 3 drawings with overshoot, each with a tiny sound. *Fits content like:* a team; a product family; features as characters.
- **Hand-lettered bubble.** A one-word reaction written on letter by letter. *Fits content like:* a review; a punchline; a call to action.

## 9. Pitfalls of the medium

- **Smooth motion** (24 or 60 unique drawings a second) reads as a template explainer. Fix: `step(t)` on everything.
- **Alpha crossfades** between scales or worlds turn to mud. Fix: swap on a drawing in fast motion, or let marks take the colour over.
- **A colour halfway between two inks** is brown mud. Fix: marks, then a solid swap.
- **Marks re-seeded every frame** boil and sparkle. Fix: seed per object; only speed streaks change per drawing.
- **Hatching too dense** turns a dark mass into a flat mid colour, and the ink disappears. Keep the base ink visible: for hair, about 3 strokes per pixel of head height.
- **Line widths that scale with the zoom** balloon or vanish in a dive. Fix: divide the width by the zoom for marks meant to stay thin.
- **Orthographic tilts** float far objects into the sky. Fix: cull anything above the horizon; draw far objects before the near terrain.
- **Small hands** read as fists or blobs. Fix: hands ≥ ½ head height, fingers longer than the palm, a clear thumb.
- **Outlines creeping in**: only bubbles have them.
- **Synth drums and snaps** push the true peak over after loudnorm. Fix: limit in the mix (`limit`), aiming at about −17 dBFS RMS before `mux.sh`.

## 10. Engine

All in [`demo/engine/`](demo/engine/), plain ES modules on Canvas 2D:

- `paint.js`: `step(t)` (12 fps quantiser); paths `trace`, `fill`, `poly`; shapes `blob`, `ell`, `scallop`; ink `taper` (variable-width ribbon: detail lines and limbs), `line`; marks `hatch` (clipped flow strokes), `arcs` (concentric, with `sy` for tilt and `density(q)` for halos), `rays`, `tooth`; flows `flowCircular`, `flowRadial`, `flowAngle`, `flowHair`; `mix` for shades only.
- `rig.js`: `ik2` (two-bone IK), `limb` (noodle through root, joint and end), `hand` (`curl`, `spread`, `thumb`, `mirror`), `head` (`turn`, `eyes`, `look`, `smile`, `mouth`, hair `bob` / `short` / `bun`).
- `fx.js`: `setCam`, `toScreen`, `dive` (exponential zoom), `bowed` / `barrel` (fisheye), `trail`, `streaks`, `mist`, `writeOn`, `bubble`.
- [`demo/tools/study.py`](demo/tools/study.py): measures a reference film (drawing rate, cuts and moves, palette, tempo, loudness), the method behind this file.

A minimal example, not in the demo (a dive into a planet that is also a peach):

```js
import { step, fill, blob, arcs } from './engine/paint.js';
import { setCam, dive } from './engine/fx.js';
window.render = t => { t = step(t);
  setCam(ctx, 1920, 1080, { z: dive(1, 6, t / 3), rot: t * 0.2 });
  ctx.fillStyle = '#1F0E35'; ctx.fillRect(-4000, -4000, 8000, 8000);
  arcs(ctx, 0, 0, 80, 600, { count: 2000, width: 2 / dive(1, 6, t / 3), colors: ['#5039B8', '#F14120'], density: q => (1 - q) ** 2 });
  fill(ctx, blob(0, 0, 90, 90, { seed: 4 }), '#FDD5C2');
};
```

## 11. Variation space

Each film decides its structure, cast, worlds, opening, ending, camera path, pacing, ground colour and inks (within §3), and whether it has a voice.

- **Three structures:** a chain of *becomes* that loops back to its start; a montage of moments, one per bar, joined by object wipes; a single oner that dives from a hand to a galaxy and back.
- **Three openings:** a pop-in cast at a low angle; an extreme macro of a texture we can't yet name; a hand entering frame to do one small action.
- **Three endings:** the first frame again (a seamless loop); a crane-up revealing every object of the film laid out; a frame-within-a-frame closing to black on the last beat.

---

How our demo was made (story, shots, score, end card, build): [DEMO.md](DEMO.md). Read it after your treatment exists. The measurements behind every rule: [STUDY.md](STUDY.md).
