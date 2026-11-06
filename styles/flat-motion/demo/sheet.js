// Model sheet: the rig's hands and heads at the film's palette (index.html?test=model)
import { hand, head } from './engine/rig.js';
import { writeOn } from './engine/fx.js';
import { P } from './film.js';
export function modelSheet(ctx) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = P.cream; ctx.fillRect(0, 0, 1920, 1080);
  const heads = [[0, 1, 0.6, 0], [0.35, 1, 0.9, 0], [-0.35, 0, 0.9, 0], [0.2, 1, 0.9, 0.6]];
  heads.forEach(([turn, eyes, smile, mouth], i) => {
    head(ctx, { x: 260 + i * 450, y: 300, s: 380, turn, eyes, look: [turn * 1.5, 0], smile, mouth, skin: P.skin, skinLine: P.skinLn,
      hair: P.ink, hairMarks: [P.inkLt, P.cob], hairStyle: i === 3 ? 'short' : 'bob', seed: 3, ink: P.ink, sclera: P.cream });
  });
  [[0, 0.1], [0.3, 0.25], [0.6, 0.5], [0.9, 0.8]].forEach(([curl, sp], i) => {
    hand(ctx, { x: 160 + i * 460, y: 820, ang: -0.6, s: 260, curl, spread: sp, skin: P.skin, line: P.skinLn, thumb: 0.5 });
  });
  writeOn(ctx, 'model sheet: turn, eyes, smile / hand curl 0 · 0.3 · 0.6 · 0.9', 960, 1050, { size: 34, color: P.ink, seed: 2 });
}
