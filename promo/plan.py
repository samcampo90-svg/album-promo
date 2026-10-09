"""Campaign planner: turns album.json + track analyses into a day-by-day list of
unique videos and the posts that use them (TikTok, YouTube Shorts, Instagram
Reels, Stories, carousels), with captions written per platform."""
import datetime as dt
import random
import re
from collections import Counter, defaultdict

from . import banks

PH = re.compile(r"{(\w+)}")
REQUIRES = {"independent artist": "independent", "no label": "independent", "almost didn't release": "almost_didnt",
            "sin disquera": "independent", "casi no saco": "almost_didnt"}
LABEL_PALETTES = ["obsidian_gold", "blood_gold", "silver_rite", "olive_reliquary", "ash_crimson"]
TEMPLATE_W = {"vinyl": 1.0, "bars": 1.0, "ring": 0.9, "pulse": 1.0, "lyric": 1.6, "photo_beats": 1.2,
              "clip_cut": 1.8, "waveform": 0.9, "text_story": 0.8, "dump": 2.0}
HOOK_STYLE_W = {"line_boxes": 0.35, "box_black": 0.2, "stroke": 0.2, "shadow": 0.15, "accent": 0.1}
FONT_SETS = ["native", "condensed", "bebas", "serif", "dmserif", "grotesk", "mono", "marker", "syne", "archivo"]
TIMES = {"tiktok": ["11:00", "15:00", "19:00", "21:30", "13:00", "17:00"], "shorts": ["12:00", "17:30", "20:30", "14:00"],
         "reels": ["13:00", "19:30", "10:00"], "stories": ["09:00", "14:00", "20:00", "22:00"]}
COUNTDOWN_DAYS = {21, 14, 10, 7, 5, 3, 2, 1}


def fmt_ts(t):
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


def fill(text, ctx):
    for k, v in REQUIRES.items():
        if k in text.lower() and not ctx.get(v):
            return None
    keys = PH.findall(text)
    if any(ctx.get(k) in (None, "", []) for k in keys):
        return None
    return PH.sub(lambda m: str(ctx[m.group(1)]), text)


def phase_of(day, release):
    d = (day - release).days
    if d < 0:
        return "pre"
    if d <= 2:
        return "release"
    return "post"


def _wchoice(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def build_plan(cfg, analyses, materials, perf=None, start=None, end=None, seed=7):
    """analyses: {title: analysis}; materials: {"photos": int, "clips": int, "lyrics": {title: {"synced": [...], "lines": [...]}}}
    perf: optional multipliers learned from results: {"track": {title: w}, "template": {...}, "hook_kind": {...}}"""
    rng = random.Random(seed)
    perf = perf or {}
    release = dt.date.fromisoformat(cfg["release_date"])
    camp = cfg.get("campaign", {})
    start = start or dt.date.fromisoformat(camp.get("start", str(dt.date.today())))
    end = end or (release + dt.timedelta(weeks=camp.get("weeks_after", 4)))
    rates = {"tiktok": 4, "shorts": 3, "reels": 2, "stories": 3, **camp.get("rates", {})}
    tracks = cfg["tracks"]
    by_title = {t["title"]: t for t in tracks}
    focus = [t["title"] for t in tracks if t.get("focus")] or [tracks[0]["title"]]
    facts = cfg.get("facts", {})
    sims = cfg.get("similar_artists", [])
    langs = cfg.get("languages") or {"en": 1.0}
    palette_mix = float(cfg.get("palette_mix", 0.0))          # share of videos in the label palette
    label_pals = cfg.get("label_palettes") or LABEL_PALETTES

    def loc(d, k, lang):
        """language-specific value: key_<lang>, falling back to the bare key only for English"""
        v = d.get(f"{k}_{lang}")
        if v in (None, "", []) and lang == "en":
            v = d.get(k)
        return v

    used_keys = set()
    hook_last = {}                      # hook text -> last day index used
    moment_use = Counter()
    template_recent = defaultdict(list)
    items, posts = [], []

    def track_weights(phase):
        w = []
        for t in tracks:
            base = 1.0
            if t["title"] in focus:
                base = {"pre": 6.0, "release": 3.0, "post": 2.0}[phase]
            elif phase == "pre":
                base = 0.35
            base *= perf.get("track", {}).get(t["title"], 1.0)
            w.append(base)
        return w

    def ctx_for(t, day, phase, moment=None, lang="en"):
        lyr = materials.get("lyrics", {}).get(t["title"], {})
        short_lines = [l for l in lyr.get("lines", []) if 12 <= len(l) <= 60]
        days_left = (release - day).days
        day_name, date, _ = banks.date_words(release, days_left, lang)
        acts = loc(cfg, "activities", lang)
        return {
            "artist": cfg.get("artist"), "album": cfg.get("album"), "song": t["title"],
            "sim1": sims[0] if sims else None, "sim2": sims[1] if len(sims) > 1 else None,
            "vibe": loc(cfg, "vibe", lang), "activity": rng.choice(acts) if acts else None,
            "made_where": loc(facts, "made_where", lang), "months": facts.get("months"),
            "independent": facts.get("independent"), "almost_didnt": t.get("almost_didnt"),
            "about": loc(t, "about", lang), "for_anyone_who": loc(t, "for_anyone_who", lang),
            "lyric": rng.choice(short_lines) if short_lines else None,
            "days": days_left if days_left > 0 else None,
            "day_name": day_name, "date": date, "n_tracks": len(tracks),
            "track_no": tracks.index(t) + 1, "post_day": max(1, (day - release).days + 1),
            "ts": fmt_ts(moment["start"]) if moment else None, "link": cfg.get("link"),
        }

    def pick_moment(t, want_len):
        a = analyses[t["title"]]
        ms = a["moments"]
        def length(m):
            return m["end"] - m["start"]
        pool = [m for m in ms if abs(length(m) - want_len) <= 4] or ms
        pool.sort(key=lambda m: (moment_use[(t["title"], m["start"], round(length(m)))], -m["score"]))
        m = pool[0] if rng.random() < 0.8 else rng.choice(pool[: max(1, min(3, len(pool)))])
        moment_use[(t["title"], m["start"], round(length(m)))] += 1
        return m

    def eligible_templates(t):
        lyr = materials.get("lyrics", {}).get(t["title"], {})
        out = {}
        for k, w in TEMPLATE_W.items():
            if k == "lyric" and not (lyr.get("synced") or lyr.get("lines")):
                continue
            if k == "photo_beats" and materials.get("photos", 0) < 2:
                continue
            if k == "clip_cut" and materials.get("clips", 0) < 1:
                continue
            if k == "dump" and materials.get("footage", 0) < 4:
                continue
            if k == "lyric" and lyr.get("synced"):
                w *= 1.3
            out[k] = w * perf.get("template", {}).get(k, 1.0)
        return out

    def pick_hook(t, day_i, day, phase, moment, template, lang):
        ctx = ctx_for(t, day, phase, moment, lang)
        cands = []
        for ph, kind, text in banks.HOOKS[lang]:
            if ph not in ("any", phase):
                continue
            if kind == "drop" and moment["kind"] != "drop":
                continue
            if kind == "wait" and moment["kind"] not in ("drop", "intro", "quiet"):
                continue
            if "{ts}" in text and template not in ("waveform",) and rng.random() < 0.7:
                continue
            if kind == "lyric" and template == "lyric":
                continue
            f = fill(text, ctx)
            if not f:
                continue
            last = hook_last.get(f, -99)
            if day_i - last < 6:
                continue
            w = perf.get("hook_kind", {}).get(kind, 1.0) * (1.6 if kind in ("story", "compare", "tease") else 1.0)
            w *= 1.0 / (1 + 0.15 * sum(1 for x in items if x["hook"] == f))
            cands.append((f, kind, w))
        if not cands:
            return "", "none"
        f, kind, _ = rng.choices(cands, weights=[c[2] for c in cands], k=1)[0]
        hook_last[f] = day_i
        return f, kind

    def story_lines(t, day, phase, lang):
        ctx = ctx_for(t, day, phase, lang=lang)
        opts = []
        for ph, seq in banks.STORIES[lang]:
            if ph not in ("any", phase):
                continue
            filled = [fill(s, ctx) for s in seq]
            if all(filled):
                opts.append(filled)
        return rng.choice(opts) if opts else None

    def caption(platform, t, day, phase, hook_kind, lang):
        ctx = ctx_for(t, day, phase, lang=lang)
        lines = [l for l in (fill(x, ctx) for x in banks.CAPTION_LINES[lang][phase]) if l]
        line = rng.choice(lines) if lines else t["title"]
        ask = rng.choice(banks.ASK_LINES[lang]) if hook_kind != "ask" else ""
        tags = list(loc(cfg, "hashtags", lang) or cfg.get("hashtags", []))[:3]
        if cfg.get("album"):
            tags.append(re.sub(r"\W", "", cfg["album"]).lower())
        tagstr = " ".join("#" + x.lstrip("#") for x in tags[:4])
        cta_t = banks.CTA[lang][phase][platform]
        cta = fill(cta_t, ctx) or cta_t.split(":")[0]
        if platform == "tiktok":
            sep = " " if line.endswith(("?", "!")) else ". "
            return {"caption": f"{line}{sep}{ask + ' ' if ask else ''}{cta}\n{tagstr}".strip()}
        if platform == "reels":
            end = "" if line.endswith(("?", "!")) else "."
            return {"caption": f"{line[0].upper() + line[1:]}{end}\n\n{(ask[0].upper() + ask[1:] + chr(10)) if ask else ''}{cta}\n\n{tagstr}"}
        title = f"{t['title']} - {cfg.get('artist', '')} ({line})"
        if len(title) > 90:
            title = f"{t['title']} - {cfg.get('artist', '')}"
        desc = (f"{t['title']} de {cfg.get('artist', '')}, del álbum {cfg.get('album', '')}." if lang == "es"
                else f"{t['title']} by {cfg.get('artist', '')}, from the album {cfg.get('album', '')}.")
        return {"title": title + " #shorts", "description": f"{desc}\n{cta}\n{tagstr}"}

    day = start
    day_i = 0
    while day <= end:
        phase = phase_of(day, release)
        days_left = (release - day).days
        n = rates["tiktok"]
        tw = track_weights(phase)
        for k in range(n):
            t = _wchoice(rng, tracks, tw)
            lang = _wchoice(rng, list(langs), list(langs.values()))
            special = None
            if k == 0 and phase == "pre" and days_left in COUNTDOWN_DAYS:
                special = "countdown"
            want_len = rng.choices([9, 15, 22, 30], weights=[4, 4, 1.5, 0.8])[0]
            for attempt in range(12):
                m = pick_moment(t, 15 if special else want_len)
                if special:
                    template = "countdown"
                else:
                    el = eligible_templates(t)
                    today_t, yday_t = template_recent[day_i], template_recent[day_i - 1]
                    el2 = {kk: w * (0.4 if kk in yday_t else 1.0) for kk, w in el.items() if kk not in today_t}
                    el = el2 or el
                    template = _wchoice(rng, list(el), list(el.values()))
                hook, kind = ("", "countdown") if template in ("countdown",) else pick_hook(t, day_i, day, phase, m, template, lang)
                key = (t["title"], round(m["start"], 1), round(m["end"], 1), template, hook)
                if key not in used_keys:
                    break
            used_keys.add(key)
            template_recent[day_i].append(template)
            style = {"hook_style": _wchoice(rng, list(HOOK_STYLE_W), list(HOOK_STYLE_W.values())),
                     "font_set": rng.choice(FONT_SETS), "pulse_mode": rng.choice(["square", "square", "full"]),
                     "lyric_bg": rng.choice(["cover", "photo"]) if materials.get("photos", 0) else "cover",
                     "palette": rng.choice(label_pals) if rng.random() < palette_mix else "cover", "lang": lang}
            if template == "countdown":
                words = banks.CARD[lang]
                short = banks.date_words(release, days_left, lang)[2]
                style.update({"days": days_left, "when": words["out"].format(date=short),
                              "unit": words["day"] if days_left == 1 else words["days"]})
            if template == "text_story":
                lines = story_lines(t, day, phase, lang)
                if not lines:
                    template = "vinyl"
                    hook, kind = pick_hook(t, day_i, day, phase, m, template, lang)
                else:
                    style["lines"] = lines
                    hook, kind = "", "story"
            vid = f"{day.isoformat()}-{k + 1}"
            item = {"id": vid, "day": day.isoformat(), "phase": phase, "track": t["title"],
                    "t0": m["start"], "t1": m["end"], "moment_kind": m["kind"], "template": template,
                    "hook": hook, "hook_kind": kind, "seed": rng.randrange(1 << 30), **style}
            items.append(item)
            posts.append({"day": day.isoformat(), "time": TIMES["tiktok"][k % len(TIMES["tiktok"])],
                          "platform": "tiktok", "media": vid, **caption("tiktok", t, day, phase, kind, lang)})
        day += dt.timedelta(days=1)
        day_i += 1

    # cross-post: Shorts reuse yesterday's TikToks, Reels the day before's (IG-friendly templates first)
    by_day = defaultdict(list)
    for it in items:
        by_day[it["day"]].append(it)
    ig_pref = ["dump", "clip_cut", "photo_beats", "lyric", "pulse", "text_story", "vinyl", "ring", "bars", "waveform", "countdown"]
    day = start
    while day <= end:
        phase = phase_of(day, release)
        y1 = by_day.get((day - dt.timedelta(days=1)).isoformat(), [])
        y2 = by_day.get((day - dt.timedelta(days=2)).isoformat(), [])
        today = by_day.get(day.isoformat(), [])
        for k, it in enumerate((y1 or today)[: rates["shorts"]]):
            t = by_title[it["track"]]
            posts.append({"day": day.isoformat(), "time": TIMES["shorts"][k % 4], "platform": "shorts",
                          "media": it["id"], **caption("shorts", t, day, phase, it["hook_kind"], it["lang"])})
        src = sorted(y2 or y1 or today, key=lambda x: ig_pref.index(x["template"]))
        for k, it in enumerate(src[: rates["reels"]]):
            t = by_title[it["track"]]
            posts.append({"day": day.isoformat(), "time": TIMES["reels"][k % 3], "platform": "reels",
                          "media": it["id"], **caption("reels", t, day, phase, it["hook_kind"], it["lang"])})
        # stories: one card + today's videos
        for k in range(rates["stories"]):
            if k == 0:
                media = f"card-{'countdown' if phase == 'pre' else 'outnow'}-{day.isoformat()}"
                note = "Add a link sticker (pre-save)" if phase == "pre" else "Add a link sticker (listen)"
            else:
                pick = today[(k - 1) % max(1, len(today))] if today else None
                if not pick:
                    continue
                media = pick["id"]
                note = rng.choice(banks.STORY_NOTES["en"])
            posts.append({"day": day.isoformat(), "time": TIMES["stories"][k % 4], "platform": "stories",
                          "media": media, "caption": "", "note": note})
        day += dt.timedelta(days=1)
    posts.sort(key=lambda p: (p["day"], p["time"], p["platform"]))
    return {"items": items, "posts": posts, "release": release.isoformat(), "start": start.isoformat(),
            "end": end.isoformat(), "card_lang": max(langs, key=langs.get)}
