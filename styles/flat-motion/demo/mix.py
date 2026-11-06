"""One Orange — foley, ambience and score → out/mix.wav (mastered later by core/render/mux.sh).

Every foley sound sits on an event from the picture (events.json, exported from timeline.js), so nothing drifts.
Run: .venv/bin/python styles/flat-motion/demo/mix.py
"""
import json, os, sys
import numpy as np
from scipy.io import wavfile

D = os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get('LIB') or os.path.abspath(os.path.join(D, '..', '..', '..'))
sys.path.insert(0, os.path.join(LIB, 'core', 'audio'))
from sfx import SR, add, lp, hp, bp, noise, brown, norm, whoosh, pop, thump, limit  # noqa: E402

TL = json.load(open(os.path.join(D, 'out', 'timeline.json')))
EVJ = json.load(open(os.path.join(D, 'events.json')))
DUR, T = EVJ['dur'], TL['T']
N = int(DUR * SR)
mix = np.zeros((N, 2))
rng = np.random.default_rng(11)


from sfx import t_ as tt  # same rounding as sfx.noise()


def fade(x, a=0.02, b=0.05):
    n = len(x); ia, ib = min(n, int(a * SR)), min(n, int(b * SR))
    if ia: x[:ia] *= np.linspace(0, 1, ia)
    if ib: x[-ib:] *= np.linspace(1, 0, ib)
    return x


# ---------- foley (tactile, close, small) ----------
def squeak():       # thumb pressing into the skin
    t = tt(0.22); f = 900 + 500 * t / 0.22
    return fade(bp(noise(0.22), 700, 2500) * 0.5 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25) * np.exp(-t / 0.08)
def mist():         # a fine spritz of juice
    t = tt(0.35); return hp(noise(0.35), 5000) * np.exp(-t / 0.07)
def peel(d):        # the peel tearing in one long ribbon: fibrous crackle over a soft rip
    t = tt(d); x = bp(noise(d), 1200, 5000) * 0.25 * (0.6 + 0.4 * np.sin(2 * np.pi * 3.1 * t) ** 2)
    k = (rng.random(len(t)) > 0.9965).astype(float); x += hp(np.convolve(k, np.exp(-np.arange(90) / 12), 'same'), 2500) * 0.9
    return fade(x, 0.05, 0.3)
def dive(d):        # air rising as the camera climbs
    t = tt(d); w = noise(d); out = np.zeros_like(w)
    for i in range(0, len(w), 960):
        f = 300 + 2200 * (i / len(w)) ** 1.5; seg = bp(w[max(0, i - 3000):i + 960], f * 0.6, f * 1.6)[-min(960, len(w) - i):]; out[i:i + len(seg)] = seg
    return fade(out * np.sin(np.pi * t / d) ** 1.5, 0.1, 0.4)
def chain(d):       # a freewheel ticking under the pedalling
    out = np.zeros(int(d * SR)); k = 0.0
    while k < d - 0.05:
        c = bp(noise(0.02), 3000, 8000) * np.exp(-tt(0.02) / 0.003); s = int(k * SR); out[s:s + len(c)] += c[:len(out) - s]; k += 1 / 9.5
    return out * 0.5
def bell():         # a bike bell: two strikes, inharmonic partials
    out = np.zeros(int(1.6 * SR))
    for at in (0.0, 0.16):
        t = tt(1.4); x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau) for f, a, tau in [(2960, 1, .5), (4410, .5, .3), (6170, .3, .15), (1480, .2, .4)])
        s = int(at * SR); out[s:s + len(x)] += x[:len(out) - s]
    return norm(out) * 0.6
def brake():        # rubber squeal, short
    t = tt(0.45); f = 2100 + 60 * np.sin(2 * np.pi * 23 * t)
    return fade(np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25 + bp(noise(0.45), 1500, 3500) * 0.15, 0.03, 0.15)
def cicadas(d):     # a pulsing high buzz, the bed of the silence
    t = tt(d); car = bp(noise(d), 4200, 6800)
    am = (0.5 + 0.5 * np.sin(2 * np.pi * 34 * t)) ** 3 * (0.55 + 0.45 * np.sin(2 * np.pi * 0.31 * t + 1))
    return fade(car * am, 0.5, 0.6)
def hum(d):         # the sun's low hum, rising as we push in
    t = tt(d); f = 55 + 55 * (t / d) ** 2
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.35 * np.sin(4 * np.pi * np.cumsum(f) / SR) + lp(noise(d), 500) * 0.3
    return fade(x * (t / d) ** 2, 0.2, 0.02)
def crack():        # the sun splits: a dry snap, a low knock, a short shimmer
    t = tt(0.9)
    snap = hp(noise(0.9), 2500) * np.exp(-t / 0.008)
    knock = np.sin(2 * np.pi * 95 * t * (1 - 0.2 * t)) * np.exp(-t / 0.09)
    shim = bp(noise(0.9), 6000, 11000) * np.exp(-t / 0.25) * 0.2
    return snap * 0.9 + knock * 0.8 + shim
def split():        # wet segments pulled apart
    t = tt(0.5); x = bp(noise(0.5), 500, 3000) * np.exp(-t / 0.12)
    k = (rng.random(len(t)) > 0.996).astype(float); x += lp(np.convolve(k, np.sin(np.arange(200) / 9) * np.exp(-np.arange(200) / 50), 'same'), 2500) * 0.6
    return fade(x, 0.01, 0.1)
def cloth():
    t = tt(0.4); return fade(bp(noise(0.4), 600, 4000) * np.sin(np.pi * t / 0.4) ** 2 * 0.4)
def take():
    t = tt(0.12); return bp(noise(0.12), 800, 3000) * np.exp(-t / 0.02) * 0.6
def scribble(d):    # a felt pen, one stroke per drawing (12 per second)
    out = np.zeros(int(d * SR) + SR // 4); k = 0.0
    while k < d:
        L = 0.06 + 0.03 * rng.random(); x = bp(noise(L), 2000, 6000) * np.sin(np.pi * tt(L) / L) * (0.6 + 0.4 * rng.random())
        s = int(k * SR); out[s:s + len(x)] += x; k += 1 / 12
    return out * 0.5


FOLEY = {
    'squeak': (lambda e: squeak(), 0.5, 0.2), 'mist': (lambda e: mist(), 0.35, 0.3),
    'peel': (lambda e: peel(e['dur']), 0.55, 0.1), 'dive': (lambda e: dive(e['dur']), 0.5, 0.0),
    'chain': (lambda e: chain(e['dur']), 0.22, -0.1), 'bell': (lambda e: bell(), 0.45, 0.0),
    'pass': (lambda e: whoosh(0.7), 0.55, 0.0), 'brake': (lambda e: brake(), 0.3, -0.3),
    'foot': (lambda e: thump(1.0, 80), 0.45, -0.3), 'cicadas': (lambda e: cicadas(e['dur']), 0.10, 0.0),
    'hum': (lambda e: hum(e['dur']), 0.28, 0.0), 'crack': (lambda e: crack(), 0.8, 0.0),
    'split': (lambda e: split(), 0.55, 0.0), 'cloth': (lambda e: cloth(), 0.3, -0.2), 'take': (lambda e: take(), 0.5, 0.3),
    'pop': (lambda e: pop(), 0.35, 0.4), 'scribble': (lambda e: scribble(e['dur']), 0.18, 0.2),
}
for e in EVJ['ev']:
    fn, g, pan = FOLEY[e['type']]
    if e['type'] == 'pass':   # pans across the frame as the rider passes the lens
        x = fn(e); n = len(x); pn = np.linspace(-0.6, 0.6, n)
        s = int(e['t'] * SR); e2 = min(N, s + n)
        mix[s:e2, 0] += x[:e2 - s] * g * np.cos((pn[:e2 - s] + 1) * np.pi / 4) * 1.414
        mix[s:e2, 1] += x[:e2 - s] * g * np.sin((pn[:e2 - s] + 1) * np.pi / 4) * 1.414
        continue
    add(mix, fn(e), e['t'], g, pan)

# ---------- ambience beds (one per world; cut with the picture, never crossfaded across a cut) ----------
room = lp(brown(DUR), 400) * 0.05
wind = bp(noise(DUR), 200, 1400) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * tt(DUR)) ** 2) * 0.04
def bed(x, t0, t1, a=0.15, b=0.15):
    s, e = int(t0 * SR), int(t1 * SR); y = x[s:e].copy(); fade(y, a, b); mix[s:e, 0] += y; mix[s:e, 1] += y
bed(room, 0, 4.4, 0.05, 0.6); bed(wind, 4.0, 11.0, 0.8, 0.05); bed(wind * 0.5, 11.0, 15.4, 0.05, 0.3)
bed(room, 15.5, DUR, 0.3, 1.5)

# ---------- score ----------
mus = np.zeros((N, 2))
for k, g in (('kal', 0.95), ('ep', 0.9), ('bass', 0.72), ('drums', 0.8), ('pad', 1.0)):
    p = os.path.join(D, 'music', 'stems', f'{k}.wav')
    sr, x = wavfile.read(p); n = min(N, len(x)); mus[:n] += x[:n] * g
mix += mus * 0.55

# master headroom: soft limit per channel (loudness is set by mux.sh)
# bring the groove near −17 dBFS RMS, then a look-ahead limiter keeps transients (kick, crack, bell) under −2 dBFS,
# so mux.sh's loudnorm needs little gain and the true peak stays below −1.2 dB
s0, s1 = int(16 * SR), int(23 * SR); g = 10 ** ((-17 - 20 * np.log10(np.sqrt((mix[s0:s1] ** 2).mean()))) / 20)
mix *= g
for c in range(2): mix[:, c] = limit(limit(mix[:, c], 0.7, 0.008), 0.7, 0.002)
os.makedirs(os.path.join(D, 'out'), exist_ok=True)
wavfile.write(os.path.join(D, 'out', 'mix.wav'), SR, mix.astype(np.float32))
# report: loudness by section (RMS dBFS) so the silence is checked, not assumed
def rms(t0, t1): s, e = int(t0 * SR), int(t1 * SR); return 20 * np.log10(np.sqrt((mix[s:e] ** 2).mean()) + 1e-9)
print('mix.wav written; RMS dBFS  table %.1f | road %.1f | breath %.1f | groove %.1f | end %.1f' % (rms(0, 4), rms(7, 11), rms(12.3, 15.3), rms(16, 23), rms(25.5, 28)))
