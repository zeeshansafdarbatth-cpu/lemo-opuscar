// Flat Illustration Motion — paint: flat shapes, tapered ink lines, and texture made of marks.
// Everything is deterministic: seeds are fixed per object, so marks never boil on a hold.
import { mulberry, clamp, lerp, TAU } from '/core/lib.js';

export { TAU };

// ---------- drawing rate ----------
// The style is drawn at 12 fps, camera included: quantise time before anything is computed.
export const DRAW_FPS = 12;
export const step = (t, fps = DRAW_FPS) => Math.floor(t * fps + 1e-6) / fps;

// ---------- smooth paths ----------
function cr(p0, p1, p2, p3, u) {           // Catmull-Rom point
  const u2 = u * u, u3 = u2 * u;
  return [
    0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * u + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u3),
    0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * u + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u3)];
}
// dense points along a smooth curve through pts
export function sample(pts, closed = false, per = 10) {
  const n = pts.length, out = [];
  if (n < 2) return pts.slice();
  const N = closed ? n : n - 1;
  for (let i = 0; i < N; i++) {
    const p0 = closed ? pts[(i - 1 + n) % n] : pts[Math.max(0, i - 1)];
    const p1 = pts[i], p2 = pts[(i + 1) % n];
    const p3 = closed ? pts[(i + 2) % n] : pts[Math.min(n - 1, i + 2)];
    for (let k = 0; k < per; k++) out.push(cr(p0, p1, p2, p3, k / per));
  }
  if (!closed) out.push(pts[n - 1]);
  return out;
}
// add a smooth path (Catmull-Rom as Béziers) to the current path
export function trace(ctx, pts, closed = true) {
  const n = pts.length; if (n < 2) return;
  ctx.moveTo(pts[0][0], pts[0][1]);
  const N = closed ? n : n - 1;
  for (let i = 0; i < N; i++) {
    const p0 = closed ? pts[(i - 1 + n) % n] : pts[Math.max(0, i - 1)];
    const p1 = pts[i], p2 = pts[(i + 1) % n];
    const p3 = closed ? pts[(i + 2) % n] : pts[Math.min(n - 1, i + 2)];
    ctx.bezierCurveTo(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
      p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1]);
  }
  if (closed) ctx.closePath();
}
export function fill(ctx, pts, color, closed = true) {
  ctx.beginPath(); trace(ctx, pts, closed); ctx.fillStyle = color; ctx.fill();
}
// a hard polygon (no smoothing): for crisp graphic shapes (wedges, zig-zags, planks)
export function poly(ctx, pts, color) {
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.closePath(); ctx.fillStyle = color; ctx.fill();
}

// ---------- shape builders ----------
export function ell(cx, cy, rx, ry, rot = 0, n = 40) {
  const c = Math.cos(rot), s = Math.sin(rot), out = [];
  for (let i = 0; i < n; i++) {
    const a = i / n * TAU, x = Math.cos(a) * rx, y = Math.sin(a) * ry;
    out.push([cx + x * c - y * s, cy + x * s + y * c]);
  }
  return out;
}
// an organic closed shape: an ellipse with fixed (seeded) radial wobble — never re-rolled per frame
export function blob(cx, cy, rx, ry, { n = 14, seed = 1, wob = 0.06, rot = 0 } = {}) {
  const r = mulberry(seed), c = Math.cos(rot), s = Math.sin(rot), out = [];
  for (let i = 0; i < n; i++) {
    const a = i / n * TAU, k = 1 + (r() * 2 - 1) * wob;
    const x = Math.cos(a) * rx * k, y = Math.sin(a) * ry * k;
    out.push([cx + x * c - y * s, cy + x * s + y * c]);
  }
  return out;
}
// a scalloped edge (skirts, clouds, spray, pith): bumps along a closed outline
export function scallop(cx, cy, r, { bumps = 9, depth = 0.12, seed = 3, ry = null, rot = 0 } = {}) {
  const rr = mulberry(seed), out = [], n = bumps * 4, c = Math.cos(rot), s = Math.sin(rot);
  const ph = rr() * TAU, amp = [];
  for (let b = 0; b < bumps; b++) amp.push(0.7 + rr() * 0.6);
  for (let i = 0; i < n; i++) {
    const a = i / n * TAU, b = Math.floor(i / 4);
    const k = 1 - depth + depth * amp[b] * Math.abs(Math.sin(a * bumps / 2 + ph));
    const x = Math.cos(a) * r * k, y = Math.sin(a) * (ry ?? r) * k;
    out.push([cx + x * c - y * s, cy + x * s + y * c]);
  }
  return out;
}

// ---------- tapered ink ----------
// A filled ribbon along a smooth curve. w(u) gives the width at u∈[0,1].
// Detail lines: taper(ctx, pts, 3, col) (pointed both ends). Limbs: taper(ctx, pts, u => lerp(w0,w1,u), col, {caps:true}).
export function taper(ctx, pts, w, color, { caps = false, per = 8, closed = false } = {}) {
  const P = pts.length > 2 ? sample(pts, closed, per) : pts;
  const n = P.length; if (n < 2) return;
  const wf = typeof w === 'function' ? w : (u => w * Math.pow(Math.sin(Math.PI * clamp(u, 0.0001, 0.9999)), 0.6));
  const L = [], R = [];
  for (let i = 0; i < n; i++) {
    const a = P[Math.max(0, i - 1)], b = P[Math.min(n - 1, i + 1)];
    let dx = b[0] - a[0], dy = b[1] - a[1]; const d = Math.hypot(dx, dy) || 1; dx /= d; dy /= d;
    const hw = wf(i / (n - 1)) / 2;
    L.push([P[i][0] - dy * hw, P[i][1] + dx * hw]); R.push([P[i][0] + dy * hw, P[i][1] - dx * hw]);
  }
  ctx.beginPath(); ctx.moveTo(L[0][0], L[0][1]);
  for (let i = 1; i < n; i++) ctx.lineTo(L[i][0], L[i][1]);
  for (let i = n - 1; i >= 0; i--) ctx.lineTo(R[i][0], R[i][1]);
  ctx.closePath(); ctx.fillStyle = color; ctx.fill();
  if (caps) {
    for (const [i, u] of [[0, 0], [n - 1, 1]]) {
      const r = wf(u) / 2; if (r <= 0.2) continue;
      ctx.beginPath(); ctx.arc(P[i][0], P[i][1], r, 0, TAU); ctx.fill();
    }
  }
}
// plain thin line, constant width (screen-thin lines: orbits, motion arcs, knob outlines)
export function line(ctx, pts, color, width = 2, smooth = true) {
  ctx.beginPath();
  if (smooth && pts.length > 2) trace(ctx, pts, false);
  else { ctx.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]); }
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.stroke();
}

// ---------- texture made of marks ----------
// Clip to a shape, then lay many thin strokes that follow a flow. This replaces every gradient and shadow.
// flow(x,y) → angle. Strokes are batched per colour (one stroke() call each), so 5–10k marks per frame are fine.
export function hatch(ctx, clipPts, o = {}) {
  const { seed = 7, count = 1500, len = [20, 60], width = 1.4, colors = ['#000'], alpha = 1,
    flow = () => 0, bbox = null, density = null, curve = 4 } = o;
  const r = mulberry(seed);
  let x0, y0, x1, y1;
  if (bbox) [x0, y0, x1, y1] = bbox;
  else { x0 = Infinity; y0 = Infinity; x1 = -Infinity; y1 = -Infinity; for (const [x, y] of clipPts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); } }
  ctx.save();
  if (clipPts) { ctx.beginPath(); trace(ctx, clipPts, true); ctx.clip(); }
  const paths = colors.map(() => new Path2D());
  for (let i = 0; i < count; i++) {
    let x = lerp(x0, x1, r()), y = lerp(y0, y1, r());
    const keep = r(), ci = Math.floor(r() * colors.length), L = lerp(len[0], len[1], r());
    if (density && keep > density(x, y)) continue;
    const p = paths[ci]; p.moveTo(x, y);
    const st = L / curve;
    for (let k = 0; k < curve; k++) { const a = flow(x, y); x += Math.cos(a) * st; y += Math.sin(a) * st; p.lineTo(x, y); }
  }
  ctx.globalAlpha = alpha; ctx.lineCap = 'round'; ctx.lineWidth = width;
  paths.forEach((p, i) => { ctx.strokeStyle = colors[i]; ctx.stroke(p); });
  ctx.restore();
}
// concentric arcs: grooves, halos, ripples, orbits of texture. Squash with sy (tilt) and rotate with rot.
// density(r) ∈ [0,1] thins the marks with the radius: this is how the style fades without a gradient.
export function arcs(ctx, cx, cy, r0, r1, o = {}) {
  const { seed = 11, count = 1200, span = [0.15, 0.8], width = 1.3, colors = ['#000'], density = null,
    sy = 1, rot = 0, spin = 0, alpha = 1 } = o;
  const r = mulberry(seed), paths = colors.map(() => new Path2D());
  for (let i = 0; i < count; i++) {
    const rr = lerp(r0, r1, r()), keep = r(), a0 = r() * TAU + spin, s = lerp(span[0], span[1], r()), ci = Math.floor(r() * colors.length);
    if (density && keep > density((rr - r0) / Math.max(1e-6, r1 - r0), rr)) continue;
    const p = paths[ci], steps = Math.max(3, Math.ceil(s * rr / 12));
    for (let k = 0; k <= steps; k++) {
      const a = a0 + s * k / steps, x = Math.cos(a) * rr, y = Math.sin(a) * rr * sy;
      const X = cx + x * Math.cos(rot) - y * Math.sin(rot), Y = cy + x * Math.sin(rot) + y * Math.cos(rot);
      if (k === 0) p.moveTo(X, Y); else p.lineTo(X, Y);
    }
  }
  ctx.save(); ctx.globalAlpha = alpha; ctx.lineCap = 'round'; ctx.lineWidth = width;
  paths.forEach((p, i) => { ctx.strokeStyle = colors[i]; ctx.stroke(p); });
  ctx.restore();
}
// radial marks: sun cores, bursts, the grain of a cut fruit. density(u) by radius share.
export function rays(ctx, cx, cy, r0, r1, o = {}) {
  const { seed = 13, count = 900, len = [0.1, 0.4], width = 1.3, colors = ['#000'], density = null, sy = 1, alpha = 1 } = o;
  const r = mulberry(seed), paths = colors.map(() => new Path2D());
  for (let i = 0; i < count; i++) {
    const a = r() * TAU, u = r(), keep = r(), l = lerp(len[0], len[1], r()) * (r1 - r0), ci = Math.floor(r() * colors.length);
    if (density && keep > density(u)) continue;
    const ra = r0 + u * (r1 - r0), rb = Math.min(r1, ra + l), p = paths[ci];
    p.moveTo(cx + Math.cos(a) * ra, cy + Math.sin(a) * ra * sy); p.lineTo(cx + Math.cos(a) * rb, cy + Math.sin(a) * rb * sy);
  }
  ctx.save(); ctx.globalAlpha = alpha; ctx.lineCap = 'round'; ctx.lineWidth = width;
  paths.forEach((p, i) => { ctx.strokeStyle = colors[i]; ctx.stroke(p); });
  ctx.restore();
}
// fine dry-brush tooth inside a shape (light: 0.04–0.08 alpha). World-anchored by its seed.
export function tooth(ctx, clipPts, color, { seed = 5, count = 600, size = [1, 2.5], alpha = 0.12 } = {}) {
  hatch(ctx, clipPts, { seed, count, len: [size[0] * 1.5, size[1] * 2], width: size[0] * 0.9, colors: [color], alpha, flow: () => -0.5, curve: 1 });
}
// flows
export const flowCircular = (cx, cy, k = 1) => (x, y) => Math.atan2(y - cy, x - cx) + Math.PI / 2 * k;
export const flowRadial = (cx, cy, curl = 0) => (x, y) => Math.atan2(y - cy, x - cx) + curl;
export const flowAngle = a => () => a;
// hair: from a crown point, outward and down, with a curl
export const flowHair = (cx, cy, curl = 0.25) => (x, y) => { const a = Math.atan2(y - cy, x - cx); return a + curl * Math.sign(x - cx || 1); };

// ---------- colour helpers ----------
export function mix(c1, c2, u) {
  const a = parseInt(c1.slice(1), 16), b = parseInt(c2.slice(1), 16);
  const r = Math.round(lerp(a >> 16, b >> 16, u)), g = Math.round(lerp(a >> 8 & 255, b >> 8 & 255, u)), bl = Math.round(lerp(a & 255, b & 255, u));
  return '#' + ((1 << 24) | (r << 16) | (g << 8) | bl).toString(16).slice(1);
}
