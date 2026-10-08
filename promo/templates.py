"""Video templates. Each template is a function render(job, feats) that yields BGR
frames. Static layers are built once; per-frame work is kept small so a 15 s
vertical video renders in well under a minute on two CPU cores."""
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from . import core as C
from .core import W, H, FPS


@dataclass
class Job:
    out: Path
    audio: Path
    t0: float
    t1: float
    analysis: dict
    cover: np.ndarray
    pal: dict
    template: str
    hook: str = ""
    title: str = ""
    artist: str = ""
    font_set: str = "native"
    hook_style: str = "line_boxes"
    style: dict = field(default_factory=dict)
    photos: list = field(default_factory=list)   # list of BGR images
    clips: list = field(default_factory=list)    # list of video paths
    lyrics: list = field(default_factory=list)   # [(abs_time, line), ...] synced, or [] / [lines] unsynced
    seed: int = 0


# ---------------------------------------------------------------- shared overlays
HOOK_Y = 215          # top of hook text block (below platform top bar)
HOOK_MAX_H = 300
LABEL_Y = 1440        # artist - title line, above caption area
SAFE_W = 880


def hook_layer(job):
    if not job.hook:
        return None
    head, _, upper = C.FONT_SETS[job.font_set]
    s = job.hook_style
    if s == "line_boxes":
        return C.text_layer(job.hook, "Inter_800ExtraBold.ttf", SAFE_W, HOOK_MAX_H, 64, 34, color=(20, 20, 20),
                            box=(255, 255, 255), box_pad=(22, 14), box_radius=14, line_boxes=True, spacing=1.08)
    if s == "box_black":
        return C.text_layer(job.hook, "Inter_800ExtraBold.ttf", SAFE_W, HOOK_MAX_H, 62, 34, color=(255, 255, 255),
                            box=(18, 18, 18), box_pad=(30, 22), box_radius=22)
    if s == "stroke":
        return C.text_layer(job.hook, head, SAFE_W, HOOK_MAX_H, 84, 40, color=(255, 255, 255), stroke=6,
                            stroke_color=(0, 0, 0), upper=upper)
    if s == "accent":
        return C.text_layer(job.hook, head, SAFE_W, HOOK_MAX_H, 96, 40, color=job.pal["vivid"], shadow=14, upper=upper)
    return C.text_layer(job.hook, head, SAFE_W, HOOK_MAX_H, 88, 40, color=(255, 255, 255), shadow=16, upper=upper)


def label_layer(job, y_hint=None):
    if not (job.title or job.artist):
        return None
    txt = f"{job.artist}  —  {job.title}" if job.artist and job.title else (job.title or job.artist)
    return C.text_layer(txt, "Inter_600SemiBold.ttf", SAFE_W, 140, 44, 28, color=(255, 255, 255), shadow=10)


def overlays(job):
    hk, lb = hook_layer(job), label_layer(job)

    def apply(frame, i, label_y=LABEL_Y, hook=True):
        if hook and hk is not None:
            C.paste(frame, hk, (W - hk.shape[1]) // 2, HOOK_Y)
        if lb is not None and label_y is not None:
            C.paste(frame, lb, (W - lb.shape[1]) // 2, label_y)
        return frame
    return apply


def _bg(job, dim=0.5):
    return C.blurred_bg(job.cover, dim=dim)


# ---------------------------------------------------------------- 1. vinyl
def vinyl(job, f):
    rng = np.random.default_rng(job.seed)
    big = _bg(job, 0.45)
    D = 820
    disc = np.zeros((D, D, 4), np.uint8)
    cv2.circle(disc, (D // 2, D // 2), D // 2 - 2, (14, 14, 16, 255), -1, cv2.LINE_AA)
    for r in range(D // 2 - 12, 190, -6):
        g = 28 + int(10 * np.sin(r * 0.7))
        cv2.circle(disc, (D // 2, D // 2), r, (g, g, g + 2, 255), 1, cv2.LINE_AA)
    lab = 330
    label = C.cover_fit(job.cover, lab, lab)
    lab_rgba = C.bgr_to_rgba(label, C.circle_mask(lab))
    C.blend_rgba(disc, lab_rgba, (D - lab) // 2, (D - lab) // 2)
    cv2.circle(disc, (D // 2, D // 2), 12, (10, 10, 10, 255), -1, cv2.LINE_AA)
    shadow = C.with_shadow(np.dstack([np.zeros((D, D, 3), np.uint8), disc[..., 3]]), blur=50, offset=(0, 30), alpha=0.7)
    # static sheen (doesn't rotate) for a vinyl look
    sheen = np.zeros((D, D, 4), np.uint8)
    yy, xx = np.mgrid[0:D, 0:D] - D / 2
    ang = np.arctan2(yy, xx)
    rr = np.sqrt(xx ** 2 + yy ** 2)
    a = (np.cos(2 * (ang - 0.8)) ** 8) * ((rr > 200) & (rr < D / 2 - 6)) * 38
    sheen[..., :3] = 255
    sheen[..., 3] = a.astype(np.uint8)
    cx, cy = W // 2, 1010
    speed = job.style.get("rpm_deg", 48.0) / FPS * (1 if rng.random() < 0.8 else -1)
    ov = overlays(job)
    for i in range(f.n):
        frame = C.crop_drift(big, i, f.n, zoom=0.06)
        frame = C.gain(frame, 0.9 + 0.2 * f.bass[i])
        C.paste(frame, shadow, cx - shadow.shape[1] // 2, cy - shadow.shape[0] // 2)
        M = cv2.getRotationMatrix2D((D / 2, D / 2), -speed * i, 1.0)
        rot = cv2.warpAffine(disc, M, (D, D), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
        C.paste(frame, rot, cx - D // 2, cy - D // 2)
        C.paste(frame, sheen, cx - D // 2, cy - D // 2)
        yield ov(frame, i, LABEL_Y + 20)


# ---------------------------------------------------------------- 2. bars
def bars(job, f):
    big = _bg(job, 0.5)
    S = 720
    cov = C.bgr_to_rgba(C.cover_fit(job.cover, S, S), C.rounded_mask(S, 28))
    cov = C.with_shadow(cov, blur=50, offset=(0, 30), alpha=0.65)
    col = job.pal["vivid"]
    nb = 34
    bw = 18
    gap = (SAFE_W - nb * bw) / (nb - 1)
    ov = overlays(job)
    base_y = 1355
    for i in range(f.n):
        frame = C.crop_drift(big, i, f.n, zoom=0.05)
        z = 1 + 0.025 * f.beat[i]
        c = cov if z < 1.002 else cv2.resize(cov, None, fx=z, fy=z, interpolation=cv2.INTER_LINEAR)
        C.paste(frame, c, W // 2 - c.shape[1] // 2, 905 - c.shape[0] // 2)
        vals = np.interp(np.linspace(0, f.bands.shape[1] - 1, nb), np.arange(f.bands.shape[1]), f.bands[i])
        x = (W - SAFE_W) / 2 + bw / 2
        for v in vals:
            hgt = int(8 + 150 * v ** 1.3)
            cv2.line(frame, (int(x), base_y - hgt // 2), (int(x), base_y + hgt // 2), col, bw, cv2.LINE_AA)
            x += bw + gap
        yield ov(frame, i, LABEL_Y + 45)


# ---------------------------------------------------------------- 3. ring
def ring(job, f):
    big = _bg(job, 0.4)
    S = 560
    cov = C.bgr_to_rgba(C.cover_fit(job.cover, S, S), C.circle_mask(S))
    col = job.pal["vivid"]
    nseg = 120
    ang = np.linspace(0, 2 * np.pi, nseg, endpoint=False) - np.pi / 2
    cx, cy = W // 2, 1000
    ov = overlays(job)
    r0 = S // 2 + 18
    for i in range(f.n):
        frame = C.crop_drift(big, i, f.n, zoom=0.08)
        b = f.bands[i]
        half = np.interp(np.linspace(0, len(b) - 1, nseg // 2), np.arange(len(b)), b)
        vals = np.concatenate([half, half[::-1]])
        glow = np.zeros((700, 700, 3), np.uint8)
        for a, v in zip(ang, vals):
            L = 10 + 125 * v ** 1.4
            x0, y0 = cx + np.cos(a) * r0, cy + np.sin(a) * r0
            x1, y1 = cx + np.cos(a) * (r0 + L), cy + np.sin(a) * (r0 + L)
            cv2.line(frame, (int(x0), int(y0)), (int(x1), int(y1)), col, 7, cv2.LINE_AA)
            gx0, gy0 = (x0 - cx) / 2 + 350, (y0 - cy) / 2 + 350
            gx1, gy1 = (x1 - cx) / 2 + 350, (y1 - cy) / 2 + 350
            cv2.line(glow, (int(gx0), int(gy0)), (int(gx1), int(gy1)), col, 8, cv2.LINE_AA)
        glow = cv2.GaussianBlur(glow, (0, 0), 9)
        glow = cv2.resize(glow, (1400, 1400), interpolation=cv2.INTER_LINEAR)
        roi = frame[cy - 700:cy + 700, cx - 700 + 160:cx + 700 - 160]
        g = glow[:, 160:1240]
        cv2.add(roi, (g * (0.6 + 0.6 * f.rms[i])).astype(np.uint8), roi)
        z = 1 + 0.03 * f.beat[i]
        M = cv2.getRotationMatrix2D((S / 2, S / 2), -i * 0.6, z)
        rc = cv2.warpAffine(cov, M, (S, S), borderValue=(0, 0, 0, 0))
        C.paste(frame, rc, cx - S // 2, cy - S // 2)
        yield ov(frame, i, LABEL_Y + 40)


# ---------------------------------------------------------------- 4. pulse
def pulse(job, f):
    full = job.style.get("pulse_mode", "square") == "full"
    big = C.cover_fit(job.cover, int(W * 1.1), int(H * 1.1)) if full else _bg(job, 0.55)
    S = 860
    sq = C.with_shadow(C.bgr_to_rgba(C.cover_fit(job.cover, S, S), C.rounded_mask(S, 10)), 40, (0, 20), 0.6)
    ov = overlays(job)
    hard = job.style.get("intensity", 1.0)
    for i in range(f.n):
        frame = C.crop_drift(big, i, f.n, zoom=0.04)
        if not full:
            C.paste(frame, sq, (W - sq.shape[1]) // 2, 1010 - sq.shape[0] // 2)
        z = 1 + 0.06 * f.bar[i] * hard + 0.025 * f.beat[i] * hard + 0.05 * i / f.n
        frame = C.zoom_frame(frame, z)
        if f.bar[i] > 0.75:
            frame = C.rgb_split(frame, 14 * hard * (f.bar[i] - 0.75) * 4)
        frame = C.gain(frame, 0.92 + 0.15 * f.beat[i])
        frame = C.grain(frame, i, 4)
        yield ov(frame, i, None)


# ---------------------------------------------------------------- 5. lyric
def _lyric_bg_source(job):
    if job.style.get("lyric_bg") == "photo" and job.photos:
        img = job.photos[job.seed % len(job.photos)]
        return C.blurred_bg(img, blur=14, dim=0.45, sat=0.9)
    return _bg(job, 0.38)


def lyric(job, f):
    big = _lyric_bg_source(job)
    head, body, upper = C.FONT_SETS[job.font_set]
    synced = bool(job.lyrics) and isinstance(job.lyrics[0], (tuple, list))
    if synced:
        lines = [(t - job.t0, l) for t, l in job.lyrics if job.t0 - 8 <= t < job.t1]
    else:
        txt = job.lyrics[:2] if job.lyrics else [job.title]
        lines = [(0.25, "\n".join(txt))]
    layers = [C.text_layer(l, head, SAFE_W, 700, 104, 44, color=(255, 255, 255), shadow=18, upper=upper)
              for _, l in lines]
    starts = [t for t, _ in lines]
    ov = overlays(job)
    small = C.bgr_to_rgba(C.cover_fit(job.cover, 150, 150), C.rounded_mask(150, 14))
    for i in range(f.n):
        t = i / FPS
        frame = C.crop_drift(big, i, f.n, zoom=0.07)
        k = int(np.searchsorted(starts, t, side="right")) - 1
        if k >= 0:
            age = t - starts[k]
            a = C.ease(age / 0.25)
            ly = layers[k]
            y = 960 - ly.shape[0] // 2 + int(30 * (1 - a))
            if k > 0 and synced:
                prev = layers[k - 1]
                C.paste(frame, prev, (W - prev.shape[1]) // 2, y - prev.shape[0] - 30 - int(30 * a), 0.32 * (1 - 0.3 * a))
            C.paste(frame, ly, (W - ly.shape[1]) // 2, y, float(a))
        C.paste(frame, small, (W - 150) // 2, 1350)
        yield ov(frame, i, LABEL_Y + 90, hook=bool(job.hook) and not synced)


# ---------------------------------------------------------------- 6. photo_beats
def photo_beats(job, f):
    pics = job.photos or [job.cover]
    rng = np.random.default_rng(job.seed)
    order = list(rng.permutation(len(pics)))
    fitted = [C.cover_fit(p, int(W * 1.12), int(H * 1.12)) for p in pics]
    grade = job.style.get("grade", 0.15)
    tint = np.array(job.pal["accent"], np.float32)[None, None, :]
    ov = overlays(job)
    every = 2 if job.analysis.get("tempo", 100) > 128 else 1
    for i in range(f.n):
        seg = int(f.bar_index[i]) // every
        img = fitted[order[seg % len(order)]]
        # frames since this segment began
        j = i
        while j > 0 and int(f.bar_index[j - 1]) // every == seg:
            j -= 1
        frame = C.crop_drift(img, i - j, int(4 * FPS), zoom=0.12)
        frame = (frame.astype(np.float32) * (1 - grade) + tint * grade).clip(0, 255).astype(np.uint8)
        flash = max(0.0, 1 - (i - j) / 4) if seg > 0 else 0.0
        if flash > 0:
            frame = cv2.addWeighted(frame, 1 - 0.5 * flash, np.full_like(frame, 255), 0.5 * flash, 0)
        frame = C.grain(frame, i, 3)
        yield ov(frame, i, LABEL_Y + 60)


# ---------------------------------------------------------------- 7. clip_cut
def _lut(pal, warmth=0.0, lift=18, contrast=1.08):
    x = np.arange(256, dtype=np.float32)
    base = np.clip((x - 128) * contrast + 128, 0, 255)
    base = lift + base * (255 - lift) / 255
    luts = []
    acc = np.array(pal["accent"], np.float32) / 255
    for ch in range(3):
        l = base * (1 - 0.12) + base * acc[ch] * 0.12 * 2
        luts.append(np.clip(l, 0, 255).astype(np.uint8))
    return luts


class _ClipReader:
    def __init__(self, path):
        self.cap = cv2.VideoCapture(str(path))
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

    def seek(self, frame_idx):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(self.n - 2, frame_idx)))

    def read(self):
        ok, fr = self.cap.read()
        if not ok:
            self.seek(0)
            ok, fr = self.cap.read()
        return fr


def clip_cut(job, f):
    if not job.clips:
        yield from photo_beats(job, f)
        return
    rng = np.random.default_rng(job.seed)
    readers = [_ClipReader(p) for p in job.clips]
    luts = _lut(job.pal)
    single = job.style.get("single", False)
    every = 2 if (job.analysis.get("tempo", 100) > 128 or single) else 1
    ov = overlays(job)
    cur, seg_prev, step = None, -1, 1.0
    for i in range(f.n):
        seg = 0 if single else int(f.bar_index[i]) // every
        if seg != seg_prev:
            cur = readers[rng.integers(len(readers))] if not single else readers[job.seed % len(readers)]
            cur.seek(int(rng.uniform(0, max(1, cur.n - 4 * cur.fps))))
            step = cur.fps / FPS
            acc = 0.0
            seg_prev = seg
            fr = cur.read()
        acc += step
        while acc >= 1:
            fr = cur.read()
            acc -= 1
        frame = C.cover_fit(fr, W, H)
        frame = cv2.merge([cv2.LUT(frame[..., c], luts[c]) for c in range(3)])
        frame = C.grain(frame, i, 4)
        yield ov(frame, i, LABEL_Y + 60)


# ---------------------------------------------------------------- 8. waveform player
def _fmt(t):
    t = max(0, int(t))
    return f"{t // 60}:{t % 60:02d}"


def waveform(job, f):
    big = _bg(job, 0.32)
    S = 640
    cov = C.with_shadow(C.bgr_to_rgba(C.cover_fit(job.cover, S, S), C.rounded_mask(S, 24)), 46, (0, 26), 0.6)
    ov = overlays(job)
    over = np.array(job.analysis["overview"])
    over = over / (over.max() + 1e-9)
    nbar = 70
    vals = np.interp(np.linspace(0, len(over) - 1, nbar), np.arange(len(over)), over)
    dur = job.analysis["duration"]
    x0, x1, y = (W - SAFE_W) // 2, (W + SAFE_W) // 2, 1405
    col = job.pal["vivid"]
    tcache = {}
    ttl = C.text_layer(job.title or "", "Inter_800ExtraBold.ttf", SAFE_W, 90, 58, 30, align="left")
    art = C.text_layer(job.artist or "", "Inter_600SemiBold.ttf", SAFE_W, 60, 40, 24, color=(210, 210, 210), align="left")
    for i in range(f.n):
        frame = C.crop_drift(big, i, f.n, zoom=0.04)
        C.paste(frame, cov, W // 2 - cov.shape[1] // 2, 890 - cov.shape[0] // 2)
        C.paste(frame, ttl, x0 - 8, 1240)
        C.paste(frame, art, x0 - 8, 1308)
        tcur = job.t0 + i / FPS
        prog = tcur / dur
        bw = SAFE_W / nbar
        for k, v in enumerate(vals):
            xx = int(x0 + k * bw + bw / 2)
            hh = int(6 + 70 * v)
            c = col if (k + 0.5) / nbar <= prog else (110, 110, 110)
            cv2.line(frame, (xx, y - hh // 2), (xx, y + hh // 2), c, max(3, int(bw * 0.55)), cv2.LINE_AA)
        px = int(x0 + prog * SAFE_W)
        cv2.circle(frame, (px, y), 13, (255, 255, 255), -1, cv2.LINE_AA)
        key = (int(tcur), int(dur))
        if key not in tcache:
            tcache[key] = (C.text_layer(_fmt(tcur), "SpaceMono_400Regular.ttf", 200, 50, 30, 20, color=(220, 220, 220)),
                           C.text_layer(_fmt(dur), "SpaceMono_400Regular.ttf", 200, 50, 30, 20, color=(160, 160, 160)))
        a, b = tcache[key]
        C.paste(frame, a, x0 - 8, y + 50)
        C.paste(frame, b, x1 - b.shape[1] + 8, y + 50)
        yield ov(frame, i, None)


# ---------------------------------------------------------------- 9. countdown
def countdown(job, f):
    big = _bg(job, 0.42)
    head, body, upper = C.FONT_SETS[job.font_set]
    days = job.style.get("days", 7)
    when = job.style.get("when", "")
    num = C.text_layer(str(days), head, 900, 520, 460, 120, color=(255, 255, 255), shadow=20)
    unit = C.text_layer("DAY" if days == 1 else "DAYS", head, 900, 140, 120, 40, color=job.pal["vivid"], shadow=10, upper=True)
    sub = C.text_layer(when, "Inter_800ExtraBold.ttf", SAFE_W, 120, 54, 28, color=(255, 255, 255), shadow=10) if when else None
    S = 300
    cov = C.with_shadow(C.bgr_to_rgba(C.cover_fit(job.cover, S, S), C.rounded_mask(S, 18)), 30, (0, 16), 0.6)
    ov = overlays(job)
    for i in range(f.n):
        frame = C.crop_drift(big, i, f.n, zoom=0.06)
        z = 1 + 0.05 * f.beat[i]
        n_ = cv2.resize(num, None, fx=z, fy=z, interpolation=cv2.INTER_LINEAR) if z > 1.003 else num
        C.paste(frame, n_, (W - n_.shape[1]) // 2, 640 - n_.shape[0] // 2)
        C.paste(frame, unit, (W - unit.shape[1]) // 2, 900)
        if sub is not None:
            C.paste(frame, sub, (W - sub.shape[1]) // 2, 1050)
        C.paste(frame, cov, (W - cov.shape[1]) // 2, 1150)
        yield ov(frame, i, LABEL_Y + 60)


# ---------------------------------------------------------------- 10. text_story
def text_story(job, f):
    lines = job.style.get("lines") or [job.hook or job.title]
    head, body, upper = C.FONT_SETS[job.font_set]
    c1 = np.array(job.pal["dark"], np.float32)
    c2 = np.array(job.pal["accent"], np.float32) * 0.8
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    layers = [C.text_layer(l, head, SAFE_W, 900, 120, 44, color=(255, 255, 255), shadow=12, upper=upper) for l in lines]
    S = 220
    cov = C.bgr_to_rgba(C.cover_fit(job.cover, S, S), C.rounded_mask(S, 16))
    ov = overlays(job)
    per = max(1, int(f.bar_index.max() + 1) // max(1, len(lines))) if len(f.bars) else 2
    for i in range(f.n):
        t = i / f.n
        mix = (yy + 0.25 * np.sin(2 * np.pi * (t * 0.5)))
        mix = np.clip(mix, 0, 1)
        frame = (c1 * (1 - mix) + c2 * mix)
        frame = np.broadcast_to(frame, (H, W, 3)).astype(np.uint8)
        frame = np.ascontiguousarray(frame)
        k = min(len(lines) - 1, int(f.bar_index[i]) // per)
        ly = layers[k]
        # pop on change
        j = i
        while j > 0 and min(len(lines) - 1, int(f.bar_index[j - 1]) // per) == k:
            j -= 1
        a = C.ease((i - j) / 6)
        z = 0.94 + 0.06 * a
        l2 = cv2.resize(ly, None, fx=z, fy=z) if z < 0.999 else ly
        C.paste(frame, l2, (W - l2.shape[1]) // 2, 860 - l2.shape[0] // 2, float(a))
        C.paste(frame, cov, (W - S) // 2, 1250)
        frame = C.grain(frame, i, 3)
        yield ov(frame, i, LABEL_Y + 70, hook=False)


TEMPLATES = {
    "vinyl": vinyl, "bars": bars, "ring": ring, "pulse": pulse, "lyric": lyric,
    "photo_beats": photo_beats, "clip_cut": clip_cut, "waveform": waveform,
    "countdown": countdown, "text_story": text_story,
}


def render(job: Job, log=print):
    import time
    a = job.analysis
    f = C.features(job.audio, job.t0, job.t1, a.get("beats", []), a.get("bars", []))
    w = C.Writer(job.out, job.audio, job.t0, job.t1 - job.t0)
    t = time.time()
    try:
        for fr in TEMPLATES[job.template](job, f):
            w.write(fr)
    finally:
        w.close()
    log(f"rendered {job.out.name} [{job.template}] {job.t1 - job.t0:.1f}s in {time.time() - t:.1f}s")
    return job.out
