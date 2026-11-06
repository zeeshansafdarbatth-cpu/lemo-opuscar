// Dump timeline.js as JSON for the score and the mix: node tools/timeline.mjs > out/timeline.json
const m = await import(new URL('../timeline.js', import.meta.url));
console.log(JSON.stringify({ BPM: m.BPM, BEAT: m.BEAT, BAR: m.BAR, DUR: m.DUR, SHOTS: m.SHOTS, T: m.T, EV: m.EV }, null, 1));
