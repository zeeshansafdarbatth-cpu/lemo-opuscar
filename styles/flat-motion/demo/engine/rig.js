// Flat Illustration Motion — rig: noodle limbs, simple hands and faces.
// People are flat shapes without outlines. Detail lines (finger splits, nose, smile, ear, folds)
// are drawn INSIDE shapes in a darker ink of the same family. Hair is one mass, textured with strokes.
import { clamp, lerp } from '/core/lib.js';
import { fill, taper, trace, blob, ell, hatch, flowHair, TAU } from './paint.js';

// two-bone IK: root a, target t, bone lengths l1, l2; bend = +1 / −1 picks the elbow side
export function ik2(a, t, l1, l2, bend = 1) {
  let dx = t[0] - a[0], dy = t[1] - a[1], d = Math.hypot(dx, dy);
  const dd = clamp(d, Math.abs(l1 - l2) + 1e-3, l1 + l2 - 1e-3);
  const ang = Math.atan2(dy, dx), cosA = (l1 * l1 + dd * dd - l2 * l2) / (2 * l1 * dd);
  const A = ang - bend * Math.acos(clamp(cosA, -1, 1));
  const e = [a[0] + Math.cos(A) * l1, a[1] + Math.sin(A) * l1];
  const tt = d > dd ? [a[0] + dx / d * dd, a[1] + dy / d * dd] : t;
  return [e, tt];
}
// a noodle limb through root a, joint j, end b: one smooth tapered tube, round ends, no seam at the joint
export function limb(ctx, a, j, b, w0, w1, color) {
  const m1 = [lerp(a[0], j[0], 0.55), lerp(a[1], j[1], 0.55)], m2 = [lerp(j[0], b[0], 0.45), lerp(j[1], b[1], 0.45)];
  taper(ctx, [a, m1, j, m2, b], u => lerp(w0, w1, u), color, { caps: true, per: 6 });
}

// A simple hand. ang = direction the fingers point; s = hand length; curl 0 (open) … 1 (fist);
// spread spreads the fingers; mirror flips thumb side. Detail lines split the fingers.
export function hand(ctx, { x, y, ang = 0, s = 80, curl = 0.2, spread = 0.15, skin, line, mirror = false, thumb = 0.5, fingers = 4 }) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(ang); if (mirror) ctx.scale(1, -1);
  const pw = s * 0.42, ph = s * 0.5;
  fill(ctx, blob(pw * 0.45, 0, pw * 0.6, ph * 0.5, { n: 10, seed: 41, wob: 0.04 }), skin);
  // fingers, from the little finger to the index
  const base = [], tips = [];
  for (let i = 0; i < fingers; i++) {
    const v = fingers === 1 ? 0 : i / (fingers - 1) - 0.5;               // −0.5 … 0.5 across the palm
    const len = s * (0.5 + 0.12 * (1 - Math.abs(v + 0.12) * 2)) * (1 - 0.45 * curl);
    const a0 = v * spread * 2.2, bend = curl * 1.7;
    const p0 = [pw * 0.85, v * ph * 0.8];
    const p1 = [p0[0] + Math.cos(a0) * len * 0.55, p0[1] + Math.sin(a0) * len * 0.55];
    const p2 = [p1[0] + Math.cos(a0 + bend) * len * 0.45, p1[1] + Math.sin(a0 + bend) * len * 0.45];
    base.push(p0); tips.push([p0, p1, p2]);
    taper(ctx, [[p0[0] - pw * 0.3, p0[1]], p0, p1, p2], u => lerp(ph * 0.27, ph * 0.22, u), skin, { caps: true, per: 5 });
  }
  // thumb on the +y side: a clear, thick digit, pointing along the fingers when open, across the palm when curled
  const tb = [pw * 0.25, ph * 0.42], ta = lerp(0.55, 1.6, thumb * 0.5 + curl * 0.5);
  const t1 = [tb[0] + Math.cos(ta * 0.6) * s * 0.24, tb[1] + Math.sin(ta * 0.6) * s * 0.24];
  const t2 = [t1[0] + Math.cos(ta) * s * 0.2, t1[1] + Math.sin(ta) * s * 0.2];
  taper(ctx, [[pw * 0.1, ph * 0.2], tb, t1, t2], u => lerp(ph * 0.42, ph * 0.26, u), skin, { caps: true, per: 5 });
  // detail lines: between fingers, and the fold where the thumb meets the palm
  for (let i = 0; i < fingers - 1; i++) {
    const A = tips[i], B = tips[i + 1];
    taper(ctx, [[lerp(A[0][0], B[0][0], .5) - pw * 0.1, lerp(A[0][1], B[0][1], .5)], [lerp(A[1][0], B[1][0], .5), lerp(A[1][1], B[1][1], .5)]], s * 0.02, line);
  }
  taper(ctx, [[pw * 0.35, ph * 0.3], [pw * 0.62, ph * 0.38], [lerp(pw * 0.62, t1[0], 0.6), lerp(ph * 0.38, t1[1], 0.6)]], s * 0.02, line);
  ctx.restore();
}

// A head. s ≈ head height. turn −1…1 (left…right), eyes 0 closed (happy arcs) … 1 open,
// look [−1…1, −1…1] moves the pupils, smile 0…1, mouth 0…1 opens it. hair: 'bob' | 'short' | 'bun'.
export function head(ctx, o) {
  const { x, y, s = 200, turn = 0, tilt = 0, eyes = 1, look = [0, 0], smile = 0.6, mouth = 0,
    skin, skinLine, hair, hairMarks = [], hairStyle = 'bob', seed = 1, sclera = '#FFF6EA', ink = '#111', back = false } = o;
  ctx.save(); ctx.translate(x, y); ctx.rotate(tilt);
  const rx = s * 0.4, ry = s * 0.5, sh = turn * rx * 0.28;
  const crown = [-sh * 0.4, -ry * 1.05];
  const hairMass = hairStyle === 'bob'
    ? [[-rx * 1.28 - sh * 0.3, ry * 0.62], [-rx * 1.36 - sh * 0.3, -ry * 0.1], [-rx * 1.12 - sh * 0.3, -ry * 0.82], [-sh * 0.35, -ry * 1.2],
      [rx * 1.12 - sh * 0.3, -ry * 0.82], [rx * 1.36 - sh * 0.3, -ry * 0.1], [rx * 1.28 - sh * 0.3, ry * 0.62], [-sh * 0.3, ry * 0.7]]
    : hairStyle === 'bun' ? blob(-sh * 0.3, -ry * 0.35, rx * 1.12, ry * 0.85, { n: 12, seed: seed + 3, wob: 0.05 })
      : blob(-sh * 0.3, -ry * 0.38, rx * 1.1, ry * 0.78, { n: 12, seed: seed + 3, wob: 0.06 });
  const texHair = pts => hairMarks.length && hatch(ctx, pts, { seed: seed + 9, count: Math.round(s * 3.2), len: [s * 0.1, s * 0.3],
    width: Math.max(1, s * 0.0045), colors: hairMarks, flow: flowHair(crown[0], crown[1], 0.15), curve: 5 });
  // hair behind the face
  fill(ctx, hairMass, hair); texHair(hairMass);
  if (hairStyle === 'bun') { const b = blob(-sh * 0.5, -ry * 1.12, rx * 0.5, ry * 0.36, { seed: seed + 5 }); fill(ctx, b, hair); texHair(b); }
  if (back) { ctx.restore(); return; }
  // face
  const face = blob(sh * 0.15, ry * 0.05, rx, ry * 0.92, { n: 16, seed: seed + 1, wob: 0.025 });
  fill(ctx, face, skin);
  // ear on the side away from the turn
  const es = turn >= 0 ? -1 : 1, ex = sh * 0.1 + es * rx * (0.92 - Math.abs(turn) * 0.1);
  fill(ctx, blob(ex, ry * 0.08, rx * 0.16, ry * 0.2, { seed: seed + 7, wob: 0.05 }), skin);
  taper(ctx, [[ex + es * rx * 0.02, ry * -0.02], [ex + es * rx * 0.08, ry * 0.08], [ex + es * rx * 0.0, ry * 0.18]], s * 0.012, skinLine);
  // fringe: hair over the top of the forehead
  const fr = [[-rx * 1.06 - sh * 0.3, ry * 0.05], [-rx * 0.98, -ry * 0.72], [-sh * 0.2, -ry * 1.06], [rx * 0.98, -ry * 0.72],
    [rx * 1.06 - sh * 0.3, ry * 0.0], [rx * 0.82 + sh * 0.2, -ry * 0.38], [rx * 0.3 + sh * 0.5, -ry * 0.52], [-rx * 0.4 + sh * 0.3, -ry * 0.36], [-rx * 0.85, -ry * 0.25]];
  fill(ctx, fr, hair); texHair(fr);
  // features follow the turn
  const fx = sh * 0.9, eyY = ry * 0.06, eyD = rx * 0.38;
  for (const side of [-1, 1]) {
    const far = (side > 0) === (turn < 0), k = 1 - (far ? Math.abs(turn) * 0.35 : 0);
    const cx = fx + side * eyD * (1 - Math.abs(turn) * 0.25), er = s * 0.055 * k;
    if (eyes > 0.15) {
      const o = clamp(eyes, 0, 1);
      ctx.fillStyle = sclera; ctx.beginPath(); ctx.ellipse(cx, eyY, er * 1.35, er * 1.5 * o, 0, 0, TAU); ctx.fill();
      ctx.fillStyle = ink; ctx.beginPath(); ctx.ellipse(cx + look[0] * er * 0.45, eyY + look[1] * er * 0.4 * o, er * 0.95, er * 1.1 * o, 0, 0, TAU); ctx.fill();
    } else {                                            // closed, happy: an arch
      taper(ctx, [[cx - er * 1.3, eyY + er * 0.3], [cx, eyY - er * 0.7], [cx + er * 1.3, eyY + er * 0.3]], s * 0.016, skinLine);
    }
  }
  // nose: one line; mouth: a smile line, or an open shape
  const nx = fx + turn * rx * 0.12;
  taper(ctx, [[nx - rx * 0.02, ry * 0.12], [nx - rx * 0.1 * Math.sign(turn || 1), ry * 0.3], [nx + rx * 0.04, ry * 0.34]], s * 0.013, skinLine);
  const my = ry * 0.5, mw = rx * (0.28 + 0.12 * smile);
  if (mouth > 0.05) {
    fill(ctx, [[fx - mw * 0.8, my - ry * 0.03], [fx, my + ry * (0.04 + 0.13 * mouth)], [fx + mw * 0.8, my - ry * 0.03], [fx, my + ry * 0.01]], ink);
  } else {
    taper(ctx, [[fx - mw, my - ry * 0.06 * smile], [fx, my + ry * 0.08 * smile], [fx + mw, my - ry * 0.06 * smile]], s * 0.015, skinLine);
  }
  ctx.restore();
}
