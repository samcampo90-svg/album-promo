"""Still images: story cards (1080x1920) and feed cards (1080x1350)."""
import cv2
import numpy as np

from . import banks
from . import core as C


def _base(cover, w, h, dim=0.45):
    big = C.blurred_bg(cover, w, h, scale=1.0, dim=dim)
    return big[:h, :w].copy()


def countdown_card(cover, pal, days, album, artist, date_str, font_set="condensed", w=1080, h=1920, lang="en"):
    head, body, upper = C.FONT_SETS[font_set]
    img = _base(cover, w, h)
    S = 560
    cov = C.with_shadow(C.bgr_to_rgba(C.cover_fit(cover, S, S), C.rounded_mask(S, 22)), 40, (0, 22), 0.6)
    C.paste(img, cov, (w - cov.shape[1]) // 2, 300)
    num = C.text_layer(str(days), head, 900, 420, 380, 100, color=(255, 255, 255), shadow=16)
    C.paste(img, num, (w - num.shape[1]) // 2, 940)
    words = banks.CARD[lang]
    u = C.text_layer((words["day"] if days == 1 else words["days"]) + " " + words["until"].format(album=album), head, 900, 200, 80, 34,
                     color=pal["vivid"], shadow=8, upper=True)
    C.paste(img, u, (w - u.shape[1]) // 2, 1340)
    s = C.text_layer(f"{artist}  ·  {date_str}", "Inter_600SemiBold.ttf", 900, 80, 42, 26, shadow=8)
    C.paste(img, s, (w - s.shape[1]) // 2, 1500)
    return img


def outnow_card(cover, pal, album, artist, font_set="condensed", w=1080, h=1920, lang="en"):
    head, body, upper = C.FONT_SETS[font_set]
    img = _base(cover, w, h)
    S = 860
    cov = C.with_shadow(C.bgr_to_rgba(C.cover_fit(cover, S, S), C.rounded_mask(S, 24)), 50, (0, 28), 0.6)
    C.paste(img, cov, (w - cov.shape[1]) // 2, 330)
    t = C.text_layer(banks.CARD[lang]["outnow"], head, 900, 200, 150, 60, color=(255, 255, 255), shadow=14, upper=True)
    C.paste(img, t, (w - t.shape[1]) // 2, 1270)
    s = C.text_layer(f"{album}  ·  {artist}", "Inter_600SemiBold.ttf", 900, 120, 46, 26, color=pal["vivid"] if np.mean(pal["vivid"]) > 90 else (255, 255, 255), shadow=8)
    C.paste(img, s, (w - s.shape[1]) // 2, 1460)
    return img


def lyric_card(cover, pal, line, song, artist, font_set="serif", w=1080, h=1350, bg=None):
    head, body, upper = C.FONT_SETS[font_set]
    img = _base(bg if bg is not None else cover, w, h, dim=0.38)
    t = C.text_layer(f"“{line}”", head, 900, int(h * 0.55), 104, 40, color=(255, 255, 255), shadow=14, upper=upper)
    C.paste(img, t, (w - t.shape[1]) // 2, (h - t.shape[0]) // 2 - 60)
    s = C.text_layer(f"{song}  ·  {artist}", "Inter_600SemiBold.ttf", 900, 80, 38, 24, color=(225, 225, 225), shadow=8)
    C.paste(img, s, (w - s.shape[1]) // 2, h - 230)
    return img


def save(img, path, q=92):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return path
