// "One Orange" — the demo film of Flat Illustration Motion.
// render(t): quantise t to the 12 fps drawing grid, pick the shot, draw it. Nothing carries between frames.
import { clamp, lerp, seg, ss, eio, eo, ei, back, mulberry } from '/core/lib.js';
import { step, fill, poly, taper, line, ell, blob, scallop, hatch, arcs, rays, tooth, mix, flowAngle, flowCircular, TAU } from './engine/paint.js';
import { ik2, limb, hand, head } from './engine/rig.js';
import { setCam, toScreen, dive, bowed, trail, streaks, mist, writeOn, bubble } from './engine/fx.js';
import { SHOTS, T, DUR } from './timeline.js';

export const W = 1920, H = 1080;
// palette: four inks + cream (STYLE §3). Hatching mixes are derived, never new hues.
export const P = {
  ink: '#15123B', cob: '#2C46D2', tang: '#FF8B3D', skin: '#B9714F', cream: '#FFEBD0',
  cobLt: '#5B73F0', cobDk: '#22389F', tangDk: '#E8662A', skinLn: '#7A3F2A', inkLt: '#2A2566',
};
const R = 230;            // the orange
let TX = [];              // texts on screen this frame (for readcheck)

// ---------- shared props ----------
function table(ctx, x0, y0, x1, y1, col = P.cob) {
  ctx.fillStyle = col; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
  hatch(ctx, null, { seed: 21, count: 900, len: [60, 220], width: 2.2, colors: [P.cobDk], alpha: 0.55, flow: flowAngle(0.08), bbox: [x0, y0, x1, y1], curve: 3 });
}
// the peel ribbon: an outward spiral around the fruit. k = 0…1 how much is laid; wmul widens it into a road
function ribbonPts(k, sy = 1, lift = null) {
  const out = [], a0 = -0.5, turns = 2.15, n = Math.max(2, Math.round(120 * k));
  for (let i = 0; i <= n; i++) {
    const th = a0 + (i / 120) * turns * TAU, r = R + 38 + 74 * (th - a0) / TAU;
    const X = Math.cos(th) * r, Y = Math.sin(th) * r;
    out.push(lift ? lift(X, Y, r) : [X, Y * sy]);
  }
  return out;
}
function ribbon(ctx, pts, w = 46, road = 0) {
  if (pts.length < 2) return;
  taper(ctx, pts, u => w * (0.75 + 0.25 * Math.min(1, u * 8)), P.cream, { caps: true, per: 2 });
  taper(ctx, pts, u => w * 0.68 * (0.75 + 0.25 * Math.min(1, u * 8)), P.tang, { caps: true, per: 2 });
  if (road > 0.01) {                              // dashed centre line once it is a road
    ctx.save(); ctx.globalAlpha = road; ctx.setLineDash([w * 0.5, w * 0.6]);
    line(ctx, pts, P.cream, w * 0.08, false); ctx.restore();
  }
}
// the orange, top-down. peel 0…1 = the cream pith disc grows from the stem; rot turns the marks with the fruit
function orange(ctx, x, y, { peel = 0, rot = 0, r = R, segs = 0, gap = 0, seed = 2 } = {}) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
  const skinPts = blob(0, 0, r, r, { n: 18, seed, wob: 0.018 });
  fill(ctx, skinPts, P.tang);
  hatch(ctx, skinPts, { seed: 31, count: 520, len: [r * 0.06, r * 0.16], width: 2.4, colors: [P.tangDk], flow: flowCircular(0, 0),
    density: (X, Y) => clamp((X + Y) / (r * 1.6) + 0.25), curve: 3 });
  tooth(ctx, skinPts, P.tangDk, { seed: 33, count: 260, size: [2, 3.5], alpha: 0.7 });
  taper(ctx, [[-r * 0.62, -r * 0.35], [-r * 0.5, -r * 0.55], [-r * 0.3, -r * 0.66]], r * 0.07, P.cream);
  if (peel > 0) {
    const rp = r * 0.94 * peel, pith = scallop(0, 0, rp, { bumps: 11, depth: 0.05, seed: 8 });
    fill(ctx, pith, P.cream);
    for (let i = 0; i < 10; i++) {                 // segment lines, faint until the pith is wide
      const a = i / 10 * TAU + 0.2;
      taper(ctx, [[0, 0], [Math.cos(a) * rp * 0.5, Math.sin(a) * rp * 0.5], [Math.cos(a + 0.05) * rp * 0.92, Math.sin(a + 0.05) * rp * 0.92]], 3.2, mix(P.cream, P.tangDk, 0.55));
    }
  }
  // stem: a small star
  const st = [];
  for (let i = 0; i < 10; i++) { const a = i / 10 * TAU, q = i % 2 ? 9 : 20; st.push([Math.cos(a) * q, Math.sin(a) * q]); }
  if (peel < 0.15) poly(ctx, st, P.ink);
  ctx.restore();
}
// a peeled orange in wedges (segs) that can open (gap) and split in halves (split px)
function wedges(ctx, x, y, { r = R, gap = 0, split = 0, rot = 0, n = 10, lift = -1, liftY = 0 } = {}) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
  for (let i = 0; i < n; i++) {
    if (i === lift) continue;
    const a0 = i / n * TAU, a1 = (i + 1) / n * TAU, am = (a0 + a1) / 2;
    const side = Math.cos(am) >= 0 ? 1 : -1;
    const ox = Math.cos(am) * gap + side * split, oy = Math.sin(am) * gap;
    wedge(ctx, ox, oy, r, a0, a1);
  }
  ctx.restore();
}
function wedge(ctx, ox, oy, r, a0, a1) {
  const pts = [[ox, oy]];
  for (let k = 0; k <= 8; k++) { const a = lerp(a0 + 0.012, a1 - 0.012, k / 8); pts.push([ox + Math.cos(a) * r, oy + Math.sin(a) * r]); }
  poly(ctx, pts, P.cream);
  const inner = [[ox + Math.cos((a0 + a1) / 2) * 6, oy + Math.sin((a0 + a1) / 2) * 6]];
  for (let k = 0; k <= 8; k++) { const a = lerp(a0 + 0.04, a1 - 0.04, k / 8); inner.push([ox + Math.cos(a) * r * 0.9, oy + Math.sin(a) * r * 0.9]); }
  poly(ctx, inner, P.tang);
  const am = (a0 + a1) / 2;
  taper(ctx, [[ox + Math.cos(am) * r * 0.2, oy + Math.sin(am) * r * 0.2], [ox + Math.cos(am) * r * 0.75, oy + Math.sin(am) * r * 0.75]], 4, P.tangDk);
}
// a forearm from off-frame into a hand (top-down shots)
function arm(ctx, from, wrist, ang, { curl = 0.3, s = 250, mirror = false, thumb = 0.5, sleeve = P.cobLt } = {}) {
  const mid = [lerp(from[0], wrist[0], 0.55), lerp(from[1], wrist[1], 0.55)];
  taper(ctx, [from, mid, wrist], u => lerp(150, 100, u), P.skin, { caps: true });
  taper(ctx, [from, [lerp(from[0], wrist[0], 0.3), lerp(from[1], wrist[1], 0.3)]], u => lerp(190, 175, u), sleeve, { caps: true });
  hand(ctx, { x: wrist[0], y: wrist[1], ang, s, curl, spread: 0.1, skin: P.skin, line: P.skinLn, mirror, thumb });
}

// ---------- shots ----------
function shotPeel(ctx, t) {
  const u = seg(t, 0, 4);
  setCam(ctx, W, H, { z: lerp(1.32, 1.42, ss(u)), rot: lerp(-0.05, 0.03, u), y: 40 });
  table(ctx, -2400, -1600, 2400, 1600);
  const k = ss(seg(t, T.peel0, T.peel1));
  ribbon(ctx, ribbonPts(k));
  const rot = 0.55 * t;
  orange(ctx, 0, 0, { peel: k * 0.85, rot });
  // hands: left grips the side, right thumb digs in and then peels
  const rel = ss(seg(t, T.release, 4.2)) * 120, dig = seg(t, T.dig - 0.25, T.dig) - seg(t, T.dig + 0.2, T.dig + 0.5);
  arm(ctx, [-700, 700], [-R - 70 - rel, 120 + rel * 0.4], -0.42, { curl: 0.28 });
  arm(ctx, [720, 700], [R + 60 + rel, 110 + rel * 0.4], Math.PI + 0.42 - dig * 0.1, { curl: 0.28 + dig * 0.3, mirror: true, thumb: 0.2 + dig * 0.7 });
  mist(ctx, { seed: 4, x: R * 0.55, y: -R * 0.35, r: 180, n: 34, u: seg(t, T.dig, T.dig + 0.6), color: P.cream, ang: -0.9, spread: 2.2, size: 7 });
  mist(ctx, { seed: 5, x: R * 0.55, y: -R * 0.35, r: 140, n: 18, u: seg(t, T.dig, T.dig + 0.5), color: P.tang, ang: -0.6, spread: 2.4, size: 6 });
}

// the hill world shared by the dive and the tilt: same spiral geometry as the table, redrawn as land
const HH = 430, RH = 640;               // hill height and radius (world px)
const hgt = r => HH * Math.max(0, 1 - (r / RH) ** 2);
function shotDive(ctx, t) {
  const u = seg(t, 4, 7), m = ss(seg(t, T.diveMorph0, T.diveMorph1));
  const z = dive(1.42, 0.5, eio(u));
  setCam(ctx, W, H, { z, rot: lerp(0.03, 0.42, eio(u)), y: lerp(40, 0, eio(u)) });
  const land = mix(P.cob, P.ink, m);
  ctx.fillStyle = land; ctx.fillRect(-4000, -4000, 8000, 8000);
  // no dissolves: marks are added or removed in steps and shapes swap on a drawing in fast motion
  if (m < 0.98) hatch(ctx, null, { seed: 21, count: Math.round(900 * (1 - m)), len: [60, 220], width: 2.2, colors: [P.cobDk], alpha: 0.55, flow: flowAngle(0.08), bbox: [-2400, -1600, 2400, 1600], curve: 3 });
  if (m > 0.02) {                        // land: contour marks round the hill, trees popping in one by one
    arcs(ctx, 0, 0, RH * 0.2, 2600, { seed: 51, count: Math.round(2600 * m), span: [0.08, 0.35], width: 2.6 / z, colors: [P.inkLt, P.cobDk],
      density: (q, rr) => rr < RH ? 0.9 : 0.55 });
    trees(ctx, m);
  }
  // the hill under the road darkens in steps after the swap
  if (m >= 0.5) {
    fill(ctx, blob(0, 0, RH, RH, { n: 20, seed: 4, wob: 0.02 }), mix(land, P.inkLt, seg(m, 0.5, 1)));
    for (let k = 1; k <= 6; k++) line(ctx, ell(0, 0, RH * k / 7, RH * k / 7, 0, 60), P.cob, 3 / z, false);
    // the orange's disc stays where it was and changes colour in steps until it is the summit
    // (no colour mixing: dark marks take the disc over, then it is solid)
    const q = seg(m, 0.5, 0.9), disc = blob(0, 0, R, R, { n: 18, seed: 2, wob: 0.018 });
    fill(ctx, disc, q < 1 ? P.tang : P.inkLt);
    if (q > 0 && q < 1) hatch(ctx, disc, { seed: 57, count: Math.round(2200 * q), len: [30, 90], width: 7, colors: [P.inkLt], flow: flowCircular(0, 0), curve: 3 });
  }
  // orange → summit: swapped on one drawing, mid-dive, when the motion hides the change
  if (m < 0.5) orange(ctx, 0, 0, { peel: 0.85, rot: 0.55 * t });
  ribbon(ctx, ribbonPts(1), 46 * lerp(1, 1.5, m), m);
  // hands leave the frame as the camera rises
  const out = ss(seg(t, 4, 4.7)), rel = ss(seg(t, T.release, 4.2)) * 120;     // continues the peel shot's release
  if (out < 1) {
    arm(ctx, [-700 - out * 900, 700 + out * 500], [-R - 70 - rel - out * 900, 120 + rel * 0.4 + out * 500], -0.42, { curl: 0.28 });
    arm(ctx, [720 + out * 900, 700 + out * 500], [R + 60 + rel + out * 900, 110 + rel * 0.4 + out * 500], Math.PI + 0.42, { curl: 0.28, mirror: true, thumb: 0.2 });
  }
  if (t > T.riderIn) riderDot(ctx, seg(t, T.riderIn, 9.0), 1, z);
}
// trees on the land round the hill; pop in one by one with m; stand up as the camera lowers (sp < 1)
function trees(ctx, m, proj = null, sp = 1, minY = -Infinity) {
  const tr = mulberry(77);
  for (let i = 0; i < 70; i++) {
    const a = tr() * TAU, rr = lerp(RH * 1.05, 2400, Math.sqrt(tr())), X = Math.cos(a) * rr, Y = Math.sin(a) * rr, s0 = lerp(18, 34, tr());
    const s = s0 * back(seg(m, 0.15 + 0.7 * i / 70, 0.25 + 0.7 * i / 70), 2);
    if (s <= 0.5) continue;
    const [x, y] = proj ? proj([X, Y]) : [X, Y], up = s * (1 - sp) * 1.4;
    if (y - up - s < minY) continue;
    fill(ctx, blob(x, y - up, s, s * (1 + (1 - sp) * 0.5), { n: 8, seed: i, wob: 0.15 }), P.cobDk);
    fill(ctx, blob(x - s * 0.25, y - up - s * 0.25, s * 0.55, s * 0.55, { n: 7, seed: i + 9, wob: 0.15 }), P.cob);
  }
}
// the tiny rider climbing the spiral (from outside to the summit)
function roadAt(k) { const pts = ribbonPts(1); const i = clamp(Math.round((1 - k) * (pts.length - 1)), 0, pts.length - 1); return [pts[i], pts[Math.max(0, i - 1)]]; }
function riderDot(ctx, k, sy, z, proj = null) {
  const [p, q] = roadAt(lerp(0.0, 0.55, k));
  const a = proj ? proj(p) : p, b = proj ? proj(q) : q;
  const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), s = 13 / Math.max(0.5, z);
  ctx.save(); ctx.translate(a[0], a[1]);
  if (sy > 0.6) { ctx.rotate(ang); fill(ctx, ell(0, 0, s * 1.7, s * 0.42), P.ink); fill(ctx, ell(-s * 0.2, 0, s * 0.62, s * 0.7), P.cream); fill(ctx, ell(s * 0.3, 0, s * 0.4, s * 0.4), P.tang); }
  else { fill(ctx, ell(0, -s * 1.1, s * 0.5, s * 0.9), P.cream); fill(ctx, ell(0, -s * 2.1, s * 0.42, s * 0.42), P.skin); fill(ctx, ell(0, 0, s * 0.9, s * 0.25), P.ink); }
  ctx.restore();
}
function shotTilt(ctx, t) {
  const u = eio(seg(t, 7, 9));
  const phi = lerp(Math.PI / 2, 0.32, u), sp = Math.sin(phi), cp = Math.cos(phi);
  const z = lerp(0.5, 1.2, u), rot = lerp(0.42, 0, ss(seg(t, 7, 8.2)));
  const proj = ([X, Y]) => { const r = Math.hypot(X, Y); return [X, Y * sp - hgt(r) * cp]; };
  setCam(ctx, W, H, { z, rot, y: lerp(0, -250, u) });
  // sky descends from the top as the camera lowers (a horizon bowed by the lens)
  ctx.fillStyle = P.ink; ctx.fillRect(-4000, -4000, 8000, 8000);
  arcs(ctx, 0, 0, RH * 0.2, 2600, { seed: 51, count: 2600, span: [0.08, 0.35], width: 2.6 / z, colors: [P.inkLt, P.cobDk], sy: sp, density: (q, rr) => rr < RH ? 0.9 : 0.55 });
  const hy = lerp(-3000, -330, u), bow = lerp(0, 90, u);
  ctx.beginPath(); ctx.moveTo(-4000, -4000);
  for (const [x, y] of bowed(-2200, 2200, hy, bow)) ctx.lineTo(x, y);
  ctx.lineTo(4000, hy); ctx.lineTo(4000, -4000); ctx.closePath(); ctx.fillStyle = P.cob; ctx.fill();
  trees(ctx, 1, proj, sp, hy + 10);
  // the hill dome: silhouette from the projected surface
  const top = [];
  for (let i = 0; i <= 48; i++) {
    const X = lerp(-RH, RH, i / 48); let best = Infinity;
    for (let j = 0; j <= 48; j++) { const Y = lerp(-RH, RH, j / 48); if (X * X + Y * Y > RH * RH) continue; best = Math.min(best, proj([X, Y])[1]); }
    top.push([X, best]);
  }
  const base = []; for (let i = 48; i >= 0; i--) { const a = Math.PI * i / 48; base.push([Math.cos(a) * RH, Math.sin(a) * RH * sp]); }
  ctx.beginPath(); ctx.moveTo(top[0][0], top[0][1]); for (const p of top) ctx.lineTo(p[0], p[1]); for (const p of base) ctx.lineTo(p[0], p[1]); ctx.closePath();
  ctx.fillStyle = P.inkLt; ctx.fill();
  // contour rings on the dome
  ctx.save(); ctx.clip();
  for (let k = 1; k <= 6; k++) { const rr = RH * k / 7, ring = []; for (let i = 0; i <= 60; i++) { const a = i / 60 * TAU; ring.push(proj([Math.cos(a) * rr, Math.sin(a) * rr])); } line(ctx, ring, P.cob, 3 / z, false); }
  ctx.restore();
  // the road: only the parts that face the camera
  const vis = ([X, Y]) => Y > -(RH * RH) * Math.tan(phi) / (2 * HH) + 1e-6 || sp > 0.97;
  const pts = ribbonPts(1), runs = []; let cur = [];
  for (const p of pts) { if (vis(p)) cur.push(proj(p)); else if (cur.length) { runs.push(cur); cur = []; } }
  if (cur.length) runs.push(cur);
  for (const r of runs) if (r.length > 1) ribbon(ctx, r, 69 * lerp(1, 0.75, u), 1);
  riderDot(ctx, seg(t, T.riderIn, 9.0), sp, z, proj);
}

// front view rider, in rider units (1 = wheel-to-head span ≈ 1.9); pedal phase ph
function riderFront(ctx, x, y, k, ph) {
  ctx.save(); ctx.translate(x, y); ctx.scale(k, k);
  const kn = Math.sin(ph);
  // legs behind the wheel
  for (const s of [-1, 1]) {
    const hip = [s * 0.11, -0.12], foot = [s * 0.15, 0.5 + s * kn * 0.1];
    const [kj] = ik2(hip, foot, 0.36, 0.36, s);
    const knee = [s * 0.2 + s * 0.04 * kn, kj[1] - 0.04];
    limb(ctx, hip, knee, foot, 0.17, 0.11, P.skin);
    limb(ctx, hip, [lerp(hip[0], knee[0], 0.7), lerp(hip[1], knee[1], 0.7)], [lerp(hip[0], knee[0], 0.75), lerp(hip[1], knee[1], 0.75)], 0.2, 0.18, P.cob);
    fill(ctx, ell(foot[0], foot[1] + 0.03, 0.08, 0.05), P.ink);
  }
  // wheel, fork
  fill(ctx, ell(0, 0.62, 0.075, 0.38), P.ink);
  fill(ctx, ell(0, 0.62, 0.025, 0.3), P.inkLt);
  taper(ctx, [[0, 0.3], [0, 0.1], [0, -0.06]], 0.05, P.ink);
  // torso and arms
  fill(ctx, blob(0, -0.38, 0.27, 0.3, { seed: 61, wob: 0.04 }), P.cream);
  taper(ctx, [[-0.12, -0.6], [0, -0.52], [0.12, -0.6]], 0.02, mix(P.cream, P.skinLn, 0.4));
  for (const s of [-1, 1]) {
    const sh = [s * 0.22, -0.56], gr = [s * 0.34, -0.06];
    const [e] = ik2(sh, gr, 0.3, 0.3, -s);
    limb(ctx, sh, e, gr, 0.13, 0.09, P.skin);
    limb(ctx, sh, [lerp(sh[0], e[0], .4), lerp(sh[1], e[1], .4)], [lerp(sh[0], e[0], .5), lerp(sh[1], e[1], .5)], 0.16, 0.15, P.cream);
  }
  taper(ctx, [[-0.4, -0.08], [0, -0.03], [0.4, -0.08]], 0.045, P.ink);
  for (const s of [-1, 1]) fill(ctx, ell(s * 0.36, -0.07, 0.06, 0.05), P.skin);
  head(ctx, { x: 0, y: -0.86, s: 0.44, turn: 0.05, eyes: 1, look: [0, 0.4], smile: 0.8, skin: P.skin, skinLine: P.skinLn, hair: P.ink, hairMarks: [P.inkLt, P.cob], hairStyle: 'short', seed: 7, ink: P.ink });
  fill(ctx, blob(0, -1.06, 0.2, 0.09, { seed: 64, wob: 0.05 }), P.tang);          // cap
  fill(ctx, ell(0.08, -1.0, 0.16, 0.035), P.tang);
  ctx.restore();
}
function shotRide(ctx, t) {
  const u = seg(t, 9, 11);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = P.cob; ctx.fillRect(0, 0, W, H);
  const hy = 430;                                    // low angle: the hill's crest bowed by the lens
  ctx.beginPath(); ctx.moveTo(0, H); for (const [x, y] of bowed(-60, W + 60, hy + 70, 150)) ctx.lineTo(x, y); ctx.lineTo(W, H); ctx.closePath();
  ctx.fillStyle = P.ink; ctx.fill();
  hatch(ctx, bowed(-60, W + 60, hy + 70, 150).concat([[W + 60, H + 40], [-60, H + 40]]), { seed: 81 + Math.floor(t * 12) % 2, count: 700, len: [20, 70], width: 3, colors: [P.inkLt, P.cobDk], flow: flowAngle(-1.35), curve: 2 });
  // road converging to the crest
  const vx = W / 2 + 40, vy = hy - 80 + 70;
  poly(ctx, [[vx - 30, vy], [vx + 30, vy], [W * 0.98, H + 10], [W * 0.02, H + 10]], P.cream);
  poly(ctx, [[vx - 20, vy], [vx + 20, vy], [W * 0.9, H + 10], [W * 0.1, H + 10]], P.tang);
  const dash = (t * 2.6) % 1;
  for (let i = 0; i < 6; i++) { const a = ((i + dash) / 6) ** 2, b = ((i + dash + 0.45) / 6) ** 2; poly(ctx, [[lerp(vx - 2, W / 2 - 14, a), lerp(vy, H, a)], [lerp(vx + 2, W / 2 + 14, a), lerp(vy, H, a)], [lerp(vx + 2, W / 2 + 14, b), lerp(vy, H, b)], [lerp(vx - 2, W / 2 - 14, b), lerp(vy, H, b)]], P.cream); }
  // the rider comes at the lens: scale grows by a constant ratio, then the wheel fills the frame
  streaks(ctx, { seed: Math.floor(t * 12), x0: 0, y0: 0, x1: W, y1: H * 0.55, n: Math.round(6 + 14 * u), len: [80, 260], ang: 0, w: 3, color: P.cobLt });
  // the rider passes the lens: the shirt covers the frame on the last drawings (a wipe made of the subject)
  const k = dive(150, 4400, ei(u) * 0.8 + u * 0.2), f = (k - 150) / (4400 - 150);
  const ay = lerp(vy - 150, H / 2 + 0.38 * k, Math.pow(f, 0.85));
  riderFront(ctx, W / 2 + 10 - f * 60, ay, k, t * TAU * 1.3);
}

// side-view bike in silhouette, ink on the sun
function riderSide(ctx, x, y, s, { roll = 0, foot = 0, breathe = 0, look = 0 } = {}) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  const C = P.ink, wr = 0.36;
  for (const wx of [-0.62, 0.62]) {
    ctx.beginPath(); ctx.arc(wx, -wr, wr, 0, TAU); ctx.lineWidth = 0.06; ctx.strokeStyle = C; ctx.stroke();
    for (let i = 0; i < 6; i++) { const a = roll + i / 6 * Math.PI; line(ctx, [[wx + Math.cos(a) * wr, -wr + Math.sin(a) * wr], [wx - Math.cos(a) * wr, -wr - Math.sin(a) * wr]], C, 0.012, false); }
    fill(ctx, ell(wx, -wr, 0.05, 0.05), C);
  }
  const bb = [-0.05, -0.32], seat = [-0.22, -0.95], bar = [0.52, -1.02];
  line(ctx, [[-0.62, -wr], bb, [0.4, -0.86], [0.62, -wr]], C, 0.05, false);
  line(ctx, [[-0.62, -wr], seat, bb], C, 0.05, false); line(ctx, [seat, [0.4, -0.86]], C, 0.05, false);
  line(ctx, [[0.4, -0.86], bar, [0.62, -1.0]], C, 0.05, false);
  // rider
  const hip = [-0.22, -1.05 + breathe * 0.01], sh = [0.12, -1.72 + breathe * 0.02];
  taper(ctx, [hip, [-0.04, -1.42], sh], u => lerp(0.36, 0.3, u), C, { caps: true });
  const ped = [bb[0] + Math.cos(roll * 0.6) * 0.17, bb[1] + Math.sin(roll * 0.6) * 0.17];
  const footDown = [-0.32, -0.02];
  const f1 = foot > 0 ? [lerp(ped[0], footDown[0], foot), lerp(ped[1], footDown[1], foot)] : ped;
  const [k1] = ik2(hip, f1, 0.55, 0.58, -1); limb(ctx, hip, k1, f1, 0.17, 0.1, C);
  const ped2 = [bb[0] - Math.cos(roll * 0.6) * 0.17, bb[1] - Math.sin(roll * 0.6) * 0.17];
  const [k2] = ik2(hip, ped2, 0.55, 0.58, -1); limb(ctx, hip, k2, ped2, 0.17, 0.1, C);
  const [e] = ik2(sh, bar, 0.36, 0.36, 1); limb(ctx, sh, e, bar, 0.12, 0.08, C);
  ctx.save(); ctx.translate(0.24, -2.0); ctx.rotate(-0.15 - look * 0.35);
  fill(ctx, blob(0, 0, 0.19, 0.22, { seed: 71, wob: 0.04 }), C);
  fill(ctx, blob(-0.02, -0.12, 0.2, 0.1, { seed: 72 }), C); fill(ctx, ell(0.15, -0.1, 0.14, 0.035, -0.1), C);  // cap + peak
  ctx.restore();
  ctx.restore();
}
const SUN = [300, -70], SR = 400;
function sun(ctx, x, y, r, { halo = 1, spin = 0 } = {}) {
  if (halo > 0.01) arcs(ctx, x, y, r * 0.86, r * 1.9, { seed: 91, count: Math.round(2600 * halo), span: [0.1, 0.5], width: 3, colors: [P.tang, P.tangDk, P.cream],
    density: q => Math.pow(1 - q, 1.7), spin });
  fill(ctx, blob(x, y, r, r, { n: 22, seed: 93, wob: 0.012 }), P.tang);
  rays(ctx, x, y, r * 0.05, r * 0.98, { seed: 95, count: 700, len: [0.08, 0.3], width: 2.6, colors: [P.tangDk, mix(P.tang, P.cream, 0.5)], density: q => 0.35 + 0.65 * q });
  arcs(ctx, x, y, r * 0.88, r * 1.0, { seed: 97, count: 380, span: [0.05, 0.25], width: 3, colors: [P.cob, P.cobLt], density: q => q, spin });
}
function shotHill(ctx, t) {
  const pu = seg(t, T.push0, 15.0), zp = dive(1, 9.5, ei(pu));
  setCam(ctx, W, H, { z: zp, x: lerp(0, SUN[0], ss(pu)), y: lerp(0, SUN[1], ss(pu)) });
  ctx.fillStyle = P.cob; ctx.fillRect(-3000, -2000, 6000, 4000);
  sun(ctx, SUN[0], SUN[1], SR, { spin: t * 0.05 });
  // the ridge
  const ridge = bowed(-1300, 1300, 330, 120, 30).concat([[1300, 900], [-1300, 900]]);
  fill(ctx, ridge, P.ink);
  hatch(ctx, ridge, { seed: 99, count: 500, len: [16, 50], width: 3, colors: [P.inkLt, P.cobDk], flow: flowAngle(-1.4), density: (x, y) => clamp(1 - (y - 260) / 260), curve: 2 });
  // the rider rolls in and stops, foot down; a breath; looks up at the sun
  const mv = eo(seg(t, 11.0, T.stop)), x = lerp(-1250, -140, mv);
  const roll = -(x / 0.36 / 200);
  const groundY = 330 - 120 * (1 - Math.pow((x + 0) / 1300, 2)) + 6;
  riderSide(ctx, x, groundY, 200, { roll, foot: ss(seg(t, T.stop - 0.25, T.stop + 0.1)), breathe: Math.sin((t - 12) * 3.2) * (t > 12 ? 1 : 0), look: ss(seg(t, 12.5, 13.1)) });
}
function shotSun(ctx, t) {
  const pull = seg(t, T.pull0, 17.0), z = dive(5.2, 1.0, eio(pull));
  setCam(ctx, W, H, { z, rot: lerp(0, -0.35, eio(pull)) });
  // table under the sun: cobalt, the same blue as the sky
  table(ctx, -2600, -1800, 2600, 1800);
  ribbon(ctx, ribbonPts(1).map(([x, y]) => [x, y]), 46);
  const cr = seg(t, T.crack, T.crack + 0.25), gp = ss(seg(t, T.gaps, T.gaps + 0.5)) - ss(seg(t, 16.5, 17)) * 0.6;
  if (cr < 1) sun(ctx, 0, 0, R, { halo: 1 - pull, spin: t * 0.05 });
  if (cr > 0) {
    if (cr < 1) {                                       // cream cracks shoot out from the centre
      for (let i = 0; i < 10; i++) { const a = i / 10 * TAU; taper(ctx, [[0, 0], [Math.cos(a) * R * cr * 0.5, Math.sin(a) * R * cr * 0.5], [Math.cos(a) * R * cr * 1.02, Math.sin(a) * R * cr * 1.02]], 9, P.cream); }
    } else wedges(ctx, 0, 0, { gap: 24 * gp });
  }
}
function shotSplit(ctx, t) {
  const u = seg(t, 17, 19);
  setCam(ctx, W, H, { z: lerp(1.0, 1.12, ss(u)), rot: -0.35 + 0.1 * ss(u) });
  table(ctx, -1600, -1000, 1600, 1000);
  ribbon(ctx, ribbonPts(1), 46);
  const sp = ss(seg(t, T.split0, T.split1)) * 120, inn = eo(seg(t, T.handsIn, T.split0));
  const lift = ss(seg(t, 18.55, 19.0));
  wedges(ctx, 0, 0, { gap: 9, split: sp, lift: lift > 0 ? 2 : -1 });
  arm(ctx, [-900, 900 - inn * 0], [lerp(-900, -R - 70, inn) - sp, lerp(700, 80, inn)], -0.3, { curl: 0.55 });
  arm(ctx, [900, 900], [lerp(900, R + 70, inn) + sp, lerp(700, 60, inn)], -2.85, { curl: 0.55, mirror: true });
  if (lift > 0) {                                         // one segment rises toward the lens: the match to the next shot
    const a0 = 2 / 10 * TAU, a1 = 3 / 10 * TAU, sc = lerp(1, 3.2, lift);
    ctx.save(); ctx.translate(lerp(Math.cos(a0) * 30 + sp, 0, lift), lerp(Math.sin(a0) * 30, 120, lift)); ctx.scale(sc, sc); wedge(ctx, 0, 0, R, a0, a1); ctx.restore();
  }
}
function shotShare(ctx, t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const sway = Math.sin(t * 2.2) * 6;
  ctx.fillStyle = P.cream; ctx.fillRect(0, 0, W, H);
  // window at dusk behind her: the sun again, small
  poly(ctx, [[1060, 90], [1640, 90], [1640, 560], [1060, 560]], P.cob);
  fill(ctx, blob(1430, 300, 95, 95, { seed: 5, wob: 0.02 }), P.tang);
  arcs(ctx, 1430, 300, 92, 170, { seed: 6, count: 260, span: [0.1, 0.4], width: 2.6, colors: [P.tang, P.cream], density: q => (1 - q) ** 1.6 });
  poly(ctx, [[1060, 500], [1640, 470], [1640, 560], [1060, 560]], P.ink);
  ctx.fillStyle = P.cream; ctx.fillRect(1340, 90, 16, 470); ctx.fillRect(1060, 300, 580, 14);
  // her: shoulders, head, the offering arm
  const hx = 600 + sway, hy = 430;
  fill(ctx, blob(hx - 20, hy + 520, 400, 300, { seed: 12, wob: 0.03 }), P.cobLt);
  hatch(ctx, blob(hx - 20, hy + 520, 400, 300, { seed: 12, wob: 0.03 }), { seed: 14, count: 160, len: [30, 80], width: 3, colors: [P.cob], flow: flowAngle(1.2), alpha: 0.6, curve: 2 });
  fill(ctx, blob(hx, hy + 230, 85, 110, { seed: 13 }), P.skin);
  taper(ctx, [[hx - 110, hy + 255], [hx, hy + 320], [hx + 100, hy + 255]], 5, P.cob);
  const open = ss(seg(t, 19.7, 19.85)), lookR = ss(seg(t, 19.8, 20.2));
  const blink = Math.abs(t - 22.4) < 0.09 ? 0 : 1;
  head(ctx, { x: hx + 10, y: hy, s: 470, turn: 0.25 * lookR, tilt: -0.05 + 0.04 * Math.sin(t * 2.2), eyes: open * blink, look: [0.8 * lookR, 0.1], smile: 0.9, mouth: t > 20.95 && t < 21.6 ? 0.6 : 0,
    skin: P.skin, skinLine: P.skinLn, hair: P.ink, hairMarks: [P.inkLt, P.cobDk, P.cobDk, P.cob], hairStyle: 'bob', seed: 3, ink: P.ink, sclera: P.cream });
  // offering arm and the segment
  const of = eio(seg(t, T.offer0, T.offer1)), tk = ss(seg(t, T.take, T.take + 0.5));
  const handP = [lerp(hx + 330, 1080, of) + tk * 50, lerp(860, 660, of) + tk * 10];
  const sh = [hx + 250, hy + 400];
  const [el] = ik2(sh, handP, 330, 320, -1);
  limb(ctx, sh, el, handP, 125, 85, P.skin);
  limb(ctx, sh, [lerp(sh[0], el[0], .4), lerp(sh[1], el[1], .4)], [lerp(sh[0], el[0], .5), lerp(sh[1], el[1], .5)], 150, 140, P.cobLt);
  // the table edge in front
  poly(ctx, [[0, 900], [W, 880], [W, H], [0, H]], P.cob);
  hatch(ctx, [[0, 900], [W, 880], [W, H], [0, H]], { seed: 15, count: 200, len: [60, 200], width: 2.4, colors: [P.cobDk], flow: flowAngle(-0.01), alpha: 0.7, curve: 2 });
  const segP = [handP[0] + 120, handP[1] - 95];
  ctx.save(); ctx.translate(segP[0], segP[1]); ctx.rotate(-0.55 + tk * 0.3); wedge(ctx, -R * 0.8, 0, R * 1.35, -0.3, 0.3); ctx.restore();
  hand(ctx, { x: handP[0], y: handP[1], ang: -0.65, s: 240, curl: 0.55, spread: 0.1, skin: P.skin, line: P.skinLn, thumb: 0.6 });
  // the friend's hand from the right, striped sleeve
  const fi = eo(seg(t, 20.4, T.take)), fx = lerp(W + 380, segP[0] + 300, fi) + tk * 30, fy = segP[1] + 30;
  taper(ctx, [[W + 500, fy + 160], [fx + 160, fy + 60], [fx + 40, fy]], u => lerp(150, 95, u), P.skin, { caps: true });
  const sl = [[W + 520, fy + 190], [lerp(W + 520, fx + 160, 0.7), lerp(fy + 190, fy + 60, 0.7)]];
  taper(ctx, sl, 190, P.ink, { caps: true });
  for (let i = 1; i < 4; i++) { const v = i / 4; taper(ctx, [[lerp(sl[0][0], sl[1][0], v), lerp(sl[0][1], sl[1][1], v) - 85], [lerp(sl[0][0], sl[1][0], v) + 10, lerp(sl[0][1], sl[1][1], v) + 85]], 22, P.cream); }
  hand(ctx, { x: fx, y: fy, ang: Math.PI + 0.35, s: 230, curl: 0.3 + 0.35 * tk, spread: 0.1, skin: P.skin, line: P.skinLn, mirror: true, thumb: 0.5 });
  // THANKS! from the friend
  const pop = seg(t, T.bubble, T.bubble + 0.25), wr = seg(t, T.bubble + 0.05, T.bubbleW);
  const b = bubble(ctx, { x: 1500, y: 230, w: 440, h: 210, tail: [1800, 470], text: 'THANKS!', pop, write: wr, size: 92, ink: P.ink, paper: '#FFFFFF', seed: 4 });
  if (b && t >= T.bubble) TX.push({ id: 'thanks', text: 'THANKS!', x0: 1280, y0: 125, x1: 1720, y1: 335 });
}
function shotEnd(ctx, t) {
  const u = seg(t, 23.5, DUR);
  const z = dive(1.15, 0.78, eio(seg(t, 23.5, 27))), rot = lerp(0.25, 0.05, eio(u));
  setCam(ctx, W, H, { z, rot });
  table(ctx, -2600, -1800, 2600, 1800);
  ribbon(ctx, ribbonPts(1), 46);
  // segments laid as rays round an empty centre: the sun again
  for (let i = 0; i < 9; i++) {
    const a = i / 9 * TAU - 0.3; ctx.save(); ctx.translate(Math.cos(a) * 40, Math.sin(a) * 40); ctx.rotate(a); wedge(ctx, 0, 0, R * 0.95, -0.27, 0.27); ctx.restore();
  }
  fill(ctx, ell(0, 0, 60, 60), P.cream); fill(ctx, ell(0, 0, 44, 44), P.tang);
  // two cups
  for (const [x, y, s] of [[-640, -330, 0.85], [660, 360, 0.8]]) {
    fill(ctx, ell(x + 14, y + 16, 150 * s, 150 * s), P.cobDk);
    fill(ctx, ell(x, y, 150 * s, 150 * s), P.cream);
    fill(ctx, ell(x, y, 98 * s, 98 * s), P.ink);
    arcs(ctx, x, y, 20 * s, 90 * s, { seed: 3 + x, count: 40, span: [0.4, 1.2], width: 2.5, colors: [P.inkLt], spin: t * 0.6 });
    taper(ctx, [[x + 150 * s, y - 30 * s], [x + 215 * s, y], [x + 150 * s, y + 30 * s]], 26 * s, P.cream);
  }
  // title, written on in screen space
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const wr = seg(t, T.title, T.titleW);
  if (t >= T.title) {
    writeOn(ctx, 'One Orange', W / 2, H - 120, { size: 120, font: 'Gochi Hand', color: P.cream, u: wr, seed: 11 });
    TX.push({ id: 'title', text: 'One Orange', x0: W / 2 - 300, y0: H - 230, x1: W / 2 + 300, y1: H - 90 });
  }
}

const DRAW = { peel: shotPeel, dive: shotDive, tilt: shotTilt, ride: shotRide, hill: shotHill, sun: shotSun, split: shotSplit, share: shotShare, end: shotEnd };
let lastStep = -1;
export function renderFrame(ctx, t) {
  const ts = Math.min(step(t), DUR - 1 / 12);
  if (ts === lastStep) return;            // on twos: the same drawing holds for two frames
  lastStep = ts; TX = [];
  const shot = SHOTS.find(s => ts >= s.t0 && ts < s.t1) || SHOTS[SHOTS.length - 1];
  ctx.save(); DRAW[shot.id](ctx, ts); ctx.restore();
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
}
export function textsAt(ctx, t) { renderFrame(ctx, t); return TX; }
