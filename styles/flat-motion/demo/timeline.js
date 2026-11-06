// "One Orange" — the single timeline. Picture, score, foley and checks all read these numbers.
export const BPM = 120, BEAT = 60 / BPM, BAR = 4 * BEAT;   // bar = 2.0 s
export const DUR = 29.0;

// shots (the picture cuts or turns into the next shot at t0)
export const SHOTS = [
  { id: 'peel', t0: 0.0, t1: 4.0 },     // top-down: hands, orange, the peel ribbon
  { id: 'dive', t0: 4.0, t1: 7.0 },     // dive out: the ribbon becomes a road on a hill
  { id: 'tilt', t0: 7.0, t1: 9.0 },     // crane down from top-down to a low angle
  { id: 'ride', t0: 9.0, t1: 11.0 },    // rider at the lens, wheel wipe
  { id: 'hill', t0: 11.0, t1: 15.0 },   // hilltop, the sun, the breath, push into the sun
  { id: 'sun', t0: 15.0, t1: 17.0 },    // the sun cracks into segments, pull back to the table
  { id: 'split', t0: 17.0, t1: 19.0 },  // hands pull the orange in two
  { id: 'share', t0: 19.0, t1: 23.5 },  // across the table: offer, take, THANKS!
  { id: 'end', t0: 23.5, t1: 29.0 },    // crane up over the table, title
];

// key times
export const T = {
  dig: 0.9, peel0: 1.2, peel1: 3.9, release: 3.7,
  diveMorph0: 4.6, diveMorph1: 6.4, riderIn: 6.0,
  bell: 9.5, pass: 10.55,
  stop: 12.0, quiet0: 12.0, quiet1: 15.5, push0: 13.5,
  crack: 15.5, gaps: 15.75, pull0: 15.9,
  handsIn: 17.2, split0: 17.8, split1: 18.5,
  offer0: 19.6, offer1: 20.4, take: 20.9, bubble: 21.0, bubbleW: 21.5,
  title: 24.8, titleW: 25.7, chord: 25.0,
};

// sound events (foley), exported with events.mjs → events.json → mix.py
export const EV = [
  { t: T.dig, type: 'squeak' }, { t: T.dig + 0.08, type: 'mist' },
  { t: T.peel0, type: 'peel', dur: T.peel1 - T.peel0 },
  { t: 4.0, type: 'dive', dur: 2.6 },
  { t: T.riderIn, type: 'chain', dur: 5.8 },
  { t: T.bell, type: 'bell' },
  { t: T.pass - 0.25, type: 'pass' },
  { t: 11.75, type: 'brake' }, { t: T.stop, type: 'foot' },
  { t: 11.0, type: 'cicadas', dur: 4.6 },
  { t: T.push0, type: 'hum', dur: T.crack - T.push0 },
  { t: T.crack, type: 'crack' },
  { t: T.split0, type: 'split' },
  { t: T.offer0, type: 'cloth' },
  { t: T.take, type: 'take' },
  { t: T.bubble, type: 'pop' }, { t: T.bubble + 0.05, type: 'scribble', dur: T.bubbleW - T.bubble },
  { t: T.title, type: 'scribble', dur: T.titleW - T.title },
];
