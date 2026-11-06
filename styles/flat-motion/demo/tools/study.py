#!/usr/bin/env python3
"""Study a reference film: the numbers a flat-motion style is built from.

    .venv/bin/python styles/flat-motion/demo/tools/study.py ref.mov out_dir [--crop-bottom 0.14] [--k 12]

Writes to out_dir/:
  sheet_NN.jpg    timestamped contact sheets (2 frames/s)
  study.json      cuts, drawing rate, holds, palette, tempo, loudness per second
and prints a short report. What it measures (the method behind STYLE.md):
  - drawing rate: run lengths of identical consecutive frames at the source rate.
    Runs of 5 at 60 fps (or 2 at 24 fps) mean the film is drawn at 12 fps ("on twos"),
    camera included, when the runs hold through camera moves.
  - cuts vs. moves: frame-difference peaks. A lone spike is a cut; a run of high
    differences is a whip, a wipe or a dive (a transition made of motion).
  - palette: k-means over sampled pixels, by share of the frame.
  - tempo: autocorrelation of spectral flux; check the double and the half.
Needs ffmpeg, numpy and Pillow only. Reference films stay local: never commit them.
"""
import argparse, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out); s = j["streams"][0]
    n, d = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(n) / float(d), float(j["format"]["duration"])


def frames(path, w, h, fps=None):
    vf = f"scale={w}:{h}" + (f",fps={fps}" if fps else "")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def kmeans(X, k, it=25, seed=0):
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), k, replace=False)].astype(float)
    for _ in range(it):
        lab = ((X[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            if (lab == j).any():
                C[j] = X[lab == j].mean(0)
    return C, np.bincount(lab, minlength=k)


def audio(path, sr=22050, hop=512, win=2048):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    if len(x) < win * 4:
        return None
    n = len(x) // hop
    rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1))
    db = 20 * np.log10(rms + 1e-9)
    S = np.array([np.abs(np.fft.rfft(x[i:i + win] * np.hanning(win))) for i in range(0, len(x) - win, hop)])
    fl = np.maximum(np.diff(np.log1p(S), axis=0), 0).sum(1)
    fl = (fl - fl.mean()) / (fl.std() + 1e-9)
    ac = np.correlate(fl, fl, "full")[len(fl) - 1:]
    fr = sr / hop
    lags = np.arange(len(ac)) / fr
    m = (lags > 0.25) & (lags < 1.5)
    period = float(lags[m][np.argmax(ac[m])])
    per_s = [float(db[int(i * fr):int((i + 1) * fr)].mean()) for i in range(int(len(x) / sr))]
    on = np.where((fl[1:-1] > fl[:-2]) & (fl[1:-1] > fl[2:]) & (fl[1:-1] > 2.0))[0] / fr
    return {"beat_period_s": round(period, 3), "bpm_guess": round(60 / period, 1),
            "bpm_double": round(120 / period, 1), "db_per_second": [round(v, 1) for v in per_s],
            "strong_onsets": [round(float(t), 2) for t in on]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("out")
    ap.add_argument("--crop-bottom", type=float, default=0.0, help="share of the height to ignore (burned captions)")
    ap.add_argument("--k", type=int, default=12, help="palette size")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    W, H, fps, dur = probe(a.video)
    keep = 1 - a.crop_bottom

    # drawing rate and motion, at the source frame rate, small
    sw = 160; sh = max(2, int(round(sw * H / W / 2)) * 2)
    F = frames(a.video, sw, sh)[:, :int(sh * keep)].astype(np.int16)
    d = np.abs(np.diff(F, axis=0)).mean(axis=(1, 2, 3))
    still = d < 0.35
    runs, r = [], 1
    for s in still:
        if s: r += 1
        else: runs.append(r); r = 1
    runs.append(r)
    hist = {}
    for v in runs: hist[v] = hist.get(v, 0) + 1
    common = max(hist, key=lambda k: hist[k] * (k > 1))
    drawing_fps = fps / common if common > 1 else fps
    # cuts: isolated spikes; moves: sustained motion
    thr = max(6.0, np.percentile(d, 97))
    events, i = [], 0
    while i < len(d):
        if d[i] > thr:
            j = i
            while j + 1 < len(d) and (d[j + 1] > thr * 0.5 or still[j + 1]) and j - i < fps * 1.5: j += 1
            events.append({"t": round((i + 1) / fps, 2), "len_s": round((j - i + 1) / fps, 2),
                           "kind": "cut" if (j - i + 1) <= common + 1 else "move/transition"})
            i = j + 1
        else:
            i += 1
    motion = [round(float(d[k:k + int(fps / 2)].mean()), 1) for k in range(0, len(d), int(fps / 2))]

    # contact sheets, 2 per second, timestamped
    tw = 400; th = int(tw * H / W)
    S = frames(a.video, tw, th, fps=2)
    for k in range(0, len(S), 12):
        chunk = S[k:k + 12]; rows = (len(chunk) + 3) // 4
        sheet = Image.new("RGB", (4 * tw, rows * th), "black"); D = ImageDraw.Draw(sheet)
        for n, im in enumerate(chunk):
            x, y = (n % 4) * tw, (n // 4) * th
            sheet.paste(Image.fromarray(im), (x, y))
            D.rectangle([x, y, x + 56, y + 16], fill="black"); D.text((x + 4, y + 2), f"{(k + n) / 2:5.1f}s", fill="yellow")
        sheet.save(os.path.join(a.out, f"sheet_{k // 12:02d}.jpg"), quality=88)

    # palette
    X = np.concatenate([s[:int(th * keep)].reshape(-1, 3)[::17] for s in S]).astype(float)
    C, n = kmeans(X, a.k)
    order = np.argsort(-n)
    palette = [{"hex": "#%02X%02X%02X" % tuple(C[j].astype(int)), "share": round(100 * n[j] / n.sum(), 1)} for j in order]

    res = {"source": {"w": W, "h": H, "fps": round(fps, 3), "dur": round(dur, 2)},
           "drawing": {"hold_runs": dict(sorted(hist.items())), "drawing_fps": round(drawing_fps, 2),
                       "still_share": round(float(still.mean()), 2)},
           "events": events, "motion_per_half_second": motion, "palette": palette, "audio": audio(a.video)}
    json.dump(res, open(os.path.join(a.out, "study.json"), "w"), indent=1)
    print(f"{W}x{H} {fps:.2f} fps {dur:.1f} s")
    print(f"drawn at ~{drawing_fps:.1f} fps (most common hold {common} frames); still share {still.mean():.2f}")
    print("events:", ", ".join(f"{e['t']}s {e['kind']}" + (f" {e['len_s']}s" if e['kind'] != 'cut' else '') for e in events))
    print("palette:", " ".join(f"{p['hex']}:{p['share']}%" for p in palette))
    if res["audio"]:
        au = res["audio"]
        print(f"tempo: {au['bpm_guess']} BPM (or {au['bpm_double']}); dB/s: {' '.join('%.0f' % v for v in au['db_per_second'])}")
    print("contact sheets and study.json in", a.out)


if __name__ == "__main__":
    sys.exit(main())
