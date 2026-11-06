"""One Orange — original score, synthesized (no samples). Reads out/timeline.json, writes music/stems/*.wav.

Sound palette of the style (STYLE.md §7): soft rounded timbres — kalimba plucks, an FM electric piano,
a round bass with 2nd/3rd harmonics, brushed-soft drums (kick, rim, shaker). The music lives in the world:
it stops when the rider stops and comes back on the crack of the sun.
Run: .venv/bin/python styles/flat-motion/demo/music/score.py
"""
import json, os, sys
import numpy as np
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.dirname(HERE)
LIB = os.environ.get('LIB') or os.path.abspath(os.path.join(D, '..', '..', '..'))
sys.path.insert(0, os.path.join(LIB, 'core', 'audio'))
from sfx import SR, lp, hp, bp, noise  # noqa: E402

TL = json.load(open(os.path.join(D, 'out', 'timeline.json')))
BEAT, BAR, DUR, T = TL['BEAT'], TL['BAR'], TL['DUR'], TL['T']
N = int((DUR + 0.5) * SR)
rng = np.random.default_rng(3)
mtof = lambda m: 440.0 * 2 ** ((m - 69) / 12)


from sfx import t_ as tt  # same rounding as sfx.noise()


def place(buf, x, at, gain=1.0, pan=0.0):
    s = int(at * SR)
    if s >= len(buf): return
    e = min(len(buf), s + len(x)); l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[s:e, 0] += x[:e - s] * gain * l; buf[s:e, 1] += x[:e - s] * gain * r


# ---------- instruments ----------
def kalimba(m, v=1.0):
    f = mtof(m); d = 1.4; t = tt(d)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.55) + 0.22 * np.sin(2 * np.pi * f * 5.93 * t) * np.exp(-t / 0.045) \
        + 0.12 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t / 0.2)
    x[:int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    click = hp(noise(0.01), 3000) * np.exp(-tt(0.01) / 0.002) * 0.15
    x[:len(click)] += click
    return x * v


def epiano(m, d, v=1.0, idx=2.2, att=0.005):
    f = mtof(m); t = tt(d + 0.8)
    I = idx * np.exp(-t / 0.35) + 0.35
    x = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * t)) * np.exp(-t / 1.6)
    x += 0.08 * np.sin(2 * np.pi * f * 7.0 * t) * np.exp(-t / 0.06)          # tine bell
    a = np.minimum(1, t / att); rel = np.clip((d + 0.8 - t) / 0.8, 0, 1) ** 2
    return x * a * np.where(t < d, 1, rel) * v


def bass(m, d, v=1.0):
    f = mtof(m); t = tt(d + 0.12)
    x = np.sin(2 * np.pi * f * t) + 0.32 * np.sin(4 * np.pi * f * t) + 0.16 * np.sin(6 * np.pi * f * t)
    env = np.minimum(1, t / 0.006) * np.exp(-t / 0.9) * np.clip((d + 0.12 - t) / 0.12, 0, 1)
    return lp(x * env, 900) * v


def kick(v=1.0):
    t = tt(0.4); f = 48 + 75 * np.exp(-t / 0.04)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.13)
    x[:200] += hp(noise(200 / SR), 2000)[:200] * np.exp(-np.arange(200) / 40) * 0.3
    return x * v


def rim(v=1.0):
    t = tt(0.12)
    return (bp(noise(0.12), 1500, 4200) * np.exp(-t / 0.012) * 0.8 + np.sin(2 * np.pi * 1750 * t) * np.exp(-t / 0.018) * 0.4) * v


def shaker(v=1.0):
    t = tt(0.09)
    return hp(noise(0.09), 6000) * np.minimum(1, t / 0.006) * np.exp(-t / 0.035) * v


# ---------- harmony ----------
CH = [  # (bass root, e-piano voicing, kalimba riff)
    (38, [62, 66, 69, 73], [74, 78, 81, 78, 85, 81, 78, 76]),   # Dmaj7
    (35, [59, 62, 66, 69], [71, 74, 78, 74, 81, 78, 74, 73]),   # Bm7
    (31, [59, 62, 66, 67], [71, 74, 79, 74, 78, 79, 74, 71]),   # Gmaj7
    (33, [61, 64, 67, 69], [73, 76, 79, 76, 81, 79, 76, 73]),   # A6/7
]
stems = {k: np.zeros((N, 2)) for k in ('kal', 'ep', 'bass', 'drums', 'pad')}


def groove(t0, t1, kal=True, ep=False, bas=False, kik=False, rm=False, shk=True, kal_v=0.5):
    b = int(np.floor(t0 / BAR + 1e-9))
    while b * BAR < t1 - 1e-6:
        root, voic, riff = CH[b % 4]; s = b * BAR
        for i, m in enumerate(riff):
            at = s + i * BEAT / 2
            if t0 <= at < t1 and kal: place(stems['kal'], kalimba(m, kal_v * (1.0 if i % 2 == 0 else 0.72)), at, pan=0.35 if i % 2 else -0.2)
        for k in range(16):
            at = s + k * BEAT / 4
            if t0 <= at < t1 and shk: place(stems['drums'], shaker(0.22 if k % 2 else 0.32), at, pan=0.5)
        if bas:
            for (bt, dd, mm) in ((0, 0.9, root), (1.5, 0.25, root + 12), (2, 0.5, root), (3.5, 0.3, root + 7)):
                at = s + bt * BEAT
                if t0 <= at < t1: place(stems['bass'], bass(mm, dd, 0.55), at)
        if kik:
            for bt in (0, 2, 2.75):
                at = s + bt * BEAT
                if t0 <= at < t1: place(stems['drums'], kick(0.8 if bt != 2.75 else 0.45), at)
        if rm:
            for bt in (1, 3):
                at = s + bt * BEAT
                if t0 <= at < t1: place(stems['drums'], rim(0.35), at, pan=-0.15)
        if ep:
            for (bt, dd, vv) in ((0, 1.3, 0.16), (3.5, 0.35, 0.11)):
                at = s + bt * BEAT
                if t0 <= at < t1:
                    for j, m in enumerate(voic): place(stems['ep'], epiano(m, dd, vv), at + j * 0.008, pan=-0.25 + j * 0.15)
        b += 1


q0, q1 = T['quiet0'], T['quiet1']
groove(0.0, 4.0, kal=True)                                                    # A: kalimba + shaker at the table
groove(4.0, 7.0, kal=True, bas=True, kik=True)                                # B1: the dive opens the band
groove(7.0, q0, kal=True, bas=True, kik=True, rm=True, ep=True)               # B2: the road
# C: the breath — one soft held chord under the cicadas, nothing on the grid
for j, m in enumerate([55, 59, 62, 66, 69]): place(stems['pad'], epiano(m, 3.0, 0.07, idx=0.6, att=0.4), q0 + 0.05 + j * 0.03, pan=-0.3 + j * 0.15)
# D: the crack is the pickup, the groove returns on the next bar line
place(stems['drums'], kick(1.0), T['crack']); place(stems['bass'], bass(38, 0.4, 0.6), T['crack'])
for j, m in enumerate([62, 66, 69, 74]): place(stems['ep'], epiano(m, 0.5, 0.14), T['crack'] + j * 0.01)
place(stems['kal'], kalimba(86, 0.6), T['crack'])
groove(16.0, 23.5, kal=True, bas=True, kik=True, rm=True, ep=True)
groove(23.5, T['chord'], kal=True, bas=True, ep=True, kik=False, rm=True)     # E: lighter under the crane-up
# the last chord rings out
c = T['chord']; place(stems['bass'], bass(38, 3.5, 0.55), c)
for j, m in enumerate([62, 66, 69, 73, 76]): place(stems['ep'], epiano(m, 3.4, 0.15), c + j * 0.012, pan=-0.3 + j * 0.15)
for j, m in enumerate([74, 78, 81, 85, 86]): place(stems['kal'], kalimba(m, 0.42), c + 0.25 * j, pan=-0.3 + j * 0.15)

os.makedirs(os.path.join(HERE, 'stems'), exist_ok=True)
for k, x in stems.items():
    wavfile.write(os.path.join(HERE, 'stems', f'{k}.wav'), SR, x.astype(np.float32))
print('stems:', ', '.join(f"{k} peak {np.abs(x).max():.2f}" for k, x in stems.items()))
