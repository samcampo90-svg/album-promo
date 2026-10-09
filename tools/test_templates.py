import json, sys, time
from pathlib import Path
import numpy as np
from promo import core as C
from promo.analyze import analyze
from promo.templates import Job, render, TEMPLATES

root = Path(__file__).resolve().parents[1]
T = root / "input" / "_test"
audio = T / "tracks" / "01 Test Song.wav"
cache = root / "work" / "test_analysis.json"
if cache.exists():
    a = json.loads(cache.read_text())
else:
    a = analyze(audio); cache.parent.mkdir(exist_ok=True, parents=True); cache.write_text(json.dumps(a))
cover = C.load_image(T / "cover.jpg")
pal = C.palette(cover)
photos = [C.load_image(p) for p in sorted((T / "photos").glob("*.jpg"))]
clips = sorted((T / "clips").glob("*.mp4"))
lyr = [(70.0, "I keep the window open"), (72.5, "so the city can come in"), (75.0, "every light a little promise"), (77.5, "that I'll start again")]
which = sys.argv[1:] or list(TEMPLATES)
hooks = {"vinyl": ("POV: you found your new favorite song", "line_boxes", "native"),
         "bars": ("wait for the chorus", "box_black", "native"),
         "ring": ("this one hits different at night", "stroke", "condensed"),
         "pulse": ("the drop I've been sitting on for a year", "shadow", "bebas"),
         "lyric": ("", "line_boxes", "serif"),
         "photo_beats": ("I made this album in my bedroom", "line_boxes", "native"),
         "clip_cut": ("studio days for this one", "box_black", "grotesk"),
         "waveform": ("the part at 1:10 lives in my head", "line_boxes", "native"),
         "countdown": ("", "line_boxes", "archivo"),
         "text_story": ("", "line_boxes", "dmserif")}
for t in which:
    hook, hs, fs = hooks[t]
    style = {"days": 5, "when": "OUT OCT 28", "lines": ["I wrote this at 3am", "after the longest year", "it's finally out Friday"]}
    job = Job(out=root / "work" / "test" / f"{t}.mp4", audio=audio, t0=70.0, t1=80.0, analysis=a, cover=cover, pal=pal,
              template=t, hook=hook, title="Test Song", artist="Sam Campo", font_set=fs, hook_style=hs,
              style=style, photos=photos, clips=clips, lyrics=lyr if t == "lyric" else [], seed=3)
    t0 = time.time(); render(job)
    C.thumbnail(job.out, root / "work" / "test" / f"{t}.jpg", t=4.0, width=540)
