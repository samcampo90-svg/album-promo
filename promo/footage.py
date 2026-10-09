"""Phone footage ingest: turns a folder of random photos and videos (HEIC, JPG,
PNG, MOV, MP4, any orientation) into a curated, scored library the video
templates can cut to music.

  python3 -m promo.footage <project_dir> [source_folder]

Steps: normalize (rotation, HEIC, HEVC -> 1080p H.264 proxies), score (sharpness,
exposure, color, motion, shake), find each video's best 2-5 s segments, drop
near-duplicates, flag likely screenshots, tag mood (night/day, warm/cool), and
write a contact sheet so the selection can be approved before anything posts.
Originals are never modified."""
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:  # HEIC just won't load
    pass

IMG = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
VID = {".mov", ".mp4", ".m4v", ".3gp", ".webm", ".mkv"}
SCREEN_SIZES = {(1170, 2532), (1179, 2556), (1290, 2796), (1284, 2778), (1125, 2436), (1242, 2688), (828, 1792),
                (750, 1334), (1080, 1920), (1080, 2340), (1080, 2400), (1440, 3200), (1440, 3120)}


def _dhash(gray, n=16):
    s = cv2.resize(gray, (n + 1, n), interpolation=cv2.INTER_AREA)
    bits = (s[:, 1:] > s[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def _ham(a, b):
    return bin(a ^ b).count("1")


def _frame_stats(bgr):
    small = cv2.resize(bgr, (360, int(360 * bgr.shape[0] / bgr.shape[1])), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
    mean = float(g.mean())
    clipped = float(((g < 8) | (g > 247)).mean())
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    sat = float(hsv[..., 1].mean())
    b, gch, r = [float(small[..., i].mean()) for i in range(3)]
    warmth = (r - b) / 255.0
    return {"sharp": sharp, "bright": mean / 255.0, "clipped": clipped, "sat": sat / 255.0, "warmth": warmth}, g


def _quality(st):
    """0..1 usability score for one frame."""
    sharp = min(1.0, np.log1p(st["sharp"]) / np.log1p(400))
    expo = 1.0 - min(1.0, abs(st["bright"] - 0.45) * 1.6) - st["clipped"] * 0.8
    return float(np.clip(0.55 * sharp + 0.3 * expo + 0.15 * min(1.0, st["sat"] * 2.5), 0, 1))


def _mood(st):
    night = st["bright"] < 0.3
    return {"night": bool(night), "warm": bool(st["warmth"] > 0.04), "bright": round(st["bright"], 3),
            "sat": round(st["sat"], 3), "warmth": round(st["warmth"], 3)}


def _focus_point(bgr):
    """Where the interesting detail is (0..1 x, y): centre of edge energy, pulled toward the middle."""
    g = cv2.cvtColor(cv2.resize(bgr, (160, int(160 * bgr.shape[0] / bgr.shape[1]))), cv2.COLOR_BGR2GRAY).astype(np.float32)
    e = cv2.GaussianBlur(np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1)), (0, 0), 6)
    ys, xs = np.mgrid[0:e.shape[0], 0:e.shape[1]]
    tot = e.sum() + 1e-6
    fx, fy = float((xs * e).sum() / tot / e.shape[1]), float((ys * e).sum() / tot / e.shape[0])
    return round(0.5 + 0.6 * (fx - 0.5), 3), round(0.5 + 0.6 * (fy - 0.5), 3)


def load_photo(path, max_side=2400, with_size=False):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    size = im.size
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    out = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    return (out, size) if with_size else out


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,codec_name:stream_side_data=rotation:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    j = json.loads(out.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    rot = 0
    for sd in st.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = st.get("width", 0), st.get("height", 0)
    if abs(rot) in (90, 270):
        w, h = h, w
    return {"w": w, "h": h, "dur": float(j.get("format", {}).get("duration", 0) or 0), "codec": st.get("codec_name")}


def proxy(src, dst, short_side=1080):
    """Autorotated 30 fps H.264 proxy, short side 1080, original audio kept."""
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale='if(lt(iw,ih),{short_side},-2)':'if(lt(iw,ih),-2,{short_side})',fps=30,format=yuv420p"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                    str(dst)], check=True)
    return dst


def video_segments(path, seg=(2.0, 5.0)):
    """Score frames every 0.25 s; return the best non-overlapping 2-5 s windows."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(fps * 0.25)))
    stats, prev, i, frames = [], None, 0, 0
    first = None
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            st, g = _frame_stats(fr)
            motion = 0.0 if prev is None else float(np.abs(g.astype(np.int16) - prev.astype(np.int16)).mean() / 255)
            prev = g
            st["motion"] = motion
            st["t"] = i / fps
            stats.append(st)
            if first is None:
                first = fr
        i += 1
    cap.release()
    if not stats:
        return [], None, {}
    q = np.array([_quality(s) for s in stats])
    m = np.array([s["motion"] for s in stats])
    # motion: some is good (alive), too much is shake/whip
    mscore = np.clip(1 - np.abs(m - 0.04) / 0.08, 0, 1)
    score = 0.7 * q + 0.3 * mscore
    win_min, win_max = int(seg[0] / 0.25), int(seg[1] / 0.25)
    out, used = [], np.zeros(len(score), bool)
    if len(score) <= win_min:
        return [{"t0": 0.0, "t1": round(len(score) * 0.25, 2), "score": round(float(score.mean()), 3)}], first, stats[0]
    for _ in range(6):
        best, arg = -1, None
        for a in range(0, len(score) - win_min):
            if used[a:a + win_min].any():
                continue
            L = win_min
            while L < win_max and a + L < len(score) and not used[a + L] and score[a + L] > 0.45:
                L += 1
            s = float(score[a:a + L].mean()) * (0.9 + 0.1 * L / win_max)
            if s > best:
                best, arg = s, (a, L)
        if arg is None or best < 0.4:
            break
        a, L = arg
        used[a:a + L] = True
        out.append({"t0": round(stats[a]["t"], 2), "t1": round(stats[min(a + L, len(stats) - 1)]["t"], 2), "score": round(best, 3)})
    mid = stats[len(stats) // 2]
    return sorted(out, key=lambda s: -s["score"]), first, mid


def ingest(project: Path, source: Path = None):
    source = source or (project / "footage")
    work = project / "_work" / "footage"
    (work / "photos").mkdir(parents=True, exist_ok=True)
    (work / "videos").mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in IMG | VID
                   and not p.name.startswith("."))
    items, hashes = [], []
    for n, p in enumerate(files, 1):
        rec = {"id": f"f{n:04d}", "src": str(p.relative_to(source)), "flags": []}
        try:
            if p.suffix.lower() in IMG:
                im, (w, h) = load_photo(p, with_size=True)
                st, g = _frame_stats(im)
                rec.update({"kind": "photo", "w": w, "h": h, "quality": round(_quality(st), 3), "mood": _mood(st),
                            "focus": _focus_point(im)})
                if ((w, h) in SCREEN_SIZES and p.suffix.lower() == ".png") or re.search(r"screen ?shot|captura", p.name, re.I):
                    rec["flags"].append("screenshot")
                out = work / "photos" / f"{rec['id']}.jpg"
                cv2.imwrite(str(out), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
                rec["path"] = str(out)
                thumb_src = im
            else:
                info = probe(p)
                out = proxy(p, work / "videos" / f"{rec['id']}.mp4")
                segs, first, mid = video_segments(out)
                rec.update({"kind": "video", "w": info["w"], "h": info["h"], "dur": round(info["dur"], 2),
                            "segments": segs, "quality": round(max([s["score"] for s in segs] or [0]), 3),
                            "mood": _mood(mid) if mid else {}, "path": str(out)})
                if first is None:
                    raise ValueError("no frames")
                rec["focus"] = _focus_point(first)
                thumb_src = first
                g = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
            rec["orient"] = "vertical" if rec["h"] > rec["w"] * 1.1 else ("square" if rec["h"] > rec["w"] * 0.9 else "horizontal")
            dh = _dhash(g)
            dup = next((it for it, hh in hashes if _ham(dh, hh) <= 14 and it["kind"] == rec["kind"]), None)
            if dup is not None:
                rec["flags"].append(f"near-duplicate of {dup['id']}")
            hashes.append((rec, dh))
            if rec["quality"] < 0.35:
                rec["flags"].append("low quality")
            th = work / "thumbs" / f"{rec['id']}.jpg"
            th.parent.mkdir(exist_ok=True)
            t = cv2.resize(thumb_src, (240, int(240 * thumb_src.shape[0] / thumb_src.shape[1])), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(th), t, [cv2.IMWRITE_JPEG_QUALITY, 85])
            rec["thumb"] = str(th)
            rec["use"] = not rec["flags"]
        except Exception as e:  # unreadable file: record it, keep going
            rec.update({"kind": "error", "error": str(e)[:200], "use": False})
        items.append(rec)
        print(f"[{n}/{len(files)}] {rec['src']}: {rec.get('kind')} q={rec.get('quality')} {', '.join(rec['flags'])}")
    idx = {"source": str(source), "items": items}
    (work / "index.json").write_text(json.dumps(idx, indent=1))
    contact_sheet(items, work / "contact-sheet.jpg")
    return idx


def contact_sheet(items, out, cols=8):
    from .core import text_layer, paste
    cells = []
    for it in items:
        if not it.get("thumb"):
            continue
        im = cv2.imread(it["thumb"])
        cell = np.full((300, 240, 3), 24, np.uint8)
        h = min(260, im.shape[0])
        y0 = (260 - h) // 2
        cell[y0:y0 + h] = im[(im.shape[0] - h) // 2:(im.shape[0] - h) // 2 + h, :240]
        tag = it["id"] + (" ✗" if not it.get("use") else "") + (f" {it.get('dur', 0):.0f}s" if it["kind"] == "video" else "")
        lab = text_layer(tag, "SpaceMono_700Bold.ttf", 236, 34, 22, 14,
                         color=(120, 120, 255) if not it.get("use") else (230, 230, 230))
        paste(cell, lab, 2, 264)
        cells.append(cell)
    if not cells:
        return None
    rows = [np.hstack(cells[i:i + cols] + [np.zeros_like(cells[0])] * (cols - len(cells[i:i + cols])))
            for i in range(0, len(cells), cols)]
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out


if __name__ == "__main__":
    proj = Path(sys.argv[1]).resolve()
    src = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    idx = ingest(proj, src)
    ok = sum(1 for i in idx["items"] if i.get("use"))
    print(f"{len(idx['items'])} files, {ok} usable; contact sheet in _work/footage/contact-sheet.jpg")
