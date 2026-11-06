# Flat Illustration Motion — our demo

One example among many. Don't reuse its story, arc, shots, props or timings.

Demo: *One Orange* (29 s) · `flat-motion.mp4` · source in [`demo/`](demo/)

## Story & structure

Someone peels an orange in one long ribbon. The camera rises, and the ribbon becomes a road spiralling up a hill at dusk. A cyclist climbs it, passes the lens, and stops on the crest in front of a giant setting sun. In near-silence the camera pushes into the sun, which cracks into segments; pulling back, they are the orange on the table again. She offers a segment across the table: "THANKS!". The last shot cranes up over the table, where the peel lies like the road and the segments like the sun's rays.

The structure is a chain of *becomes* (STYLE §8) that returns home: orange → road → hill → sun → segments → orange. Each join keeps one shape (the spiral, the disc, the wedges). Native moves spent: *becomes* (peel → road, orange → summit, sun → segments), *scale dive* (out at 4 s, in at 13.5 s, out at 15.9 s), *tilt-to-become* (7–9 s), *subject passes the lens* (10.6 s), *diegetic music switch* (the band stops when the rider stops and returns on the crack), *hand-lettered bubble* (21 s).

## Shots

| # | Time | Shot | Camera | Native move / note |
|---|---|---|---|---|
| 1 | 0.0–4.0 | top-down: hands, the orange; the thumb digs in, juice mist; the peel coils out | slow push, slight rotation | hook in the first second |
| 2 | 4.0–7.0 | the same spiral, now a road on dark land; trees pop in; the orange's disc is taken over by dark marks and becomes the summit | **dive out** with a spin (×0.35) | *becomes* with no dissolve |
| 3 | 7.0–9.0 | top-down → low angle: the hill rises, the sky comes down from the top, the road winds up the dome | **tilt-to-become** | far side of the road culled |
| 4 | 9.0–11.0 | low angle, bowed crest: the rider comes up the road at the lens | rider scale ×29 by a constant ratio | the shirt covers the frame: **passes the lens** |
| 5 | 11.0–15.0 | side: the rider rolls in against a giant sun, foot down at 12.0, looks up; at 13.5 the push into the sun begins | locked, then **dive in** (×9.5) | the breath: 3.5 s near-silence |
| 6 | 15.0–17.0 | inside the sun: radial marks; cream cracks shoot out at 15.5; the wedges open; pull back to the table | **dive out** with a turn | the sun *becomes* the orange |
| 7 | 17.0–19.0 | top-down: hands pull the orange in two; one segment rises at the lens | slow push | match to shot 8's segment |
| 8 | 19.0–23.5 | across the table: closed-eye smile, eyes open, she offers a segment; a striped sleeve takes it; "THANKS!" | locked, body sway | the only words in the film |
| 9 | 23.5–29.0 | top-down: peel spiral, segments as rays, two cups; title "One Orange" written on | crane up (dive out) | echo of shots 2 and 5 |

## Score structure

120 BPM, 4/4, one bar = 2 s, D major (Dmaj7 – Bm7 – Gmaj7 – A6/7), all synthesized in [`demo/music/score.py`](demo/music/score.py):

| Time | Section | What plays |
|---|---|---|
| 0–4 | A | kalimba riff in eighths, shaker in sixteenths |
| 4–7 | B1 | + round bass, kick (the dive opens the band) |
| 7–12 | B2 | + rim, e-piano chord stabs |
| 12–15.5 | C | the band stops with the foot-down; one soft held chord, cicadas, wind; a low hum rises with the push |
| 15.5 | hit | the crack: kick, bass D, e-piano chord, a high kalimba D |
| 16–23.5 | D | full groove |
| 23.5–25 | E | lighter (no kick) under the crane-up |
| 25–29 | end | Dmaj9 rings out, kalimba arpeggio up |

Mix ([`demo/mix.py`](demo/mix.py)): foley from the picture's events (peel crackle, mist, freewheel ticks, bell, pass whoosh, brake squeal, foot-down, cicadas, hum, crack, wet split, cloth, pop, pen scratches at 12 per second); one ambience bed per world (room, wind, room). Measured: groove −17 dBFS RMS before mastering, the breath at 13 s 19 dB below it, low end −3.6 dB against the mids; the film masters at −14.0 LUFS, true peak −1.4 dB.

## Palette & props

Four inks + cream: ink indigo `#15123B`, ground cobalt `#2C46D2`, tangerine `#FF8B3D` (the story object only: orange, road, sun, cap), skin `#B9714F`, cream `#FFEBD0`. Shades for marks: `#5B73F0`, `#22389F`, `#E8662A`, `#7A3F2A`, `#2A2566`. The cobalt is table, sky and land, so worlds turn into each other without a colour jump.

Props: the orange (seeded blob, circular rind marks darker toward one side, a cream highlight stroke, a star stem); the ribbon (an Archimedean spiral of 2.15 turns, cream under tangerine so both edges show the pith; a dashed centre line once it is a road); the hill (a paraboloid projected orthographically, contour rings); the bike (front view: an ink ellipse wheel; side: spoked rings in silhouette); the cups; the window with a small sun.

## End card

The film ends on its own hand-lettered title, "One Orange", held 4.2 s. Unlike the library's other demos, it carries no LemoLab sign-off card.

## Build notes

| File | What it does |
|---|---|
| `index.html` | page contract (`DUR`, `EV`, `render`, `TEXTS`, `READY`); `?test=model` shows the model sheet |
| `timeline.js` | shots, key times and sound events: the single source for picture, score and mix |
| `film.js` | the nine shots; `renderFrame` quantises to 12 fps and skips a redraw when the drawing hasn't changed |
| `sheet.js` | model sheet: four heads, four hand curls |
| `engine/` | the style's reusable engine (STYLE §10) |
| `music/score.py` | the synthesized score → `music/stems/*.wav` |
| `mix.py` | foley + ambience + stems → `out/mix.wav` |
| `tools/timeline.mjs` | `timeline.js` → `out/timeline.json` for the Python side |
| `tools/study.py` | measures a reference or our own render (drawing rate, joins, palette, loudness) |

`sh styles/flat-motion/demo/build.sh` runs everything: fonts (downloaded once), timeline, events, score, mix, frames (≈25 s on 4 workers), mux, stills. `mux.sh` needs **ffmpeg 7+**: with 6.x it refuses the mix as cut off. Review: `node core/render/still.mjs styles/flat-motion/demo 3.5 12.8 21.6`, and `tools/study.py` on the render should report about 12 fps and no cut at 4.0 or 7.0 s.

Pitfalls met on this demo's props: the hill's far trees floated into the sky in the tilt (culled above the horizon); the first dive's orange → summit alpha fade made mud (replaced by marks taking the disc over, then a solid swap); the groove's bar index was rounded, which dropped the music at 7–8 s (use floor).
