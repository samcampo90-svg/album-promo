"""Adapter for Sam's Asset Forge (solo-label-engine/assets): renders its WebGL
fractal "drop clips" for any audio file, without needing the vault database.

It builds the same feature pack and section map Asset Forge expects, swaps the
Windows GPU flags for software rendering on Linux, and adds a selection step:
many seed candidates are rendered as small sample frames, scored, and only the
best go to full render. That turns the generator's inconsistency into a
pick-the-best problem.
"""
import os
import sys
import time
from pathlib import Path

import numpy as np

SLE = Path(os.environ.get("SLE_PATH", "/home/claude/solo-label-engine"))
if str(SLE) not in sys.path:
    sys.path.insert(0, str(SLE))

from core.timeline import compute_timeline            # noqa: E402
from assets import (director, timeline_features, beatgrid, choreography,  # noqa: E402
                    renderer, brand)

# Linux / headless: software WebGL instead of the Windows ANGLE-D3D11 path.
renderer._CHROMIUM_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                           "--ignore-gpu-blocklist"]

LABEL_MAP = {"chorus": "drop", "high": "drop", "low": "breakdown", "mid": "verse"}


def feature_pack(audio: Path, out_dir: Path):
    """Compute Asset Forge's ~10 fps feature pack for an audio file -> .npz path."""
    import librosa
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (audio.stem + ".npz")
    if out.exists() and out.stat().st_mtime > audio.stat().st_mtime:
        return out
    y, sr = librosa.load(str(audio), sr=44100, mono=True)
    pack = compute_timeline(y.astype(np.float32), sr)
    np.savez_compressed(out, **pack)
    return out


def sections_from_analysis(a):
    """Map promo.analyze sections onto Asset Forge labels (intro/build/drop/verse/breakdown/outro)."""
    secs = a.get("sections", [])
    out = []
    for i, s in enumerate(secs):
        lab = LABEL_MAP.get(s.get("label"), "verse")
        if i == 0 and s.get("energy", 1) < 0.4:
            lab = "intro"
        elif i == len(secs) - 1 and s.get("energy", 1) < 0.4:
            lab = "outro"
        out.append({"label": lab, "start_s": s["start"], "end_s": s["end"],
                    "loudness": float(s.get("energy", 0)) * 20 - 20})
    # a short section right before a drop reads as the build
    for i in range(1, len(out)):
        if out[i]["label"] == "drop" and out[i - 1]["label"] in ("verse", "breakdown") \
                and out[i - 1]["end_s"] - out[i - 1]["start_s"] <= 16:
            out[i - 1]["label"] = "build"
    return out


def make_track(audio: Path, analysis: dict, pack: Path, mood="", genre="", tone="", tid=1):
    return {"id": tid, "track_title": analysis.get("title", audio.stem), "audio_path": str(audio),
            "bpm": analysis.get("tempo"), "tempo_confidence": 0.8, "duration_s": analysis.get("duration"),
            "feature_path": str(pack), "genre": genre, "mood": mood, "tone": tone, "clip_path": None}


def _score(imgs):
    """Aesthetic score for sample frames: contrast, detail, not mostly black, motion between samples."""
    import cv2
    s, prev = [], None
    for im in imgs:
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
        lum = g.mean() / 255
        contrast = g.std() / 64
        detail = np.abs(cv2.Laplacian(g, cv2.CV_32F)).mean() / 20
        dark = (g < 12).mean()
        motion = 0.0 if prev is None else np.abs(g - prev).mean() / 30
        prev = g
        pen = 2.0 if dark > 0.75 else 0.0
        s.append(min(contrast, 1.5) + min(detail, 1.5) + min(motion, 1.0) + min(lum * 3, 1.0) - pen)
    return float(np.mean(s))


def plan_clip(track, sections, seconds, fps, spec):
    start_s, duration = timeline_features.select_window(track, sections, seconds)
    signals, n_frames = timeline_features.load_signals(track, start_s, duration, fps)
    grid = beatgrid.build_grid(track, signals, duration, fps)
    plan = choreography.build_keyframes(sections, start_s, duration, fps, spec, int(spec.get("seed") or 0), grid=grid)
    scene_static, frames = timeline_features.build_frames(signals, n_frames, spec, fps, plan, grid=grid)
    return start_s, duration, scene_static, frames, plan


def candidates(track, sections, n=8, seconds=15, fps=30, sw=180, sh=320, presets=None, palettes=None,
               journey=False, seed0=1):
    """Render a few sample frames for n seed/preset/palette variants and score them.
    Returns a list of (score, spec, sample_images) sorted best-first."""
    import cv2
    rng = np.random.default_rng(seed0)
    presets = presets or ["kali", "spiral", "mandala", "mandelbrot", "julia", "burning_ship", "flow", "orbit"]
    palettes = palettes or brand.palette_names()
    out = []
    for k in range(n):
        ov = {"seed": int(rng.integers(1, 1 << 20)), "preset": presets[k % len(presets)],
              "palette": palettes[int(rng.integers(len(palettes)))]}
        spec = director.build_scene_spec(track, sections, use_ai=False, overrides=ov, journey=journey)
        start_s, duration, scene_static, frames, plan = plan_clip(track, sections, seconds, fps, spec)
        idx = sorted({min(len(frames) - 1, int(t * len(frames))) for t in (0.2, 0.45, 0.6, 0.8)})
        imgs = []
        for b in renderer.frame_stream(scene_static, [frames[i] for i in idx], sw, sh):
            imgs.append(cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR))
        out.append((_score(imgs), spec, imgs))
    out.sort(key=lambda x: -x[0])
    return out


def render(track, sections, spec, out: Path, seconds=15, fps=30, w=720, h=1280, log=print):
    """Full render of one spec -> mp4 (audio = the clip window). Frames are upscaled to 1080x1920."""
    import cv2
    from .core import Writer
    start_s, duration, scene_static, frames, plan = plan_clip(track, sections, seconds, fps, spec)
    t = time.time()
    wr = Writer(out, Path(track["audio_path"]), start_s, duration)
    try:
        for b in renderer.frame_stream(scene_static, frames, w, h):
            im = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
            if im.shape[1] != 1080:
                im = cv2.resize(im, (1080, 1920), interpolation=cv2.INTER_CUBIC)
            wr.write(im)
    finally:
        wr.close()
    log(f"forge render {out.name}: {spec.get('preset')}/{spec.get('palette_name')} seed {spec.get('seed')} "
        f"{len(frames)} frames in {time.time() - t:.0f}s")
    return out, start_s, duration
