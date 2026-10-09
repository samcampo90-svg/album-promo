# album-promo

Turns an album (tracks, cover art, lyrics, photos, phone clips) into a short-form video campaign: hundreds of vertical videos for TikTok, Reels and Shorts, captions per platform, and a day-by-day posting calendar page.

## How it works

1. **Analyze** each track (`promo/analyze.py`): tempo, beats, bar lines, sections, and the best 9–30 s moments (chorus, builds/drops, quiet parts, intro), all starting and ending on bar lines.
2. **Plan** the campaign (`promo/plan.py`, `promo/banks.py`): for each day, which track, moment, video style, on-screen hook, fonts, and captions for each platform. Hooks that state facts only appear when those facts are provided in `album.json`.
3. **Render** (`promo/templates.py`, `promo/core.py`): frames are drawn with OpenCV/numpy and driven by per-frame audio features (48-band spectrum, bass, loudness, beat and bar pulses), then encoded with ffmpeg to H.264/AAC MP4. Ten styles: vinyl, bars, ring, pulse, lyric, photo_beats, clip_cut, waveform, countdown, text_story.
4. **Calendar** (`promo/calendar.py`): a phone-friendly page with each day's posts, save buttons, copy-caption buttons, posted checkboxes and view logging.

## Run

```
pip install -r requirements.txt        # plus ffmpeg on the PATH
python3 -m promo.build <project_dir> plan
python3 -m promo.build <project_dir> render --from 2026-10-08 --to 2026-10-14
python3 -m promo.build <project_dir> calendar --from 2026-10-08 --to 2026-10-14
```

`<project_dir>` holds `album.json`, `cover.jpg`, `tracks/`, `lyrics/` (plain `.txt` or synced `.lrc`), `photos/` and `clips/`. See `tools/make_test_assets.py` for a stand-in project. Media is never committed here.
