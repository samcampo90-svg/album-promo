"""Track analysis: tempo, bars, sections, and the best short-form moments.

A "moment" is a window that starts on a bar line and is a good candidate for a
short video: the chorus, a drop, a build into the chorus, a quiet emotional part,
or the intro.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import librosa
import numpy as np

SR = 22050
HOP = 512
KEYS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


@dataclass
class Moment:
    kind: str
    start: float
    end: float
    score: float
    note: str = ""


def _key(chroma):
    prof = chroma.mean(axis=1)
    best = (-1e9, "")
    for i in range(12):
        for name, p in (("major", MAJOR), ("minor", MINOR)):
            r = np.corrcoef(np.roll(p, i), prof)[0, 1]
            if r > best[0]:
                best = (r, f"{KEYS[i]} {name}")
    return best[1]


def _smooth(x, n):
    if n <= 1:
        return x
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), k, mode="valid")


def analyze(path: Path) -> dict:
    y, _ = librosa.load(str(path), sr=SR, mono=True)
    dur = len(y) / SR
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    db = 20 * np.log10(rms + 1e-6)
    times = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=HOP)
    onset = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=SR, hop_length=HOP, units="frames")
    tempo = float(np.atleast_1d(tempo)[0])
    if len(beats) < 16:
        beats = librosa.time_to_frames(np.arange(0, dur, 60 / max(tempo, 60)), sr=SR, hop_length=HOP)
    # pick downbeat phase (of 4): bar lines tend to carry low-end hits AND chord changes
    S = np.abs(librosa.stft(y, hop_length=HOP, n_fft=2048))
    low = S[: int(150 / (SR / 2048)), :].sum(axis=0)
    low_on = np.maximum(0, np.diff(low, prepend=low[0]))
    chroma = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP)
    Cb = librosa.util.sync(chroma, beats, aggregate=np.median)[:, 1:]  # column j = beat j..j+1
    hchange = np.r_[0, np.linalg.norm(np.diff(librosa.util.normalize(Cb, axis=0), axis=1), axis=0)]
    win = np.array([low_on[max(0, b - 2): b + 3].max() for b in beats])
    lo = win / (win.mean() + 1e-9)
    hc = hchange[: len(beats)] / (hchange.mean() + 1e-9)
    hc = np.pad(hc, (0, len(beats) - len(hc)))
    # low-end hits separate {1,3} from {2,4}; harmonic change picks 1 over 3
    pair = int(np.argmax([lo[p::4].mean() + lo[p + 2::4].mean() for p in (0, 1)]))
    cands = (pair, pair + 2)
    phase = max(cands, key=lambda p: hc[p::4].mean() + 0.3 * lo[p::4].mean())
    bars = beats[phase::4]
    bar_t = librosa.frames_to_time(bars, sr=SR, hop_length=HOP)
    beat_t = librosa.frames_to_time(beats, sr=SR, hop_length=HOP)

    # beat-synchronous features for repetition / sectioning
    mfcc = librosa.feature.mfcc(y=y, sr=SR, hop_length=HOP, n_mfcc=13)
    C = librosa.util.sync(chroma, beats, aggregate=np.median)
    M = librosa.util.sync(mfcc, beats)
    E = librosa.util.sync(db[None, :], beats)[0]
    feat = np.vstack([librosa.util.normalize(C, axis=0), librosa.util.normalize(M, axis=0) * 0.5])
    R = librosa.segment.recurrence_matrix(feat, width=8, mode="affinity", sym=True)
    rep = _smooth(R.sum(axis=1), 8)
    rep = (rep - rep.min()) / (np.ptp(rep) + 1e-9)
    en = (E - np.percentile(E, 5)) / (np.percentile(E, 98) - np.percentile(E, 5) + 1e-9)
    en = np.clip(_smooth(en, 4), 0, 1)
    # sync() returns one column per segment: [0, b0), [b0, b1), ... [bN, end)
    bt = np.concatenate([[0.0], beat_t])[: len(en)]
    n = min(len(bt), len(en), len(rep))
    bt, en, rep = bt[:n], en[:n], rep[:n]

    # sections: novelty at bar lines (feature + energy change between 2-bar blocks)
    bar_idx = np.searchsorted(bt, bar_t)
    nb = len(bar_idx)
    nov = np.zeros(nb)
    for i in range(2, nb - 2):
        a0, a1, b1 = bar_idx[i - 2], bar_idx[i], bar_idx[min(i + 2, nb - 1)]
        if a1 <= a0 or b1 <= a1:
            continue
        fa, fb = feat[:, a0:a1].mean(axis=1), feat[:, a1:b1].mean(axis=1)
        nov[i] = np.linalg.norm(fa - fb) + 2.0 * abs(en[a1:b1].mean() - en[a0:a1].mean())
    thr = nov.mean() + 0.5 * nov.std()
    cuts = [0]
    for i in np.argsort(-nov):
        if nov[i] < thr:
            break
        if all(abs(i - c) >= 4 for c in cuts):
            cuts.append(int(i))
    cuts = sorted(cuts)
    edges = [0.0] + [float(bar_t[c]) for c in cuts if c > 0] + [dur]
    if len(bar_t) and bar_t[0] > 4 and edges[1] != float(bar_t[0]):
        edges.insert(1, float(bar_t[0]))
    edges = sorted(set(edges))
    sections = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (bt >= a) & (bt < b)
        if not m.any():
            continue
        sections.append({"start": round(a, 3), "end": round(b, 3),
                         "energy": float(en[m].mean()), "repetition": float(rep[m].mean())})
    es = [x["energy"] for x in sections]
    rs = [x["repetition"] for x in sections]
    for s_ in sections:
        hi_e = s_["energy"] >= np.percentile(es, 60)
        hi_r = s_["repetition"] >= np.percentile(rs, 40)
        s_["label"] = "chorus" if (hi_e and hi_r) else ("high" if hi_e else ("low" if s_["energy"] < 0.35 else "mid"))

    def at(arr, t):
        i = np.searchsorted(bt, t)
        return arr[min(max(i, 0), len(arr) - 1)]

    def window_stats(t0, t1):
        m = (bt >= t0) & (bt < t1)
        if not m.any():
            return 0, 0
        return float(en[m].mean()), float(rep[m].mean())

    def snap_end(t0, L):
        cand = bar_t[bar_t > t0 + L * 0.8]
        if len(cand) == 0:
            return min(dur, t0 + L)
        e = cand[np.argmin(np.abs(cand - (t0 + L)))]
        return float(min(e, dur))

    moments = []
    lengths = [9, 15, 22, 30]
    # 1) chorus / hook windows: start on bars, score energy + repetition
    for L in lengths:
        for t0 in bar_t:
            if t0 + L > dur - 1:
                break
            t1 = snap_end(t0, L)
            e, r = window_stats(t0, t1)
            entry = max(0.0, at(en, t0 + 0.5) - at(en, t0 - 2.0))
            score = 0.55 * e + 0.35 * r + 0.25 * entry
            moments.append(Moment("hook", float(t0), t1, score, f"{L}s"))
    # 2) drops / builds: biggest energy rises; start ~2 bars before the rise
    rise = np.array([at(en, t + 1.0) - at(en, t - 3.0) for t in bar_t])
    bar_len = float(np.median(np.diff(bar_t))) if len(bar_t) > 2 else 2.5
    for idx in np.argsort(-rise)[:6]:
        t_rise = bar_t[idx]
        for lead_bars in (2, 3):
            t0 = max(0.0, t_rise - lead_bars * bar_len)
            t0 = float(bar_t[np.argmin(np.abs(bar_t - t0))])
            t1 = snap_end(t0, 15)
            moments.append(Moment("drop", t0, t1, float(rise[idx]) + 0.3, f"rise at {t_rise:.1f}s"))
    # 3) quiet/emotional: lowest-energy sustained section that isn't silence
    for s in sections:
        if s["label"] == "low" and s["end"] - s["start"] > 8 and s["start"] > 5:
            t0 = float(bar_t[np.argmin(np.abs(bar_t - s["start"]))])
            moments.append(Moment("quiet", t0, snap_end(t0, 15), 0.4 + 0.3 * (1 - s["energy"]), "quiet section"))
    # 4) intro
    first = 0.0 if (len(bar_t) == 0 or bar_t[0] > 4) else float(bar_t[0])
    moments.append(Moment("intro", first, snap_end(first, 15), 0.3, "opening"))

    # non-max suppression per kind and per length bucket
    def nms(ms, keep, max_overlap=0.35):
        out = []
        for m in sorted(ms, key=lambda m: -m.score):
            ok = True
            for o in out:
                ov = max(0, min(m.end, o.end) - max(m.start, o.start))
                if ov / min(m.end - m.start, o.end - o.start) > max_overlap:
                    ok = False
                    break
            if ok:
                out.append(m)
            if len(out) >= keep:
                break
        return out

    picked = []
    for L in lengths:
        picked += nms([m for m in moments if m.kind == "hook" and m.note == f"{L}s"], 4)
    picked += nms([m for m in moments if m.kind == "drop"], 3)
    picked += nms([m for m in moments if m.kind == "quiet"], 2)
    picked += [m for m in moments if m.kind == "intro"]
    picked.sort(key=lambda m: (m.start, m.end))
    for i, m in enumerate(picked):
        m.score = round(m.score, 3)

    # overview curves for waveform visuals (400 points)
    pts = 400
    idx = np.linspace(0, len(rms) - 1, pts).astype(int)
    overview = (rms[idx] / (rms.max() + 1e-9)).round(4).tolist()

    return {
        "file": str(path), "title": Path(path).stem, "duration": round(dur, 3),
        "tempo": round(tempo, 2), "key": _key(chroma),
        "beats": [round(float(t), 3) for t in beat_t], "bars": [round(float(t), 3) for t in bar_t],
        "sections": sections, "moments": [asdict(m) for m in picked], "overview": overview,
    }


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        a = analyze(Path(p))
        print(json.dumps({k: a[k] for k in ("title", "duration", "tempo", "key")}))
        for s in a["sections"]:
            print(f"  section {s['start']:6.1f}-{s['end']:6.1f} {s['label']:7s} e={s['energy']:.2f} r={s['repetition']:.2f}")
        for m in a["moments"]:
            print(f"  moment {m['kind']:6s} {m['start']:6.1f}-{m['end']:6.1f} score={m['score']:.2f} {m['note']}")
