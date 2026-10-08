"""Command line entry point.

  python3 -m promo.build <project_dir> analyze
  python3 -m promo.build <project_dir> plan
  python3 -m promo.build <project_dir> render  --from 2026-10-08 --to 2026-10-14
  python3 -m promo.build <project_dir> calendar --from 2026-10-08 --to 2026-10-14

<project_dir> holds album.json, cover.*, tracks/, lyrics/, photos/, clips/.
Outputs go to <project_dir>/_work and <project_dir>/_out."""
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

from . import banks
from . import core as C
from . import stills
from .analyze import analyze
from .plan import build_plan
from .templates import Job, render

IMG = {".jpg", ".jpeg", ".png", ".webp"}
VID = {".mp4", ".mov", ".m4v", ".webm"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.cfg = json.loads((root / "album.json").read_text())
        self.work = root / "_work"
        self.out = root / "_out"
        self.work.mkdir(exist_ok=True)
        self.out.mkdir(exist_ok=True)

    # ---------------- materials
    def track_file(self, t):
        p = self.root / "tracks" / t["file"]
        if not p.exists():
            raise FileNotFoundError(p)
        return p

    def cover_path(self):
        for p in sorted(self.root.glob("cover.*")):
            if p.suffix.lower() in IMG:
                return p
        raise FileNotFoundError("cover image")

    def photos(self):
        d = self.root / "photos"
        return sorted(p for p in d.glob("*") if p.suffix.lower() in IMG) if d.exists() else []

    def clips(self):
        d = self.root / "clips"
        return sorted(p for p in d.glob("*") if p.suffix.lower() in VID) if d.exists() else []

    def lyrics(self):
        out = {}
        d = self.root / "lyrics"
        for t in self.cfg["tracks"]:
            entry = {"lines": [], "synced": []}
            for cand in [t.get("lyrics"), Path(t["file"]).stem + ".txt", Path(t["file"]).stem + ".lrc"]:
                if not cand or not (d / cand).exists():
                    continue
                txt = (d / cand).read_text(errors="ignore")
                for raw in txt.splitlines():
                    m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)", raw.strip())
                    if m:
                        line = m.group(3).strip()
                        if line:
                            entry["synced"].append((int(m.group(1)) * 60 + float(m.group(2)), line))
                            entry["lines"].append(line)
                    else:
                        line = raw.strip()
                        if line and not re.match(r"^\[.*\]$", line) and line not in entry["lines"]:
                            entry["lines"].append(line)
            out[t["title"]] = entry
        return out

    def analyses(self):
        res = {}
        for t in self.cfg["tracks"]:
            p = self.track_file(t)
            cache = self.work / "analysis" / f"{slug(t['title'])}.json"
            if cache.exists() and cache.stat().st_mtime > p.stat().st_mtime:
                res[t["title"]] = json.loads(cache.read_text())
                continue
            t0 = time.time()
            a = analyze(p)
            cache.parent.mkdir(exist_ok=True)
            cache.write_text(json.dumps(a))
            print(f"analyzed {t['title']}: {a['tempo']} BPM, {a['key']}, {len(a['moments'])} moments ({time.time() - t0:.0f}s)")
            res[t["title"]] = a
        return res

    def plan(self):
        p = self.work / "plan.json"
        return json.loads(p.read_text())


def cmd_plan(pr: Project, args):
    an = pr.analyses()
    lyr = pr.lyrics()
    mats = {"photos": len(pr.photos()), "clips": len(pr.clips()), "lyrics": lyr}
    perf_p = pr.root / "performance.json"
    perf = json.loads(perf_p.read_text()) if perf_p.exists() else None
    plan = build_plan(pr.cfg, an, mats, perf=perf, seed=args.seed)
    (pr.work / "plan.json").write_text(json.dumps(plan, indent=1))
    from collections import Counter
    plat = Counter(p["platform"] for p in plan["posts"])
    tmpl = Counter(i["template"] for i in plan["items"])
    trk = Counter(i["track"] for i in plan["items"])
    print(f"plan {plan['start']} → {plan['end']} (release {plan['release']})")
    print(f"  {len(plan['items'])} unique videos, {len(plan['posts'])} posts: {dict(plat)}")
    print(f"  templates: {dict(tmpl)}")
    print(f"  tracks: {dict(trk)}")


def _range(args, plan):
    a = dt.date.fromisoformat(args.from_ or plan["start"])
    b = dt.date.fromisoformat(args.to or plan["end"])
    return a, b


def cmd_render(pr: Project, args):
    plan = pr.plan()
    a, b = _range(args, plan)
    an = pr.analyses()
    cover = C.load_image(pr.cover_path())
    pal = C.palette(cover)
    photos = [C.load_image(p, 2200) for p in pr.photos()]
    clips = pr.clips()
    lyr = pr.lyrics()
    cfg = pr.cfg
    by_title = {t["title"]: t for t in cfg["tracks"]}
    media = pr.out / "media"
    media.mkdir(exist_ok=True)
    todo = [it for it in plan["items"] if a <= dt.date.fromisoformat(it["day"]) <= b]
    print(f"{len(todo)} videos to render for {a} → {b}")
    for n, it in enumerate(todo, 1):
        out = media / f"{it['id']}.mp4"
        if out.exists() and not args.force:
            continue
        t = by_title[it["track"]]
        L = lyr.get(t["title"], {})
        ipal = pal if it.get("palette", "cover") == "cover" else C.label_palette(it["palette"])
        job = Job(out=out, audio=pr.track_file(t), t0=it["t0"], t1=it["t1"], analysis=an[t["title"]],
                  cover=cover, pal=ipal, template=it["template"], hook=it["hook"], title=t["title"],
                  artist=cfg.get("artist", ""), font_set=it["font_set"], hook_style=it["hook_style"],
                  style={k: it[k] for k in ("days", "when", "unit", "lines", "pulse_mode", "lyric_bg") if k in it},
                  photos=photos, clips=clips, lyrics=L.get("synced") or L.get("lines", []), seed=it["seed"])
        print(f"[{n}/{len(todo)}] ", end="")
        render(job)
        C.thumbnail(out, media / f"{it['id']}.jpg", t=min(1.5, (it["t1"] - it["t0"]) / 3))
    # story cards
    release = dt.date.fromisoformat(plan["release"])
    lang = plan.get("card_lang", "en")
    lpal = C.label_palette("obsidian_gold")
    d = a
    while d <= b:
        days = (release - d).days
        name = f"card-{'countdown' if days > 0 else 'outnow'}-{d.isoformat()}.jpg"
        p = media / name
        if not p.exists() or args.force:
            cpal = lpal if (d.toordinal() % 2 and cfg.get("palette_mix", 0)) else pal
            date_str = banks.date_words(release, days, lang)[1]
            img = (stills.countdown_card(cover, cpal, days, cfg["album"], cfg["artist"], date_str, lang=lang)
                   if days > 0 else stills.outnow_card(cover, cpal, cfg["album"], cfg["artist"], lang=lang))
            stills.save(img, p)
        d += dt.timedelta(days=1)


def cmd_calendar(pr: Project, args):
    from .calendar import write_calendar
    plan = pr.plan()
    a, b = _range(args, plan)
    out = write_calendar(pr, plan, a, b)
    print(f"calendar → {out}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("cmd", choices=["analyze", "plan", "render", "calendar"])
    ap.add_argument("--from", dest="from_")
    ap.add_argument("--to")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    pr = Project(Path(args.project).resolve())
    if args.cmd == "analyze":
        pr.analyses()
    elif args.cmd == "plan":
        cmd_plan(pr, args)
    elif args.cmd == "render":
        cmd_render(pr, args)
    elif args.cmd == "calendar":
        cmd_calendar(pr, args)


if __name__ == "__main__":
    main()
