// Flat Illustration Motion — camera, lens and effects.
import { mulberry, clamp, lerp, back } from '/core/lib.js';
import { fill, taper, trace, line, blob, TAU } from './paint.js';

// ---------- camera ----------
// World units are pixels at zoom 1, world origin at the frame centre. One camera per shot.
export function setCam(ctx, W, H, { x = 0, y = 0, z = 1, rot = 0 } = {}) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.translate(W / 2, H / 2); ctx.rotate(rot); ctx.scale(z, z); ctx.translate(-x, -y);
}
export function toScreen(W, H, cam, p) {
  const { x = 0, y = 0, z = 1, rot = 0 } = cam, dx = (p[0] - x) * z, dy = (p[1] - y) * z;
  return [W / 2 + dx * Math.cos(rot) - dy * Math.sin(rot), H / 2 + dx * Math.sin(rot) + dy * Math.cos(rot)];
}
// a scale dive: zoom changes by a constant ratio per second, so the speed feels even across scales
export const dive = (z0, z1, u) => z0 * Math.pow(z1 / z0, clamp(u));
// fisheye: a horizon or plank line bowed by the lens. k > 0 bows the middle up (low angle).
export function bowed(x0, x1, y, k, n = 24) {
  const out = [];
  for (let i = 0; i <= n; i++) { const u = i / n, x = lerp(x0, x1, u); out.push([x, y - k * (1 - Math.pow(2 * u - 1, 2))]); }
  return out;
}
// a whole-frame barrel bend for one point (use on the corners of big shapes in low-angle wides)
export function barrel(W, H, p, k = 0.12) {
  const nx = (p[0] - W / 2) / (W / 2), ny = (p[1] - H / 2) / (H / 2), r2 = nx * nx + ny * ny, f = 1 + k * r2;
  return [W / 2 + nx * f * W / 2, H / 2 + ny * f * H / 2];
}

// ---------- motion marks ----------
// thin white arcs trailing a fast hand, a board, a wheel: one tapered stroke behind the path
export function trail(ctx, pts, w, color) { taper(ctx, pts, u => w * Math.sin(Math.PI * u) * (0.4 + 0.6 * u), color); }
// speed streaks across a region (seeded per drawing so they flicker at 12 fps, which reads as speed)
export function streaks(ctx, { seed, x0, y0, x1, y1, n = 12, len = [60, 200], ang = 0, w = 2, color = '#fff' }) {
  const r = mulberry(seed);
  for (let i = 0; i < n; i++) {
    const x = lerp(x0, x1, r()), y = lerp(y0, y1, r()), L = lerp(len[0], len[1], r());
    line(ctx, [[x, y], [x + Math.cos(ang) * L, y + Math.sin(ang) * L]], color, w * lerp(0.6, 1.2, r()), false);
  }
}
// mist / spray: a burst of dots that fly out and shrink. u = 0…1 through the burst.
export function mist(ctx, { seed, x, y, r = 120, n = 40, u, color, ang = -Math.PI / 2, spread = Math.PI, size = 6 }) {
  if (u <= 0 || u >= 1) return;
  const rr = mulberry(seed); ctx.fillStyle = color;
  for (let i = 0; i < n; i++) {
    const a = ang + (rr() - 0.5) * spread, d = r * (0.3 + rr() * 0.9) * Math.pow(u, 0.6), s = size * (0.4 + rr()) * (1 - u);
    ctx.beginPath(); ctx.arc(x + Math.cos(a) * d, y + Math.sin(a) * d + 40 * u * u, s, 0, TAU); ctx.fill();
  }
}

// ---------- lettering ----------
// Hand-lettered write-on: letters appear one by one at the drawing rate, each with a fixed tilt and
// baseline wobble (seeded), so a word looks drawn, not typeset. u = 0…1 of the reveal.
export function writeOn(ctx, text, x, y, { size = 80, font = 'Gochi Hand', color = '#111', u = 1, seed = 3, align = 'center', tilt = 0.06, track = 0.02 } = {}) {
  ctx.save(); ctx.font = `${size}px "${font}"`; ctx.textBaseline = 'alphabetic'; ctx.fillStyle = color;
  const ch = [...text], ws = ch.map(c => ctx.measureText(c).width), gap = size * track;
  const total = ws.reduce((a, b) => a + b, 0) + gap * (ch.length - 1);
  let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
  const shown = clamp(u) * ch.length, r = mulberry(seed);
  for (let i = 0; i < ch.length; i++) {
    const a = (r() - 0.5) * 2 * tilt, dy = (r() - 0.5) * size * 0.08;
    if (i < Math.floor(shown) || (i < shown && shown - i > 0.5)) {
      ctx.save(); ctx.translate(cx + ws[i] / 2, y + dy); ctx.rotate(a); ctx.fillText(ch[i], -ws[i] / 2, 0); ctx.restore();
    }
    cx += ws[i] + gap;
  }
  ctx.restore();
  return { w: total, h: size };
}
// Speech bubble: the one outlined shape in the style (ink outline, paper fill), popped in with overshoot.
// pop 0…1 scales it in (back easing over ~3 drawings); write 0…1 reveals the words.
export function bubble(ctx, { x, y, w, h, tail, text, pop = 1, write = 1, size = 64, ink = '#111', paper = '#fff', seed = 9, font = 'Gochi Hand', lw = 4 }) {
  const k = back(pop, 2.2); if (k <= 0.01) return null;
  ctx.save(); ctx.translate(x, y); ctx.scale(k, k);
  const b = blob(0, 0, w / 2, h / 2, { n: 12, seed, wob: 0.04 });
  const tx = tail[0] - x, ty = tail[1] - y, ta = Math.atan2(ty, tx), bw = Math.min(w, h) * 0.16;
  const base1 = [Math.cos(ta + 0.35) * w * 0.36, Math.sin(ta + 0.35) * h * 0.36], base2 = [Math.cos(ta - 0.35) * w * 0.36, Math.sin(ta - 0.35) * h * 0.36];
  ctx.beginPath(); trace(ctx, b, true);
  ctx.moveTo(base1[0], base1[1]); ctx.lineTo(tx / k, ty / k); ctx.lineTo(base2[0], base2[1]);
  ctx.lineJoin = 'round'; ctx.lineWidth = lw * 2; ctx.strokeStyle = ink; ctx.stroke();
  ctx.fillStyle = paper; ctx.fill();
  ctx.beginPath(); trace(ctx, b, true); ctx.fill();
  writeOn(ctx, text, 0, size * 0.34, { size, font, color: ink, u: write, seed: seed + 1 });
  ctx.restore();
  return { x0: x - w / 2 * k, y0: y - h / 2 * k, x1: x + w / 2 * k, y1: y + h / 2 * k };
}
