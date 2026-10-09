"""Writes the phone-friendly posting calendar (an HTML page for publishing as an
artifact) for a date range, plus files.json mapping published paths to media."""
import datetime as dt
import json
from pathlib import Path

from . import core as C


def _hex(bgr):
    b, g, r = bgr
    return f"#{r:02x}{g:02x}{b:02x}"


def _lum(bgr):
    b, g, r = [x / 255 for x in bgr]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


PLATFORM = {"tiktok": "TikTok", "shorts": "YouTube Shorts", "reels": "Instagram Reels", "stories": "Instagram Story"}


def write_calendar(pr, plan, a: dt.date, b: dt.date, label=None):
    cfg = pr.cfg
    media_dir = pr.out / "media"
    items = {it["id"]: it for it in plan["items"]}
    posts = [p for p in plan["posts"] if a <= dt.date.fromisoformat(p["day"]) <= b]
    files = {}
    out_posts = []
    for p in posts:
        mid = p["media"]
        is_card = mid.startswith("card-")
        src = media_dir / (f"{mid}.jpg" if is_card else f"{mid}.mp4")
        if not src.exists():
            continue
        pub = f"media/{src.name}"
        files[pub] = str(src)
        thumb = None
        if not is_card:
            th = media_dir / f"{mid}.jpg"
            if th.exists():
                files[f"media/{th.name}"] = str(th)
                thumb = f"media/{th.name}"
        it = items.get(mid)
        info = None
        if it:
            info = {"track": it["track"], "range": f"{int(it['t0'] // 60)}:{int(it['t0'] % 60):02d}–{int(it['t1'] // 60)}:{int(it['t1'] % 60):02d}",
                    "template": it["template"], "hook": it.get("hook") or " / ".join(it.get("lines", [])) or ""}
        pid = f"{p['day']}_{p['platform']}_{p['time'].replace(':', '')}_{mid[-1] if not is_card else 'c'}"
        out_posts.append({"id": pid, "day": p["day"], "time": p["time"], "platform": p["platform"],
                          "kind": "image" if is_card else "video", "src": pub, "thumb": thumb or pub,
                          "caption": p.get("caption", ""), "title": p.get("title", ""),
                          "description": p.get("description", ""), "note": p.get("note", ""), "info": info,
                          "filename": f"{p['day']}-{p['platform']}-{p['time'].replace(':', '')}{'.jpg' if is_card else '.mp4'}"})
    cover = C.load_image(pr.cover_path())
    pal = C.palette(cover)
    acc = pal["vivid"]
    cov_small = pr.out / "cover-256.jpg"
    import cv2
    cv2.imwrite(str(cov_small), C.cover_fit(cover, 256, 256), [cv2.IMWRITE_JPEG_QUALITY, 88])
    files["cover.jpg"] = str(cov_small)
    data = {"artist": cfg.get("artist", ""), "album": cfg.get("album", ""), "release": plan["release"],
            "link": cfg.get("link", ""), "from": a.isoformat(), "to": b.isoformat(), "posts": out_posts,
            "platforms": PLATFORM}
    html = TEMPLATE
    html = html.replace("__TITLE__", f"{cfg.get('album', 'Album')} Rollout")
    html = html.replace("__ACCENT__", _hex(acc)).replace("__ON_ACCENT__", "#111014" if _lum(acc) > 0.35 else "#ffffff")
    html = html.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    out_dir = pr.out / "calendar"
    out_dir.mkdir(exist_ok=True)
    page = out_dir / "rollout.html"
    page.write_text(html)
    (out_dir / "files.json").write_text(json.dumps(files, indent=0))
    size = sum(Path(v).stat().st_size for v in files.values())
    print(f"{len(out_posts)} posts, {len(files)} files, {size / 1e6:.1f} MB")
    return page


TEMPLATE = r"""<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;900&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: a tour-week run sheet. Date rail across the top, the chosen day's posts as a running order by time. */
:root {
  --bg: #f1f0f3; --surface: #ffffff; --ink: #18161d; --muted: #67636f; --line: #dddae3;
  --accent: __ACCENT__; --on-accent: __ON_ACCENT__;
  --tiktok: #18161d; --shorts: #c62d2d; --reels: #b0337a; --stories: #b7791f; --done: #2f7d4f;
  --display: "Big Shoulders Display", "Arial Narrow", "Helvetica Neue", sans-serif;
  --body: "Hanken Grotesk", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #111015; --surface: #1b1a21; --ink: #f0eef4; --muted: #a3a0ad; --line: #2d2b35;
  --tiktok: #f0eef4; --shorts: #ff6b6b; --reels: #f07ab8; --stories: #f2b04c; --done: #5cc98a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #111015; --surface: #1b1a21; --ink: #f0eef4; --muted: #a3a0ad; --line: #2d2b35;
  --tiktok: #f0eef4; --shorts: #ff6b6b; --reels: #f07ab8; --stories: #f2b04c; --done: #5cc98a; color-scheme: dark }
* { box-sizing: border-box }
body { background: var(--bg); color: var(--ink); font: 15px/1.5 var(--body); margin: 0 }
.wrap { max-width: 760px; margin: 0 auto; padding-inline: 16px; padding-block: 20px 64px; display: grid; gap: 20px }
header { display: grid; grid-template-columns: 72px 1fr; gap: 14px; align-items: center }
header img { width: 72px; height: 72px; border-radius: 6px; object-fit: cover; display: block }
h1 { font: 900 clamp(34px, 8vw, 52px)/0.92 var(--display); text-transform: uppercase; letter-spacing: 0.01em; margin: 0; text-wrap: balance }
.meta { color: var(--muted); font-size: 14px; margin-top: 4px }
.meta b { color: var(--ink); font-weight: 600 }
.count { font: 600 13px var(--mono); display: flex; gap: 10px; flex-wrap: wrap; align-items: center }
.bar { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; flex: 1 1 160px; min-width: 120px }
.bar i { display: block; height: 100%; background: var(--accent); width: 0; transition: width .3s }
details.howto { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px }
details.howto summary { cursor: pointer; font-weight: 600 }
details.howto ol { margin: 10px 0 2px; padding-left: 20px; display: grid; gap: 6px; color: var(--ink) }
.rail { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin }
.rail button { flex: 0 0 auto; width: 64px; padding: 8px 0 7px; border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  border-radius: 10px; cursor: pointer; display: grid; justify-items: center; gap: 1px; font: inherit }
.rail button .wd { font: 600 11px var(--mono); text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted) }
.rail button .dn { font: 900 26px/1 var(--display) }
.rail button .left { font: 600 11px var(--mono); color: var(--muted) }
.rail button.rel { border-color: var(--accent) }
.rail button[aria-pressed="true"] { background: var(--accent); color: var(--on-accent); border-color: var(--accent) }
.rail button[aria-pressed="true"] .wd, .rail button[aria-pressed="true"] .left { color: var(--on-accent) }
.rail button:focus-visible, .btn:focus-visible, .thumb:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px }
.dayhead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap }
.dayhead h2 { font: 700 28px/1 var(--display); text-transform: uppercase; letter-spacing: 0.02em; margin: 0 }
.phase { font: 600 12px var(--mono); text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted) }
.list { display: grid; gap: 12px }
.post { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px; display: grid; gap: 12px }
.post.done { opacity: .62 }
.top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap }
.time { font: 600 15px var(--mono) }
.plat { font: 600 12px var(--mono); letter-spacing: 0.04em; padding: 2px 8px; border-radius: 999px; border: 1.5px solid currentColor }
.plat.tiktok { color: var(--tiktok) } .plat.shorts { color: var(--shorts) } .plat.reels { color: var(--reels) } .plat.stories { color: var(--stories) }
.state { margin-left: auto; font: 600 12px var(--mono); color: var(--done) }
.body { display: grid; grid-template-columns: 96px 1fr; gap: 14px; align-items: start }
.thumb { width: 96px; aspect-ratio: 9 / 16; border-radius: 8px; overflow: hidden; background: var(--line); border: 0; padding: 0; cursor: pointer; position: relative; max-width: 100% }
.thumb img, .thumb video { width: 100%; height: 100%; object-fit: cover; display: block }
.thumb .play { position: absolute; inset: auto 6px 6px auto; font: 600 11px var(--mono); background: rgba(0,0,0,.6); color: #fff; padding: 2px 6px; border-radius: 4px }
.player { width: 100%; max-width: 320px; aspect-ratio: 9 / 16; border-radius: 10px; background: #000; display: block }
.text { min-width: 0; display: grid; gap: 8px }
.cap { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px }
.lbl { font: 600 11px var(--mono); text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted) }
.info { font: 400 12px/1.5 var(--mono); color: var(--muted); overflow-wrap: anywhere }
.note { font-weight: 600 }
.actions { display: flex; gap: 8px; flex-wrap: wrap }
.btn { font: 600 14px var(--body); padding: 9px 14px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); cursor: pointer }
.btn.primary { background: var(--accent); color: var(--on-accent); border-color: var(--accent) }
.btn.ok { background: var(--done); color: var(--surface); border-color: var(--done) }
.stats { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 14px }
.stats input { width: 110px; font: 600 14px var(--mono); padding: 7px 9px; border-radius: 8px; border: 1px solid var(--line); background: var(--bg); color: var(--ink) }
.msg { font-size: 13px; color: var(--muted); min-height: 1em }
.empty { color: var(--muted); padding: 24px 0 }
@media (max-width: 420px) { .body { grid-template-columns: 80px 1fr } .thumb { width: 80px } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important } }
</style>

<div class="wrap">
  <header>
    <img src="cover.jpg" alt="Album cover">
    <div>
      <h1 id="album"></h1>
      <div class="meta" id="meta"></div>
    </div>
  </header>
  <div class="count"><span id="progress"></span><div class="bar"><i id="barfill"></i></div></div>
  <details class="howto">
    <summary>How to post</summary>
    <ol>
      <li><b>Save video</b> puts the file on your device. On iPhone, choose <b>Save Video</b> in the share sheet so it lands in Photos.</li>
      <li>Upload it natively in the app, paste the caption with <b>Copy caption</b>, and add the song's official sound once it's live on TikTok and Instagram.</li>
      <li>Faster on a computer: schedule a whole day in TikTok Studio, YouTube Studio and Meta Business Suite (which can also share Reels to Facebook).</li>
      <li>Tap <b>Mark posted</b>. A day or two later, log the views on each post so the next batch leans into what's working.</li>
    </ol>
  </details>
  <nav class="rail" id="rail" aria-label="Days"></nav>
  <section>
    <div class="dayhead"><h2 id="dayname"></h2><span class="phase" id="phase"></span></div>
    <div class="list" id="list"></div>
  </section>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
(() => {
  const D = JSON.parse(document.getElementById("data").textContent);
  const $ = (id) => document.getElementById(id);
  const state = {};            // post id -> {posted, views, likes}
  let db = null, downloads = null;
  const release = new Date(D.release + "T00:00:00");
  const days = [];
  for (let d = new Date(D.from + "T00:00:00"); d <= new Date(D.to + "T00:00:00"); d.setDate(d.getDate() + 1)) days.push(new Date(d));
  const iso = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const todayIso = iso(new Date());
  let current = days.some((d) => iso(d) === todayIso) ? todayIso : iso(days[0]);

  $("album").textContent = D.album;
  const left = Math.round((release - new Date(todayIso + "T00:00:00")) / 864e5);
  const relStr = release.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  $("meta").innerHTML = "";
  const m1 = document.createElement("div");
  m1.textContent = D.artist + " · release " + relStr;
  const m2 = document.createElement("div");
  m2.innerHTML = left > 0 ? "<b>" + left + "</b> day" + (left === 1 ? "" : "s") + " to go" : left === 0 ? "<b>Release day</b>" : "<b>Out now</b> · day " + (1 - left) + " after release";
  $("meta").append(m1, m2);

  function postsFor(day) { return D.posts.filter((p) => p.day === day).sort((a, b) => a.time.localeCompare(b.time)); }

  function progress() {
    const total = D.posts.length;
    const done = D.posts.filter((p) => state[p.id]?.posted).length;
    $("progress").textContent = done + " of " + total + " posts done this batch";
    $("barfill").style.width = (total ? (100 * done / total) : 0) + "%";
  }

  function rail() {
    const r = $("rail");
    r.textContent = "";
    for (const d of days) {
      const id = iso(d);
      const ps = postsFor(id);
      const todo = ps.filter((p) => !state[p.id]?.posted).length;
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("aria-pressed", String(id === current));
      if (id === D.release) b.classList.add("rel");
      b.innerHTML = '<span class="wd"></span><span class="dn"></span><span class="left"></span>';
      b.querySelector(".wd").textContent = id === todayIso ? "today" : d.toLocaleDateString(undefined, { weekday: "short" });
      b.querySelector(".dn").textContent = d.getDate();
      b.querySelector(".left").textContent = todo ? todo + " left" : "done";
      b.addEventListener("click", () => { current = id; render(); });
      r.append(b);
    }
  }

  async function copy(text, msgEl) {
    try { await navigator.clipboard.writeText(text); msgEl.textContent = "Copied"; }
    catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.append(ta); ta.select();
      let ok = false; try { ok = document.execCommand("copy"); } catch (_) {}
      ta.remove();
      msgEl.textContent = ok ? "Copied" : "Select the text above and copy it";
    }
  }

  async function save(p, msgEl) {
    if (!downloads) { msgEl.textContent = "Saving isn't available in this view. Open the page in the Claude app or a browser."; return; }
    msgEl.textContent = "Preparing file…";
    try {
      const blob = await (await fetch(p.src)).blob();
      await downloads.save({ filename: p.filename, data: blob });
      msgEl.textContent = "Saved";
    } catch (e) {
      const code = e && e.code;
      msgEl.textContent = code === "declined" ? "Not saved" : code === "rate_limited" ? "Another save is open. Try again in a moment." : "Couldn't save this file here";
    }
  }

  async function writeState(p) {
    if (!db) return;
    try { await db.doc("posts/" + p.id).set({ ...state[p.id], day: p.day, platform: p.platform, media: p.src, at: new Date().toISOString() }); }
    catch (e) { /* keeps working locally for this visit */ }
  }

  function card(p) {
    const s = state[p.id] || {};
    const el = document.createElement("article");
    el.className = "post" + (s.posted ? " done" : "");
    const top = document.createElement("div");
    top.className = "top";
    top.innerHTML = '<span class="time"></span><span class="plat"></span><span class="state"></span>';
    top.querySelector(".time").textContent = p.time;
    const pl = top.querySelector(".plat");
    pl.classList.add(p.platform); pl.textContent = D.platforms[p.platform];
    top.querySelector(".state").textContent = s.posted ? "posted" : "";
    el.append(top);

    const body = document.createElement("div");
    body.className = "body";
    const th = document.createElement("button");
    th.className = "thumb"; th.type = "button";
    th.setAttribute("aria-label", p.kind === "video" ? "Play video" : "View image");
    const img = document.createElement("img");
    img.src = p.thumb; img.alt = ""; img.loading = "lazy";
    th.append(img);
    if (p.kind === "video") { const pb = document.createElement("span"); pb.className = "play"; pb.textContent = "play"; th.append(pb); }
    const text = document.createElement("div");
    text.className = "text";
    const viewer = document.createElement("div");
    th.addEventListener("click", () => {
      if (viewer.firstChild) { viewer.textContent = ""; return; }
      if (p.kind === "video") {
        const v = document.createElement("video");
        v.className = "player"; v.src = p.src; v.controls = true; v.playsInline = true; v.preload = "metadata";
        viewer.append(v); v.play().catch(() => {});
      } else {
        const im = document.createElement("img"); im.className = "player"; im.src = p.src; im.alt = "Story card"; viewer.append(im);
      }
    });
    const capText = p.platform === "shorts" ? p.title + "\n\n" + p.description : p.caption;
    if (p.platform === "shorts") {
      text.innerHTML = '<span class="lbl">Title</span><div class="cap t"></div><span class="lbl">Description</span><div class="cap d"></div>';
      text.querySelector(".t").textContent = p.title; text.querySelector(".d").textContent = p.description;
    } else if (p.caption) {
      const c = document.createElement("div"); c.className = "cap"; c.textContent = p.caption; text.append(c);
    }
    if (p.note) { const n = document.createElement("div"); n.className = "note"; n.textContent = p.note; text.append(n); }
    if (p.info) {
      const i = document.createElement("div"); i.className = "info";
      i.textContent = p.info.track + " " + p.info.range + " · " + p.info.template + (p.info.hook ? " · on screen: " + p.info.hook : "");
      text.append(i);
    }
    body.append(th, text);
    el.append(body, viewer);

    const msg = document.createElement("div"); msg.className = "msg";
    const actions = document.createElement("div"); actions.className = "actions";
    const bSave = document.createElement("button"); bSave.className = "btn primary"; bSave.type = "button";
    bSave.textContent = p.kind === "video" ? "Save video" : "Save image";
    bSave.addEventListener("click", () => save(p, msg));
    actions.append(bSave);
    if (capText) {
      const bCopy = document.createElement("button"); bCopy.className = "btn"; bCopy.type = "button";
      bCopy.textContent = p.platform === "shorts" ? "Copy title + description" : "Copy caption";
      bCopy.addEventListener("click", () => copy(capText, msg));
      actions.append(bCopy);
    }
    const bDone = document.createElement("button"); bDone.type = "button";
    bDone.className = "btn" + (s.posted ? " ok" : "");
    bDone.textContent = s.posted ? "Posted ✓" : "Mark posted";
    bDone.setAttribute("aria-pressed", String(!!s.posted));
    bDone.addEventListener("click", async () => {
      state[p.id] = { ...(state[p.id] || {}), posted: !(state[p.id]?.posted) };
      render(); await writeState(p);
    });
    actions.append(bDone);
    el.append(actions);

    if (s.posted && p.platform !== "stories") {
      const st = document.createElement("div"); st.className = "stats";
      const vid = "v-" + p.id, lid = "l-" + p.id;
      st.innerHTML = '<label for="' + vid + '">Views</label><input inputmode="numeric" id="' + vid + '"><label for="' + lid + '">Likes</label><input inputmode="numeric" id="' + lid + '">';
      const vi = st.querySelector("#" + CSS.escape(vid)), li = st.querySelector("#" + CSS.escape(lid));
      vi.value = s.views ?? ""; li.value = s.likes ?? "";
      const commit = async () => {
        const v = parseInt(vi.value.replace(/\D/g, ""), 10), l = parseInt(li.value.replace(/\D/g, ""), 10);
        const next = { ...(state[p.id] || {}), views: isNaN(v) ? null : v, likes: isNaN(l) ? null : l };
        if (next.views === state[p.id]?.views && next.likes === state[p.id]?.likes) return;
        state[p.id] = next; msg.textContent = "Saved stats"; await writeState(p);
      };
      vi.addEventListener("change", commit); li.addEventListener("change", commit);
      el.append(st);
    }
    el.append(msg);
    return el;
  }

  function render() {
    rail();
    progress();
    const d = new Date(current + "T00:00:00");
    $("dayname").textContent = d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
    const dl = Math.round((release - d) / 864e5);
    $("phase").textContent = dl > 0 ? dl + " days before release" : dl === 0 ? "release day" : "day " + (1 - dl) + " after release";
    const list = $("list");
    list.textContent = "";
    const ps = postsFor(current);
    if (!ps.length) { const e = document.createElement("p"); e.className = "empty"; e.textContent = "Nothing scheduled for this day."; list.append(e); return; }
    for (const p of ps) list.append(card(p));
  }

  render();

  if (window.claude && window.claude.use) {
    window.claude.use("downloads").then((x) => { downloads = x; });
    window.claude.use("db").then((x) => {
      db = x;
      if (!db) return;
      db.collection("posts").onSnapshot((snap) => {
        let changed = false;
        for (const doc of snap.docs) {
          const v = doc.data() || {};
          const cur = state[doc.id] || {};
          if (cur.posted !== v.posted || cur.views !== v.views || cur.likes !== v.likes) {
            state[doc.id] = { posted: !!v.posted, views: v.views ?? null, likes: v.likes ?? null }; changed = true;
          }
        }
        if (changed) render();
      }, () => {});
    });
  }
})();
</script>
"""
