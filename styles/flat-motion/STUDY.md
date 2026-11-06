# Flat Illustration Motion: the reference study

The measured basis of [`STYLE.md`](STYLE.md). Two contemporary studio spots (screen recordings the user supplied, credited to Lobster Studio) were taken apart frame by frame. This file records what was measured and how each finding became a rule. It teaches grammar only: never copy their characters, shots, props, lettering or music, never name the studio or the advertised brand in a film, and never commit the reference files.

Re-run the measurements on any new reference with [`demo/tools/study.py`](demo/tools/study.py) (contact sheets, drawing rate, cuts and moves, palette, tempo, loudness per second).

## 1. The numbers

| Measure | Ref A: alpine spot | Ref B: vinyl loop |
|---|---|---|
| Length, frame | 22.6 s, 16:10 crop of 16:9 | 14.3 s, square (≈1:1) |
| Drawing rate | **12 fps**: 81 % of frames repeat the previous one; holds of 5 frames at 60 fps | **12 fps**: 80 % repeat; holds of 5 at 59.94 |
| Stepping applies to | everything: characters, camera, wipes, particles | everything, the slow dive included |
| Shots | 11 in 21 s (≈1.9 s each); cuts land on bar lines | 9 in 14 s; most joined by motion, not cuts |
| Hard cuts | 1 (onto a new location) | 2, both exactly on the beat (10.98, 11.98 s) |
| Tempo | ≈99 BPM (bar ≈2.4 s); voice-over rides it | 60/120 BPM; beat = 1.0 s |
| Loudness shape | flat: −13…−17 dB every second | a story: −14 → **−37 dB for 3 s** (needle lifted) → −11 dB after the needle drop and the volume knob |
| Palette (share of frame) | snow white #FEFEFE/#EAEFFE 37 %, sky #95B2EB 15 %, snow shadow #D3DBF3 12 %, deep teal #3B5158 11 %, red #D0555D 8 %, mustard #CFA326 5 %, wood #816153 2 %, cobalt #5373AB 2 %, ink #2C2B2D <1 % | ink-aubergine #1F0E35 29 %, vermilion #F14120 30 %, peach #FDD5C2 22 %, violet #5039B8 4 % (plus its hatched mixes #2D1A55, #412A7D), cream #FFF5EE small |
| Hues | 1 ground family (cool blue-white) + 4 accents | **4 inks + cream**, nothing else |
| Gradients | one (a yellow sky glow at the last shot's horizon) | none: every soft edge is made of strokes |
| Outlines | none on silhouettes; dark detail lines inside | none on silhouettes; thin detail lines inside, in a darker ink of the same family |

## 2. Ref A shot log (alpine spot, voice-over on a groove)

| Time | Shot | Move / transition |
|---|---|---|
| 1.2–1.7 | slope and gondola cables, wide | (player UI fading out of the recording) |
| 1.7–4.2 | peak, hand-lettered welcome sign, a small yellow bird | bird hops, flaps off: a gag on a hold |
| 4.2–4.7 | crew of three, low angle, fisheye | **pop-in from the bottom edge**, ~3 drawings, overshoot |
| 4.7–6.9 | crew hold | 12 fps secondary motion: pole raised, sway, gondolas swing |
| 6.9–9.6 | two mittens form a heart over the frame | **frame within a frame**: the content inside the heart changes three times |
| 9.6–10.2 | the mittens close into a fist that fills the frame | **object wipe**, then pull back along the arm to a rider |
| 10.3–11.5 | rider carving, spray arcs | the spray fills the frame: wipe |
| 11.6–13.1 | hand-lettered signpost; rider rushes the lens | **subject passes the lens** |
| 13.2–15.2 | rail trick from below, "YEWWW" bubble written on | rider passes overhead: wipe |
| 15.2–17.2 | skier waves, "HOWDY!" | hold, wave cycle |
| 17.2–18.6 | deck with fire pit, fisheye planks, "WICKED!" | the film's only hard cut |
| 18.6–19.0 | push to two friends | **jump-zoom**, crossed skis wipe the frame |
| 19.0–21.4 | skier straight at camera; group with a deer | trees whip past in the foreground |
| 21.4–22.6 | 4×4 on a snowy road | trees wipe in; **camera orbits** the car, which is redrawn as it turns |

## 3. Ref B shot log (vinyl loop, music only)

| Time | Shot | Move / transition |
|---|---|---|
| 0.0–0.6 | dancer at a record console, frontal, full figure on flat vermilion | dance hold |
| 0.6–1.3 | she spins; the camera cranes over her to top-down | **crane-over**: the console tilts away in 3–4 redrawn perspectives; white arcs trail her hands |
| 1.3–2.0 | top-down: she shrinks, the vermilion floor becomes a disc with a hatched violet rim | **scale dive (out)**: the floor becomes a star; orbit lines and planets enter |
| 2.0–3.6 | a star system: peach core of radial hatching, white dot at its centre (where she was) | orbits turn; slow tilt begins |
| 3.6–4.3 | the star flattens into an ellipse and becomes the record label; space becomes grooves; vermilion sky rises at the top | **tilt-to-become**: star → label, core → spindle, space → vinyl |
| 4.3–5.2 | low angle across the spinning record | label graphics rotate |
| 5.3–6.6 | her head rises behind the record's horizon, holding the cartridge | **scale cheat**: a giant behind the object; music falls to near silence |
| 6.7–7.0 | her hand lowers the cartridge | push in |
| 7.0–9.2 | macro: stylus over a landscape of violet zig-zag groove walls | **the object as a landscape**; needle drop at 8.0 s brings the music back |
| 9.3–10.9 | hand turns the volume knob | 3 drawings of fingers around the knob; level rises 9 dB |
| 11.0–12.0 | top-down speaker cone of rings | pulses on each beat; hard cuts in and out **on the beat** |
| 12.0–13.3 | wide again; she turns from back to front | turnaround in 4–5 drawings |
| 13.3–14.3 | crane-over and dive again | last frame = the 1.3 s frame: **a seamless loop** |

## 4. What both share, and the rule each became

1. **Drawn at 12 fps, everything included** → STYLE §5: render at 24 fps, hold every drawing for two frames, camera too.
2. **Flat fills, no silhouette outlines; detail lines inside shapes** in a darker ink of the shape's own family → §2.
3. **Texture is made of marks, not filters**: dense thin strokes following a flow (hair, grooves, galaxy, snow shadows, wood) and a fine dry-brush tooth → §2 hatching and tooth.
4. **Few inks, one ground** (B: 4 + cream; A: a cool ground + 4 accents); the darkest ink is never pure black → §3.
5. **Chunky, simple people**: small heads, dot eyes or closed-eye arcs, a nose that is one line, big hands and boots or long tapered arms; hair is one hatched mass → §2 characters.
6. **Transitions made of things**: a body, a fist, spray, trees or skis crossing the lens; a shape that turns into the next shot's shape; a window shape that frames the next scene → §6, §8.
7. **Scale travel**: a person becomes a star, a record becomes a landscape, a head rises like a moon behind an object → §8.
8. **Lens drama**: fisheye curvature on wides and low angles, extreme low angles for heroes, things thrust at the lens → §6.
9. **Holds stay alive** at 12 fps: sway, blink, a prop wobble, hair settling → §5.
10. **Sound follows the objects** (B): the music lives in the record player, so lifting the needle silences it and turning the knob raises it → §7.
11. **Hand lettering for every word in the picture**: signs, speech bubbles written on stroke by stroke → §4.
12. **One shape carries across the cut** (circle → circle in B; curved horizon → curved horizon in A) → §6.

## 5. Where they differ (the range of the style)

| | Ref A | Ref B | In the style |
|---|---|---|---|
| Tempo of cutting | fast montage, ~2 s per shot | 1–2 long chained moves, with inserts | both allowed; choose per film (§11) |
| Ground | light (snow, sky) | dark and saturated (vermilion / aubergine) | one ground per film, light or saturated |
| Words | voice-over, bubbles, signs | none | voice optional; lettering hand-made |
| Texture amount | light tooth, hatch in shadows | heavy hatching on hair, space, grooves | hatching is the signature; amount varies |
| Structure | list of moments, ends on the road | loop | §11 gives structures |
