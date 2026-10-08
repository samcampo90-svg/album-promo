"""Rendering core: audio features per video frame, image/text helpers, and the
ffmpeg writer. Frames are BGR uint8 numpy arrays (OpenCV convention)."""
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import cv2
import librosa
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"

FONT_SETS = {
    # name: (headline font, body font, uppercase headline?)
    "native": ("Inter_800ExtraBold.ttf", "Inter_600SemiBold.ttf", False),
    "condensed": ("Anton_400Regular.ttf", "Inter_600SemiBold.ttf", True),
    "bebas": ("BebasNeue_400Regular.ttf", "SpaceGrotesk_500Medium.ttf", True),
    "serif": ("PlayfairDisplay_700Bold_Italic.ttf", "PlayfairDisplay_400Regular_Italic.ttf", False),
    "dmserif": ("DMSerifDisplay_400Regular.ttf", "Inter_400Regular.ttf", False),
    "grotesk": ("SpaceGrotesk_700Bold.ttf", "SpaceGrotesk_500Medium.ttf", False),
    "mono": ("SpaceMono_700Bold.ttf", "SpaceMono_400Regular.ttf", False),
    "marker": ("PermanentMarker_400Regular.ttf", "Inter_600SemiBold.ttf", False),
    "syne": ("Syne_800ExtraBold.ttf", "Inter_600SemiBold.ttf", True),
    "archivo": ("ArchivoBlack_400Regular.ttf", "Inter_600SemiBold.ttf", True),
}


# ---------------------------------------------------------------- audio features
@dataclass
class Features:
    t0: float
    dur: float
    n: int                      # number of video frames
    rms: np.ndarray             # (n,) 0..1
    bass: np.ndarray            # (n,) 0..1
    highs: np.ndarray           # (n,) 0..1
    bands: np.ndarray           # (n, B) 0..1, attack/release smoothed
    beat: np.ndarray            # (n,) 0..1 decaying pulse at each beat
    bar: np.ndarray             # (n,) 0..1 decaying pulse at each bar line
    bar_index: np.ndarray       # (n,) int, which bar we're in (for cuts)
    wave: np.ndarray            # (n, 512) waveform snippet per frame, -1..1
    beats: list = field(default_factory=list)  # beat times relative to clip start
    bars: list = field(default_factory=list)


def _norm(x, hi_pct=97):
    hi = np.percentile(x, hi_pct) + 1e-9
    return np.clip(x / hi, 0, 1)


def _ar(x, att, rel):
    """attack/release smoothing along axis 0"""
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        d = x[i] - y[i - 1]
        y[i] = y[i - 1] + d * np.where(d > 0, att, rel)
    return y


def features(audio: Path, t0: float, t1: float, beats=(), bars=(), n_bands=48) -> Features:
    sr = 22050
    dur = t1 - t0
    y, _ = librosa.load(str(audio), sr=sr, mono=True, offset=max(0, t0 - 0.05), duration=dur + 0.1)
    pad = int(0.05 * sr) if t0 >= 0.05 else int(t0 * sr)
    y = y[pad: pad + int(dur * sr)]
    if len(y) < int(dur * sr):
        y = np.pad(y, (0, int(dur * sr) - len(y)))
    n = int(round(dur * FPS))
    hop = sr / FPS
    centers = (np.arange(n) * hop + hop / 2).astype(int)
    nfft = 2048
    win = np.hanning(nfft)
    ypad = np.pad(y, (nfft // 2, nfft // 2))
    frames = np.stack([ypad[c: c + nfft] * win for c in centers])
    spec = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    edges = np.geomspace(40, 11000, n_bands + 1)
    bands = np.stack([spec[:, (freqs >= a) & (freqs < b)].mean(axis=1) if ((freqs >= a) & (freqs < b)).any()
                      else np.zeros(n) for a, b in zip(edges[:-1], edges[1:])], axis=1)
    bands = np.log1p(bands * 10)
    bands = bands / (np.percentile(bands, 98, axis=0) + 1e-9)
    bands = np.clip(_ar(bands, 0.7, 0.18), 0, 1)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    bass = spec[:, (freqs > 30) & (freqs < 160)].mean(axis=1)
    highs = spec[:, (freqs > 4000)].mean(axis=1)
    t = np.arange(n) / FPS

    def pulses(times, decay):
        p = np.zeros(n)
        for tb in times:
            m = t >= tb
            p[m] = np.maximum(p[m], np.exp(-(t[m] - tb) / decay))
        return p

    rb = [b - t0 for b in beats if t0 - 0.5 <= b < t1]
    rbar = [b - t0 for b in bars if t0 - 0.5 <= b < t1]
    bar_index = np.searchsorted(np.array(rbar), t, side="right") if rbar else (t // 2.0).astype(int)
    # waveform snippet per frame for oscilloscope lines
    wl = 512
    idx = np.clip(centers[:, None] + np.arange(-wl // 2, wl // 2)[None, :], 0, len(y) - 1)
    wave = y[idx]
    wave = wave / (np.percentile(np.abs(y), 99.5) + 1e-9)
    return Features(t0, dur, n, _ar(_norm(rms), 0.6, 0.15), _ar(_norm(bass), 0.7, 0.2),
                    _ar(_norm(highs), 0.7, 0.2), bands, pulses(rb, 0.16), pulses(rbar, 0.35),
                    bar_index, np.clip(wave, -1.5, 1.5), rb, rbar)


# ---------------------------------------------------------------- image helpers
def load_image(path, max_side=2000):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        img = cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2BGR)
    s = max(img.shape[:2])
    if s > max_side:
        f = max_side / s
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    return img


def cover_fit(img, w, h):
    """scale+center-crop to exactly w x h"""
    ih, iw = img.shape[:2]
    f = max(w / iw, h / ih)
    r = cv2.resize(img, (int(np.ceil(iw * f)), int(np.ceil(ih * f))), interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC)
    y0 = (r.shape[0] - h) // 2
    x0 = (r.shape[1] - w) // 2
    return r[y0:y0 + h, x0:x0 + w].copy()


def blurred_bg(img, w=W, h=H, scale=1.12, blur=60, dim=0.55, sat=1.15, vig=0.55):
    """oversized blurred background (vignette baked in) so it can drift/zoom by cropping"""
    bw, bh = int(w * scale), int(h * scale)
    small = cover_fit(img, bw // 4, bh // 4)
    small = cv2.GaussianBlur(small, (0, 0), blur / 4)
    big = cv2.resize(small, (bw, bh), interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(big, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * sat, 0, 255)
    hsv[..., 2] *= dim
    big = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    if vig:
        big = (big * vignette(bw, bh, vig)).clip(0, 255).astype(np.uint8)
    return big


def crop_drift(big, i, n, w=W, h=H, zoom=0.0):
    """crop a w x h window that drifts slowly; zoom>0 zooms in over time"""
    bh, bw = big.shape[:2]
    t = i / max(1, n - 1)
    z = 1 + zoom * t
    cw, ch = int(w * (bw / w) / z), int(h * (bh / h) / z)
    cw, ch = min(bw, max(w, cw)), min(bh, max(h, ch))
    x0 = int((bw - cw) * (0.5 + 0.4 * np.sin(t * 2.1)) )
    y0 = int((bh - ch) * (0.5 + 0.4 * np.cos(t * 1.7)))
    win = big[y0:y0 + ch, x0:x0 + cw]
    if win.shape[1] != w or win.shape[0] != h:
        win = cv2.resize(win, (w, h), interpolation=cv2.INTER_LINEAR)
    return win.copy()


def vignette(w=W, h=H, strength=0.55):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    return (1 - strength * d ** 2)[..., None].astype(np.float32)


def rounded_mask(size, radius):
    m = np.zeros((size, size), np.uint8)
    cv2.rectangle(m, (radius, 0), (size - radius, size), 255, -1)
    cv2.rectangle(m, (0, radius), (size, size - radius), 255, -1)
    for cx, cy in ((radius, radius), (size - radius, radius), (radius, size - radius), (size - radius, size - radius)):
        cv2.circle(m, (cx, cy), radius, 255, -1, cv2.LINE_AA)
    return m


def circle_mask(size):
    m = np.zeros((size, size), np.uint8)
    cv2.circle(m, (size // 2, size // 2), size // 2 - 1, 255, -1, cv2.LINE_AA)
    return m


def with_shadow(rgba, blur=40, offset=(0, 24), alpha=0.6):
    """returns a larger RGBA image with a soft drop shadow"""
    h, w = rgba.shape[:2]
    p = blur * 2
    out = np.zeros((h + 2 * p, w + 2 * p, 4), np.uint8)
    sh = np.zeros((h + 2 * p, w + 2 * p), np.float32)
    sh[p + offset[1]: p + offset[1] + h, p + offset[0]: p + offset[0] + w] = rgba[..., 3] / 255.0
    sh = cv2.GaussianBlur(sh, (0, 0), blur / 2) * alpha
    out[..., 3] = (sh * 255).astype(np.uint8)
    blend_rgba(out, rgba, p, p)
    return out


def blend_rgba(dst_rgba, src_rgba, x, y):
    """alpha-over src onto an RGBA canvas (used for building layers)"""
    h, w = src_rgba.shape[:2]
    d = dst_rgba[y:y + h, x:x + w].astype(np.float32)
    s = src_rgba.astype(np.float32)
    sa = s[..., 3:4] / 255
    da = d[..., 3:4] / 255
    oa = sa + da * (1 - sa)
    rgb = (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    dst_rgba[y:y + h, x:x + w, :3] = rgb.astype(np.uint8)
    dst_rgba[y:y + h, x:x + w, 3] = (oa[..., 0] * 255).astype(np.uint8)


def paste(frame, rgba, x, y, opacity=1.0):
    """alpha-composite an RGBA (or BGR) layer onto a BGR frame at (x, y), clipped"""
    h, w = rgba.shape[:2]
    fx0, fy0 = max(0, x), max(0, y)
    fx1, fy1 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
    if fx1 <= fx0 or fy1 <= fy0:
        return frame
    sx0, sy0 = fx0 - x, fy0 - y
    src = rgba[sy0:sy0 + (fy1 - fy0), sx0:sx0 + (fx1 - fx0)]
    dst = frame[fy0:fy1, fx0:fx1]
    if src.shape[2] == 3:
        if opacity >= 1:
            dst[:] = src
        else:
            cv2.addWeighted(src, opacity, dst, 1 - opacity, 0, dst)
        return frame
    a = src[..., 3:4].astype(np.uint16)
    if opacity < 1:
        a = (a * int(opacity * 255)) // 255
    dst[:] = ((src[..., :3].astype(np.uint16) * a + dst.astype(np.uint16) * (255 - a)) // 255).astype(np.uint8)
    return frame


def bgr_to_rgba(img, mask=None):
    a = np.full(img.shape[:2], 255, np.uint8) if mask is None else mask
    return np.dstack([img, a])


# ---------------------------------------------------------------- palette
def palette(img, k=6):
    small = cv2.resize(img, (96, 96), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, labels, centers = cv2.kmeans(small, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k)
    cols = [tuple(int(v) for v in c) for c in centers]
    hsv = [cv2.cvtColor(np.uint8([[c]]), cv2.COLOR_BGR2HSV)[0, 0] for c in cols]
    order = np.argsort(-counts)
    dominant = cols[order[0]]
    # accent: most saturated*bright color that isn't tiny
    score = [(int(h[1]) * int(h[2])) * (0.3 + counts[i] / counts.sum()) for i, h in enumerate(hsv)]
    accent = cols[int(np.argmax(score))]
    dark = cols[int(np.argmin([h[2] for h in hsv]))]
    light = cols[int(np.argmax([int(h[2]) - int(h[1]) * 0.3 for h in hsv]))]
    acc_hsv = cv2.cvtColor(np.uint8([[accent]]), cv2.COLOR_BGR2HSV)[0, 0].astype(int)
    acc_hsv[1] = max(acc_hsv[1], 150)
    acc_hsv[2] = max(acc_hsv[2], 210)
    vivid = tuple(int(v) for v in cv2.cvtColor(np.uint8([[acc_hsv]]), cv2.COLOR_HSV2BGR)[0, 0])
    return {"dominant": dominant, "accent": accent, "vivid": vivid, "dark": dark, "light": light,
            "all": [cols[i] for i in order]}


LABEL = {  # the label's brand colors (solo-label-engine assets/brand.py), as BGR
    "gold": (55, 175, 212), "red": (0, 0, 176), "crimson": (0, 0, 139), "olive": (47, 107, 85),
    "silver": (192, 192, 192), "white": (245, 245, 245), "black": (9, 10, 12), "charcoal": (26, 26, 26),
}
LABEL_PALETTES = {  # (bg, primary, secondary, accent, highlight)
    "obsidian_gold": ("black", "gold", "crimson", "olive", "white"),
    "blood_gold": ("black", "red", "gold", "crimson", "silver"),
    "silver_rite": ("charcoal", "silver", "gold", "white", "crimson"),
    "olive_reliquary": ("black", "olive", "gold", "silver", "white"),
    "ash_crimson": ("charcoal", "crimson", "silver", "gold", "white"),
}


def label_palette(name):
    """A label sub-palette in the same shape as palette(). The bright role drives
    bars/rings/accent text; the background blur is desaturated so the brand
    colors carry the frame."""
    bg, pri, sec, acc, hi = (LABEL[c] for c in LABEL_PALETTES.get(name, LABEL_PALETTES["obsidian_gold"]))
    bright = max((pri, sec), key=lambda c: sum(c))
    return {"dominant": pri, "accent": pri, "vivid": bright, "dark": bg, "light": hi, "secondary": sec,
            "all": [pri, sec, acc, hi], "bg_sat": 0.25, "bg_dim": 0.8, "name": name}


# ---------------------------------------------------------------- text
@lru_cache(maxsize=256)
def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(draw, text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        words = para.split()
        cur = ""
        for w_ in words:
            test = (cur + " " + w_).strip()
            if draw.textlength(test, font=fnt) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w_
        lines.append(cur)
    return lines


def text_layer(text, font_name, max_w=900, max_h=600, size=96, min_size=36, color=(255, 255, 255),
               stroke=0, stroke_color=(0, 0, 0), box=None, box_pad=(28, 18), box_radius=18,
               align="center", spacing=1.12, shadow=0, upper=False, line_boxes=False):
    """render text to an RGBA numpy array (BGR order), shrinking to fit max_w x max_h.
    box: BGR color for a solid rounded box behind (TikTok-native style). line_boxes: box per line."""
    if upper:
        text = text.upper()
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    s = size
    while True:
        fnt = font(font_name, s)
        lines = _wrap(probe, text, fnt, max_w - (2 * box_pad[0] if box else 0))
        asc, desc = fnt.getmetrics()
        lh = int((asc + desc) * spacing)
        widths = [probe.textlength(l, font=fnt) for l in lines]
        th = lh * len(lines)
        if (th <= max_h and max(widths) <= max_w) or s <= min_size:
            break
        s = int(s * 0.92)
    pad = stroke + shadow + 4
    bx, by = (box_pad if box else (0, 0))
    Wt = int(max(widths) + 2 * bx + 2 * pad)
    Ht = int(th + 2 * by + 2 * pad + (by * (len(lines) - 1) * 0.4 if line_boxes else 0))
    img = Image.new("RGBA", (Wt, Ht), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rgb = lambda c: (c[2], c[1], c[0])
    if box is not None and not line_boxes:
        d.rounded_rectangle([pad, pad, Wt - pad, Ht - pad], radius=box_radius, fill=rgb(box) + (255,))
    y = pad + by
    for l, wl in zip(lines, widths):
        if align == "center":
            x = (Wt - wl) / 2
        elif align == "left":
            x = pad + bx
        else:
            x = Wt - pad - bx - wl
        if box is not None and line_boxes:
            d.rounded_rectangle([x - bx * 0.7, y - by * 0.35, x + wl + bx * 0.7, y + lh - by * 0.1],
                                radius=box_radius, fill=rgb(box) + (255,))
        if shadow:
            d.text((x + shadow * 0.4, y + shadow), l, font=fnt, fill=(0, 0, 0, 150))
        d.text((x, y), l, font=fnt, fill=rgb(color) + (255,), stroke_width=stroke, stroke_fill=rgb(stroke_color) + (255,))
        y += lh + (by * 0.4 if line_boxes else 0)
    arr = np.array(img)
    if shadow:
        a = arr[..., 3].astype(np.float32)
        glow = cv2.GaussianBlur(a, (0, 0), shadow)
        sh = np.zeros_like(arr)
        sh[..., 3] = (glow * 0.6).astype(np.uint8)
        out = sh.copy()
        out_rgba = np.dstack([arr[..., 2], arr[..., 1], arr[..., 0], arr[..., 3]])
        blend_rgba(out, out_rgba, 0, 0)
        return out
    return np.dstack([arr[..., 2], arr[..., 1], arr[..., 0], arr[..., 3]])


# ---------------------------------------------------------------- effects
_GRAIN = {}


def grain(frame, i, amount=10):
    key = (frame.shape, amount)
    if key not in _GRAIN:
        rng = np.random.default_rng(7)
        layers = []
        for _ in range(6):
            n = rng.integers(-amount, amount + 1, frame.shape[:2], dtype=np.int16)
            pos = np.repeat(np.clip(n, 0, None).astype(np.uint8)[..., None], 3, axis=2)
            neg = np.repeat(np.clip(-n, 0, None).astype(np.uint8)[..., None], 3, axis=2)
            layers.append((pos, neg))
        _GRAIN[key] = layers
    pos, neg = _GRAIN[key][i % 6]
    out = cv2.add(frame, pos)
    return cv2.subtract(out, neg, dst=out)


def gain(frame, g):
    return cv2.convertScaleAbs(frame, alpha=float(g), beta=0) if abs(g - 1) > 1e-3 else frame


def rgb_split(frame, px):
    if px < 1:
        return frame
    px = int(px)
    out = frame.copy()
    out[:, px:, 2] = frame[:, :-px, 2]
    out[:, :-px, 0] = frame[:, px:, 0]
    return out


def zoom_frame(frame, z):
    if abs(z - 1) < 1e-3:
        return frame
    h, w = frame.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), 0, z)
    return cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def ease(x):
    x = np.clip(x, 0, 1)
    return 1 - (1 - x) ** 3


# ---------------------------------------------------------------- writer
class Writer:
    def __init__(self, out: Path, audio: Path = None, t0=0.0, dur=None, w=W, h=H, fps=FPS,
                 fade_out=0.6, crf=21, preset="veryfast"):
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
        if audio is not None:
            cmd += ["-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(audio)]
            af = f"afade=t=in:d=0.02,afade=t=out:st={max(0, dur - fade_out):.3f}:d={fade_out},volume=-1dB"
            cmd += ["-filter:a", af, "-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-maxrate", "5M", "-bufsize", "10M",
                "-pix_fmt", "yuv420p",
                "-profile:v", "high", "-movflags", "+faststart", "-shortest", str(out)]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self.out = out

    def write(self, frame):
        self.p.stdin.write(frame.tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise RuntimeError(f"ffmpeg failed for {self.out}")


def thumbnail(video: Path, out: Path, t=1.0, width=360):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                    "-vf", f"scale={width}:-2", "-q:v", "4", str(out)], check=True)
