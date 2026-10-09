"""Generate stand-in assets (song, cover, photos, clips) so the engine can be built
and tested before the real album files arrive. Output goes to input/_test/."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter

SR = 44100
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "input" / "_test"


def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    e = np.minimum(t / a, 1.0) * np.exp(-t / r)
    return e


def note(freq, dur, kind="saw", r=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "sine":
        w = np.sin(2 * np.pi * freq * t)
    else:
        w = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 8))
    return w * env(n, 0.01, r)


def song(path, bpm=96, seed=1):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = 4 * beat
    # (name, bars, drums, bass, pad, lead, level)
    form = [("intro", 8, 0, 0, 1, 0, 0.35), ("verse", 16, 1, 1, 1, 0, 0.55),
            ("pre", 4, 2, 1, 1, 0, 0.65), ("chorus", 8, 3, 1, 1, 1, 1.0),
            ("verse", 16, 1, 1, 1, 0, 0.55), ("chorus", 8, 3, 1, 1, 1, 1.0),
            ("bridge", 8, 0, 1, 1, 0, 0.45), ("chorus", 8, 3, 1, 1, 1, 1.0),
            ("outro", 8, 1, 0, 1, 0, 0.4)]
    total = sum(f[1] for f in form) * bar
    y = np.zeros(int(total * SR) + SR)
    chords = [[220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.7], [164.8, 207.7, 246.9]]
    motif = [440, 523.3, 587.3, 523.3, 440, 392, 440, 0]
    kick = note(55, 0.35, "sine", 0.12) * 1.2
    snare = rng.standard_normal(int(0.2 * SR)) * env(int(0.2 * SR), 0.001, 0.06) * 0.6
    hat = rng.standard_normal(int(0.05 * SR)) * env(int(0.05 * SR), 0.001, 0.01) * 0.25
    t0 = 0.0
    sections = []
    for name, bars, drums, bass, pad, lead, lvl in form:
        sections.append((name, t0, t0 + bars * bar))
        for b in range(bars):
            bs = t0 + b * bar
            ch = chords[b % 4]
            def add(sig, at, g=1.0):
                i = int(at * SR)
                j = min(len(y), i + len(sig))
                y[i:j] += sig[: j - i] * g * lvl
            if pad:
                for f in ch:
                    add(note(f, bar, "saw", bar * 0.6), bs, 0.05)
            if bass:
                for k in range(4):
                    add(note(ch[0] / 2, beat * 0.9, "saw", 0.25), bs + k * beat, 0.12)
            if drums:
                for k in range(4):
                    if drums >= 1 and k in (0, 2):
                        add(kick, bs + k * beat, 0.7)
                    if drums >= 1 and k in (1, 3):
                        add(snare, bs + k * beat, 0.6)
                    if drums >= 2:
                        add(hat, bs + k * beat + beat / 2, 1.0)
                    if drums >= 3:
                        add(hat, bs + k * beat, 1.0)
            if lead:
                for k, f in enumerate(motif):
                    if f:
                        add(note(f, beat * 0.45, "saw", 0.3), bs + k * beat / 2, 0.09)
        t0 += bars * bar
    # outro fade
    y = y[: int(total * SR)]
    a = int((total - 8 * bar) * SR)
    y[a:] *= np.linspace(1, 0, len(y) - a)
    y = np.tanh(y * 1.4) * 0.8
    st = np.stack([y, np.roll(y, 40) * 0.98], axis=1)
    sf.write(path, st.astype(np.float32), SR, subtype="PCM_24")
    return sections


def cover(path, seed=3):
    rng = np.random.default_rng(seed)
    S = 1600
    img = Image.new("RGB", (S, S))
    px = np.zeros((S, S, 3), np.float32)
    yy, xx = np.mgrid[0:S, 0:S] / S
    px[..., 0] = 40 + 180 * yy
    px[..., 1] = 20 + 60 * xx
    px[..., 2] = 120 + 100 * (1 - yy)
    img = Image.fromarray(px.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(9):
        r = int(rng.uniform(80, 420))
        x, y = rng.uniform(0, S, 2)
        col = tuple(int(c) for c in rng.uniform([200, 80, 40], [255, 200, 120]))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    img = img.filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(img)
    d.rectangle([120, S - 260, S - 120, S - 120], fill=(15, 10, 30))
    img.save(path, quality=95)


def photo(path, seed):
    rng = np.random.default_rng(seed)
    W, H = 1200, 1600
    base = rng.uniform(30, 200, 3)
    img = Image.new("RGB", (W, H), tuple(int(c) for c in base))
    d = ImageDraw.Draw(img)
    d.ellipse([W * 0.3, H * 0.15, W * 0.7, H * 0.45], fill=(230, 190, 160))
    d.rectangle([W * 0.2, H * 0.45, W * 0.8, H], fill=tuple(int(c) for c in rng.uniform(20, 120, 3)))
    img.filter(ImageFilter.GaussianBlur(2)).save(path, quality=92)


def clip(path, src, dur=8):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    src, "-t", str(dur), "-c:v", "libx264",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", str(path)], check=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "photos").mkdir(exist_ok=True)
    (OUT / "clips").mkdir(exist_ok=True)
    (OUT / "tracks").mkdir(exist_ok=True)
    secs = song(OUT / "tracks" / "01 Test Song.wav", 96, 1)
    song(OUT / "tracks" / "02 Second Test.wav", 124, 2)
    cover(OUT / "cover.jpg")
    for i in range(3):
        photo(OUT / "photos" / f"photo{i + 1}.jpg", 10 + i)
    clip(OUT / "clips" / "clip1.mp4", "mandelbrot=size=1080x1920:rate=30")
    clip(OUT / "clips" / "clip2.mp4", "life=size=1080x1920:rate=30:mold=10:ratio=0.1:death_color=#202040:life_color=#e0a060")
    (OUT / "lyrics").mkdir(exist_ok=True)
    (OUT / "lyrics" / "01 Test Song.txt").write_text(
        "[Chorus]\nI keep the window open\nso the city can come in\nevery light a little promise\nthat I'll start again\n")
    print("sections (ground truth):", [(n, round(a, 1), round(b, 1)) for n, a, b in secs])
