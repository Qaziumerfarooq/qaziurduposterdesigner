"""HarfBuzz + FreeType based shaping/rasterizer for Urdu/Arabic text.

Used as a fallback renderer for fonts whose cmap does not expose the
Arabic Presentation-Forms block (e.g. Jameel Noori Nastaleeq, KFGQPC
Uthmanic Hafs), which the arabic_reshaper + bidi pipeline cannot draw.

Shapes base (logical) text with HarfBuzz (full GSUB/GPOS/bidi) and
rasterizes the resulting glyphs with FreeType, returning a transparent
RGBA image and its advance metrics.

Font files and already-loaded HarfBuzz faces are cached so repeated
renders (per-preview refresh, big font sizes) do not re-parse the
10+ MB TTF files on every call.
"""
import functools

import uharfbuzz as hb
import freetype
from PIL import Image


# --- per-process caches -------------------------------------------------

@functools.lru_cache(maxsize=16)
def _hb_blob(path):
    return hb.Blob.from_file_path(path)


@functools.lru_cache(maxsize=16)
def _hb_face(path):
    blob = _hb_blob(path)
    return hb.Face(blob)


@functools.lru_cache(maxsize=16)
def _ft_face(path):
    return freetype.Face(path)


def clear_caches():
    """Drop cached faces (useful after deleting/replacing font files)."""
    _hb_blob.cache_clear()
    _hb_face.cache_clear()
    _ft_face.cache_clear()


def _font_unit_scale(face, size):
    upem = face.upem or 1000
    return size / float(upem)


def shape(path, text, size):
    """Run HarfBuzz shaping on logical text. Returns (hbfont, buffer, face, upem)."""
    face = _hb_face(path)
    upem = face.upem or 1000
    hbf = hb.Font(face)
    hbf.scale = (int(size * 64), int(size * 64))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbf, buf)
    return hbf, buf, face, upem


def measure(path, text, size):
    """Return (w, h) in pixels of shaped text (without rasterizing glyphs)."""
    _, buf, face, upem = shape(path, text, size)
    pen = 0.0
    for p in buf.glyph_positions:
        pen += p.x_advance / 64.0
    # Estimate line height cheaply (no glyph rasterization): the classic
    # calligraphy fonts are very tall, so reserve generous vertical room.
    h = int(size * 1.9) + 4
    return max(pen, 1.0), h


def render(path, text, size, fill, alpha=255):
    """Render shaped text to a transparent RGBA image aligned at top-left.

    fill is an (r, g, b) tuple. Returns an RGBA Image and (advance_w, w, h).
    """
    _, buf, face, upem = shape(path, text, size)
    ft = _ft_face(path)
    ft.set_char_size(int(size * 64))

    # Single pass: load every glyph once, keep the pixmaps for compositing.
    info_pos = list(zip(buf.glyph_infos, buf.glyph_positions))
    pen_x = 0.0
    min_top = 10 ** 9
    max_h = 0
    items = []  # (grey_image | None, x_offset, top, advance)
    for info, p in info_pos:
        gid = info.codepoint
        ft.load_glyph(gid, freetype.FT_LOAD_RENDER)
        bmp = ft.glyph.bitmap
        top = ft.glyph.bitmap_top
        rows = bmp.rows
        pen_x += p.x_advance / 64.0
        if bmp.width and rows:
            raw = bytes(bmp.buffer)
            grey = Image.frombytes("L", (bmp.width, rows), raw)
            items.append((grey, p.x_offset / 64.0, top, p.x_advance / 64.0))
        else:
            items.append((None, p.x_offset / 64.0, top, p.x_advance / 64.0))
        min_top = min(min_top, top)
        max_h = max(max_h, rows + top)

    pad = 2
    W = max(int(pen_x), 1) + pad * 2
    H = max(int(abs(min_top) + max_h), size) + pad * 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    r, g, b = fill
    baseline = pad + abs(min_top)
    x = pad
    for grey, off, top, adv in items:
        if grey is not None:
            # freetype glyph pixmap: value 0 = ink (background transparent).
            # Build a coverage mask: opaque where ink (0 -> 255).
            mask = grey.point(lambda v: 255 - v)
            img.paste((r, g, b), (int(x + off), int(baseline - top)), mask)
        x += adv

    if alpha != 255:
        a = img.getchannel("A").point(lambda v: int(v * alpha / 255))
        img.putalpha(a)
    return img, pen_x


def render_segments(segments, size, fill, alpha=255):
    """Combine multiple (path, text) shaped runs on one canvas left-to-right.

    Returns a single RGBA image and (total_w, h, baseline_top).
    """
    imgs = []
    for path, text in segments:
        im, adv = render(path, text, size, fill, 255)
        imgs.append((im, adv))
    # stack vertically aligned by top
    W = int(sum(adv for _, adv in imgs)) + 4
    H = max(im.height for im, _ in imgs) + 2
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x = 2
    for im, adv in imgs:
        out.alpha_composite(im, (x, 1))
        x += adv
    total_h = max(im.height for im, _ in imgs)
    return out, (x - 2, total_h)