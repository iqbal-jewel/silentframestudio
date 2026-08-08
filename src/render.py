"""Renders the daily 'on this day' card.

Trivia and fact posts are text-only; only the on_this_day slot gets an image,
to keep the 6-month content bank sustainable without per-post art.

Background is a colourful photo pulled from Pexels (query drawn from the
headline's keywords, e.g. "animation film"), with a bottom-weighted scrim so
text stays legible. Falls back to a procedural colour-wash gradient if
PEXELS_API_KEY is unset or the search comes back empty, so rendering never
hard-fails the pipeline.

    python -m src.render POST_ID "headline text" [--query "film reel"]
"""
import hashlib
import os
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
FONTS = ROOT / "fonts"
PHOTO_CACHE = ROOT / "photo_cache"

WIDTH, HEIGHT = 1080, 1080
MARGIN = 80
FG = "#FFFFFF"
ACCENT = "#E8A33D"  # film-reel gold, used when no photo is available

EYEBROW = "ON THIS DAY IN ANIMATION"
FOOTER = "Silent Frames Studio"

# Rotating gradient palettes for the no-photo fallback -- picked to feel like
# a colourful page rather than a single flat brand colour.
GRADIENTS = [
    ("#FF6B6B", "#4ECDC4"),
    ("#8E2DE2", "#4A00E0"),
    ("#F7971E", "#FFD200"),
    ("#00C9FF", "#92FE9D"),
    ("#F857A6", "#FF5858"),
    ("#43CBFF", "#9708CC"),
]

FONT_CANDIDATES = [
    FONTS / "Poppins-Bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
]


def _font_path():
    for c in FONT_CANDIDATES:
        if c.exists():
            return c
    return None


def _font(size):
    p = _font_path()
    if p is None:
        return ImageFont.load_default()
    return ImageFont.truetype(str(p), size)


def _wrap(draw, text, font, max_width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, max_width, max_height, start, minimum=32):
    size = start
    while size > minimum:
        font = _font(size)
        lines = _wrap(draw, text, font, max_width)
        line_h = int(size * 1.32)
        if len(lines) * line_h <= max_height:
            return font, lines, line_h
        size -= 2
    font = _font(minimum)
    return font, _wrap(draw, text, font, max_width), int(minimum * 1.32)


def _cover(img, w, h):
    src_ratio, dst_ratio = img.width / img.height, w / h
    if src_ratio > dst_ratio:
        new_w = int(img.height * dst_ratio)
        box = ((img.width - new_w) // 2, 0, (img.width + new_w) // 2, img.height)
    else:
        new_h = int(img.width / dst_ratio)
        box = (0, (img.height - new_h) // 2, img.width, (img.height + new_h) // 2)
    return img.resize((w, h), Image.LANCZOS, box=box)


def _scrim(w, h, strength=0.82):
    grad = Image.new("L", (1, h), 0)
    px = grad.load()
    start = int(h * 0.30)
    span = h - start
    for y in range(start, h):
        t = (y - start) / span
        px[0, y] = int(255 * strength * t * t)
    top_start = int(h * 0.22)
    for y in range(0, top_start):
        t = 1 - (y / top_start)
        px[0, y] = max(px[0, y], int(140 * t * t))
    return grad.resize((w, h))


def _pexels_photo(query: str, post_id: str) -> Image.Image | None:
    """Fetch a colourful landscape photo for query, cached to disk by post_id."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None

    PHOTO_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = PHOTO_CACHE / f"{post_id}.jpg"
    if cache_path.exists():
        return Image.open(cache_path).convert("RGB")

    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": query, "per_page": 15, "orientation": "square"},
            timeout=20,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return None
        # Deterministic pick per post_id so re-runs don't fetch a different photo.
        idx = int(hashlib.sha1(post_id.encode()).hexdigest(), 16) % len(photos)
        url = photos[idx]["src"]["large"]
        img_resp = requests.get(url, timeout=30)
        img_resp.raise_for_status()
        cache_path.write_bytes(img_resp.content)
        return Image.open(cache_path).convert("RGB")
    except requests.RequestException:
        return None


def _gradient(post_id: str) -> Image.Image:
    idx = int(hashlib.sha1(post_id.encode()).hexdigest(), 16) % len(GRADIENTS)
    c1, c2 = GRADIENTS[idx]

    def hexrgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    r1, g1, b1 = hexrgb(c1)
    r2, g2, b2 = hexrgb(c2)
    base = Image.new("RGB", (WIDTH, HEIGHT))
    px = base.load()
    for y in range(HEIGHT):
        t = y / HEIGHT
        row = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
        for x in range(WIDTH):
            px[x, y] = row
    return base


def render(headline: str, image_name: str, query: str = "animation film",
           out_dir: Path = IMAGES) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    post_id = Path(image_name).stem

    photo = _pexels_photo(query, post_id)
    base = _cover(photo, WIDTH, HEIGHT) if photo else _gradient(post_id)
    base.paste(Image.new("RGB", (WIDTH, HEIGHT), "black"), (0, 0), _scrim(WIDTH, HEIGHT))

    draw = ImageDraw.Draw(base)
    inner = WIDTH - 2 * MARGIN

    ef = _font(40)
    ew = draw.textlength(EYEBROW, font=ef)
    draw.text(((WIDTH - ew) / 2, MARGIN), EYEBROW, font=ef, fill=ACCENT)

    ff = _font(34)
    fw = draw.textlength(FOOTER, font=ff)
    fy = HEIGHT - MARGIN - 34
    draw.text(((WIDTH - fw) / 2, fy), FOOTER, font=ff, fill=ACCENT)

    top = MARGIN + 40 + 48
    bottom = fy - 48
    font, lines, line_h = _fit(draw, headline, inner, bottom - top, 72)
    block = len(lines) * line_h
    y = top + (bottom - top - block) / 2
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((WIDTH - w) / 2, y), line, font=font, fill=FG)
        y += line_h

    path = out_dir / image_name
    base.save(path, "JPEG", quality=90, optimize=True, progressive=True)
    return path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("post_id")
    ap.add_argument("headline")
    ap.add_argument("--query", default="animation film")
    args = ap.parse_args()
    path = render(args.headline, f"{args.post_id}.jpg", query=args.query)
    print(f"rendered -> {path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
