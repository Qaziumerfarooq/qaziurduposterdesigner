"""Qazi Urdu Poster Designer - platform independent core engine.

This module contains every rendering / composing feature of the desktop
app (tkinter) but with ZERO GUI dependencies, so it runs identically on
desktop and Android (Kivy). The Kivy UI (kivy_app.py) is a thin wrapper.

Features kept 1:1 with the original desktop app:
  - Background image upload / replace / blank canvas / card / colour
  - Multi-layer Urdu text labels (font, size, colour, rotation, opacity,
    arc/curved text, word spacing)
  - Overlay / logo images (uniform + independent W/H scale, flip,
    rotation, opacity, crop, remove-background, replace)
  - Layer ordering (to front / forward / backward / to back)
  - Persian/Arabic shaping via arabic_reshaper + bidi, optional
    HarfBuzz/FreeType fallback for fonts without presentation forms
  - Hit-testing (tap selection), element boxes, resize ratios
  - Save project (.qazip) / open project (embedded image + state)
  - Full-resolution render + fast preview render
"""
import os
import sys
import io
import re
import json
import base64
import functools
import math

from PIL import Image, ImageDraw, ImageFont

import urdu_text
from pdf_export import save_as_pdf

# Optional HarfBuzz + FreeType fallback renderer for fonts whose cmap does
# not expose Arabic Presentation-Forms (e.g. Jameel Noori Nastaleeq).
try:
    import urdu_render as _urdu_render
    _HB_AVAILABLE = True
except Exception:
    _HB_AVAILABLE = False


def log_error(msg):
    """Best-effort error logging (no crash when disks are locked)."""
    try:
        log_path = os.path.join(os.path.expanduser("~"), "QaziUrduPosterDesigner_error.log")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("=" * 60 + "\n")
            import traceback
            fh.write(str(msg) + "\n")
            fh.write(traceback.format_exc() + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------ dirs
def app_root_dir():
    """Directory containing the python source / bundled resources."""
    return os.path.dirname(os.path.abspath(__file__))


def user_data_dir():
    """Writable per-user dir (APPDATA on Windows; app-private on Android)."""
    if os.name == "nt" and os.environ.get("APPDATA"):
        return os.path.join(os.environ["APPDATA"], "QaziUrduPosterDesigner")
    return os.path.join(os.path.expanduser("~"), "QaziUrduPosterDesigner")


def user_font_dir():
    """Writable folder for downloaded / imported fonts."""
    d = os.path.join(user_data_dir(), "fonts")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def output_dir():
    """Writable folder for exported images / PDFs / projects."""
    d = os.path.join(user_data_dir(), "output")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _find_bundled_font_dir():
    """Locate a directory containing bundled TTF/OTF fonts."""
    base = app_root_dir()
    for cand in (os.path.join(base, "fonts"),
                 os.path.join(base, "_internal", "fonts"),
                 os.path.join(base, "..", "fonts")):
        try:
            if os.path.isdir(cand) and any(f.lower().endswith((".ttf", ".otf"))
                                           for f in os.listdir(cand)):
                return cand
        except Exception:
            continue
    return os.path.join(base, "fonts")


def _scan_font_dir(fonts, d, skip=("_internal", "build", "__pycache__",
                                   ".idea", ".git", "dist", "output", "arm64-v8a")):
    """Add every *.ttf / *.otf from folder d into the {name: path} map."""
    if not d or not os.path.isdir(d):
        return
    try:
        for fname in os.listdir(d):
            if fname.lower().endswith((".ttf", ".otf")):
                fonts[os.path.splitext(fname)[0]] = os.path.join(d, fname)
    except Exception:
        pass
    try:
        for sub in os.listdir(d):
            if sub.lower() in skip:
                continue
            full = os.path.join(d, sub)
            if os.path.isdir(full):
                try:
                    for fname in os.listdir(full):
                        if fname.lower().endswith((".ttf", ".otf")):
                            fonts[os.path.splitext(fname)[0]] = os.path.join(full, fname)
                except Exception:
                    pass
    except Exception:
        pass


def discover_fonts():
    """Return {font_name: path} merging bundled + user + system fonts."""
    fonts = {}
    _scan_font_dir(fonts, _find_bundled_font_dir())
    _scan_font_dir(fonts, user_font_dir())
    try:
        _scan_font_dir(fonts, os.path.join(app_root_dir(), "fonts"))
    except Exception:
        pass
    # Android system fonts (available for Latin text)
    try:
        _scan_font_dir(fonts, "/system/fonts")
    except Exception:
        pass
    return fonts


def system_font_paths():
    """Candidate latin fonts by platform (never a black box)."""
    cands = []
    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        cands = [os.path.join(windir, "Fonts", n) for n in
                 ("arial.ttf", "segoeui.ttf", "calibri.ttf", "verdana.ttf",
                  "tahoma.ttf", "DejaVuSans.ttf")]
    elif os.path.isdir("/system/fonts"):
        cands = [os.path.join("/system/fonts", n) for n in
                 ("Roboto-Regular.ttf", "Roboto.ttf", "NotoSans-Regular.ttf",
                  "DroidSans.ttf")]
    else:
        cands = [os.path.join("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                 os.path.join("/usr/share/fonts/truetype/freefont/FreeSans.ttf")]
    return [c for c in cands if os.path.exists(c)]


URDU_FONTS = discover_fonts()

DEFAULT_FONT = "NotoNaskhArabic-Regular"
for cand in ["Jameel_Noori_Nastaleeq", "JameelNooriNastaleeq", "Amiri-Regular", "Amiri"]:
    if cand in URDU_FONTS:
        DEFAULT_FONT = cand
        break

# Free/open-source Urdu & Arabic fonts with stable download links.
ONLINE_FONTS = [
    {"name": "Amiri",
     "files": [
         ("Amiri-Regular.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf"),
         ("Amiri-Bold.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Bold.ttf"),
     ]},
    {"name": "Noto Nastaliq Urdu",
     "files": [
         ("NotoNastaliqUrdu.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/notonastaliqurdu/NotoNastaliqUrdu%5Bwght%5D.ttf"),
     ]},
    {"name": "Noto Naskh Arabic",
     "files": [
         ("NotoNaskhArabic.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf"),
     ]},
    {"name": "Gulzar",
     "files": [
         ("Gulzar-Regular.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/gulzar/Gulzar-Regular.ttf"),
     ]},
    {"name": "Scheherazade New",
     "files": [
         ("ScheherazadeNew-Regular.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/scheherazadenew/ScheherazadeNew-Regular.ttf"),
         ("ScheherazadeNew-Bold.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/scheherazadenew/ScheherazadeNew-Bold.ttf"),
     ]},
    {"name": "Lateef",
     "files": [
         ("Lateef-Regular.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/lateef/Lateef-Regular.ttf"),
     ]},
    {"name": "Reem Kufi",
     "files": [
         ("ReemKufi.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/reemkufi/ReemKufi%5Bwght%5D.ttf"),
     ]},
    {"name": "Markazi Text",
     "files": [
         ("MarkaziText.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/markazitext/MarkaziText%5Bwght%5D.ttf"),
     ]},
]


# ------------------------------------------------------------------ models
class TextLabel:
    """A logical text layer placed on the poster."""

    def __init__(self, text="", font_name=DEFAULT_FONT, size=60, color=(0, 0, 0),
                 x=0.5, y=0.5, rotation=0, opacity=100, arc_angle=0, z=0,
                 word_spacing=0):
        self.text = text
        self.font_name = font_name
        self.size = size
        self.color = tuple(color)          # (r,g,b)
        self.x = x                          # normalized 0..1 (center)
        self.y = y                          # normalized 0..1 (center)
        self.rotation = rotation            # degrees
        self.opacity = max(0, min(100, int(opacity)))   # 0..100 %
        self.arc_angle = int(arc_angle)     # 0=straight, +/- degrees
        self.z = z                          # layer order (higher = on top)
        self.word_spacing = int(word_spacing)           # extra px between words


class OverlayImage:
    """A placed image (logo / photo) over the base picture."""

    def __init__(self, path="", base_image=None, x=0.5, y=0.5, scale=1.0,
                 flip_h=False, flip_v=False, data=None, crop=None, rotation=0,
                 opacity=100, z=0, scale_x=None, scale_y=None):
        self.path = path            # path OR content uri / label
        self.base_image = base_image  # optional preloaded PIL image (from picker)
        self.x = x
        self.y = y
        self.scale = scale          # uniform reference (corner-drag resizing)
        self.scale_x = scale if scale_x is None else scale_x
        self.scale_y = scale if scale_y is None else scale_y
        self.flip_h = flip_h
        self.flip_v = flip_v
        self.rotation = int(rotation)
        self.opacity = max(0, min(100, int(opacity)))
        self.z = z
        self.data = data            # processed PIL image (crop/rembg result)
        self.crop = crop            # optional (l,t,r,b) pre-crop box

    def open(self):
        """Return the base PIL image (processed data if available)."""
        if self.data is not None:
            img = self.data.convert("RGBA")
        elif self.base_image is not None:
            img = self.base_image.convert("RGBA")
        elif self.path and os.path.exists(self.path):
            img = Image.open(self.path).convert("RGBA")
        else:
            raise IOError("missing image")
        if self.crop:
            l, t, r, b = [int(v) for v in self.crop]
            img = img.crop((l, t, r, b))
        return img


# ------------------------------------------------------------------ engine
class Poster:
    """Holds the canvas + layers and renders / edits it. GUI-agnostic."""

    def __init__(self, width=1600, height=2200, fill=(255, 255, 255)):
        self.base_pil = Image.new("RGB", (width, height), fill)
        self.labels = []
        self.overlays = []
        self._z_counter = 1
        self.selected = None        # ("label", idx) | ("overlay", idx) | None
        self.canvas_color = tuple(fill)

    # ---------------------------------------------------------- lifecycle
    def new_canvas(self, w, h, fill=(255, 255, 255)):
        self.base_pil = Image.new("RGB", (max(int(w), 20), max(int(h), 20)), fill)
        self.canvas_color = tuple(fill)
        self.labels = []
        self.overlays = []
        self.selected = None
        self._z_counter = 1

    @property
    def width(self):
        return self.base_pil.width if self.base_pil else 0

    @property
    def height(self):
        return self.base_pil.height if self.base_pil else 0

    def set_background_pil(self, pil_image):
        """Set the background image (already converted to RGB)."""
        self.base_pil = pil_image.convert("RGB")
        self.labels = []
        self.overlays = []
        self.selected = None
        self._z_counter = 1

    def replace_background_pil(self, pil_image):
        """Replace background keeping labels / overlays (design preserved)."""
        self.base_pil = pil_image.convert("RGB")

    def recolor_background(self, color):
        img = Image.new("RGB", self.base_pil.size, tuple(color))
        self.base_pil = img

    # --------------------------------------------------------------- z
    def _next_z(self):
        z = self._z_counter
        self._z_counter += 1
        return z

    def _get_element(self, kind, idx):
        if kind == "label" and 0 <= idx < len(self.labels):
            return self.labels[idx]
        if kind == "overlay" and 0 <= idx < len(self.overlays):
            return self.overlays[idx]
        return None

    def _layer_adjust(self, el, others, mode):
        elz = el.z
        if mode in ("front", "top"):
            el.z = max([o.z for o in others], default=0) + 1
        elif mode in ("back", "bottom"):
            el.z = min([o.z for o in others], default=0) - 1
        elif mode == "forward":
            above = [o for o in others if o.z > elz]
            if above:
                nxt = min(above, key=lambda o: o.z)
                el.z, nxt.z = nxt.z, el.z
        elif mode == "backward":
            below = [o for o in others if o.z < elz]
            if below:
                prv = max(below, key=lambda o: o.z)
                el.z, prv.z = prv.z, el.z

    def layer_move(self, mode):
        """Move the selected element's z-order. mode: front|forward|backward|back."""
        if not self.selected:
            return
        kind, idx = self.selected
        el = self._get_element(kind, idx)
        if el is None:
            return
        others = [o for j, o in enumerate(self.overlays)
                  if not (kind == "overlay" and j == idx)]
        others += [l for j, l in enumerate(self.labels)
                   if not (kind == "label" and j == idx)]
        self._layer_adjust(el, others, mode)

    # ------------------------------------------------------------ labels
    def add_label(self, text="\u0646\u0626\u06cc \u062a\u062d\u0631\u06cc\u0631",
                  size=60, font_name=None, opacity=100, arc_angle=0,
                  word_spacing=0, x=0.5, y=None, sync_editor=True):
        """Create a new text label. y auto-stacks if not given."""
        if y is None:
            i = len(self.labels)
            y = 0.5 + i * 0.08
            if y > 0.9:
                y = 0.9
        lbl = TextLabel(text=urdu_text.normalize(text),
                        font_name=font_name or DEFAULT_FONT,
                        size=size, x=x, y=y, z=self._next_z())
        lbl.opacity = opacity
        lbl.arc_angle = arc_angle
        lbl.word_spacing = word_spacing
        self.labels.append(lbl)
        self.selected = ("label", len(self.labels) - 1)
        return self.selected

    def add_text_at(self, text, x, y, font_name=None, size=60, z=None):
        lbl = TextLabel(text=urdu_text.normalize(text),
                        font_name=font_name or DEFAULT_FONT,
                        size=size, x=x, y=y, z=self._next_z() if z is None else z)
        self.labels.append(lbl)
        self.selected = ("label", len(self.labels) - 1)
        return self.selected

    def update_selected_label_text(self, text):
        if self.selected and self.selected[0] == "label":
            i = self.selected[1]
            if 0 <= i < len(self.labels):
                self.labels[i].text = urdu_text.normalize(text)
                return True
        return False

    def delete_selected(self):
        if not self.selected:
            return
        kind, i = self.selected
        if kind == "label" and i < len(self.labels):
            del self.labels[i]
        elif kind == "overlay" and i < len(self.overlays):
            del self.overlays[i]
        self.selected = None

    # ----------------------------------------------------------- overlays
    def add_overlay(self, path="", base_image=None, x=0.5, y=0.5):
        ov = OverlayImage(path=path, base_image=base_image, x=x, y=y)
        ov.z = self._next_z()
        self.overlays.append(ov)
        self.selected = ("overlay", len(self.overlays) - 1)
        return self.selected

    def _selected_overlay(self):
        if self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if 0 <= i < len(self.overlays):
                return self.overlays[i], i
        return None, -1

    def replace_selected_overlay_image(self, base_image=None, path=""):
        ov, _ = self._selected_overlay()
        if ov is None:
            return False
        ov.base_image = base_image
        ov.path = path
        ov.data = None   # reset any previous crop/bg removal
        return True

    # ---------------------------------------------------- element helpers
    def element_box(self, kind, idx):
        """(cx, cy, half_w, half_h) in full-image pixels for an element."""
        w = self.width
        h = self.height
        if kind == "label" and idx < len(self.labels):
            lbl = self.labels[idx]
            return (lbl.x * w, lbl.y * h,
                    max(lbl.size * 1.4, 30) / 2, max(lbl.size * 0.45, 14) / 2)
        if kind == "overlay" and idx < len(self.overlays):
            ov = self.overlays[idx]
            try:
                o = ov.open()
                base_w = max(w, 4) * 0.3
                half_w = (base_w * ov.scale_x) / 2
                half_h = (o.height * (base_w / max(o.width, 1)) * ov.scale_y) / 2
                return (ov.x * w, ov.y * h, half_w, half_h)
            except Exception:
                return (ov.x * w, ov.y * h, 40.0, 40.0)
        return None

    def hit_test(self, img_x, img_y):
        """Return ("label"|"overlay", idx) for the nearest element."""
        best = None
        best_d = 1e9
        for i, ov in enumerate(self.overlays):
            try:
                o = ov.open()
                ow = max(self.width, 4) * 0.3 * ov.scale_x
                oh = o.height * (max(self.width, 4) * 0.3 / max(o.width, 1)) * ov.scale_y
            except Exception:
                ow = oh = 80
            cx, cy = ov.x * self.width, ov.y * self.height
            if abs(img_x - cx) < ow / 2 and abs(img_y - cy) < oh / 2:
                d = (img_x - cx) ** 2 + (img_y - cy) ** 2
                if d < best_d:
                    best_d = d
                    best = ("overlay", i)
        for i, lbl in enumerate(self.labels):
            cx, cy = lbl.x * self.width, lbl.y * self.height
            d = (img_x - cx) ** 2 + (img_y - cy) ** 2
            if d < best_d and d < (max(lbl.size * 2, 40) ** 2):
                best_d = d
                best = ("label", i)
        return best

    def corner_at(self, img_x, img_y, threshold_px=30):
        """Return ("label"|"overlay", idx) if point is within a corner handle."""
        if not self.selected:
            return None
        kind, i = self.selected
        if kind not in ("label", "overlay"):
            return None
        box = self.element_box(kind, i)
        if box is None:
            return None
        cx0, cy0, hw, hh = box
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            if abs(img_x - (cx0 + sx * hw)) < threshold_px and \
               abs(img_y - (cy0 + sy * hh)) < threshold_px:
                return (kind, i)
        return None

    def read_size(self, sel):
        kind, i = sel
        if kind == "label" and i < len(self.labels):
            return self.labels[i].size
        if kind == "overlay" and i < len(self.overlays):
            return self.overlays[i].scale
        return None

    def resize_ratio_for(self, kind, i):
        """Fixed multiplier from element size to its corner half-width."""
        if kind == "label" and i < len(self.labels):
            halfw = max(self.labels[i].size * 1.4, 30) / 2
            return self.labels[i].size / max(halfw, 1)
        if kind == "overlay" and i < len(self.overlays):
            ov = self.overlays[i]
            halfw = (max(self.width, 4) * 0.3 * ov.scale_x) / 2
            return ov.scale_x / max(halfw, 1)
        return 1.0

    def do_resize(self, kind, idx, img_x, img_y):
        """Resize the selected element by dragging (dist from its center)."""
        box = self.element_box(kind, idx)
        if box is None:
            return
        cx0, cy0, hw, hh = box
        dist = max(abs(img_x - cx0), 12)
        ratio = self.resize_ratio_for(kind, idx)
        if kind == "label" and idx < len(self.labels):
            self.labels[idx].size = max(8, int(ratio * dist))
        elif kind == "overlay" and idx < len(self.overlays):
            ov = self.overlays[idx]
            prev_x = ov.scale_x
            ov.scale_x = max(0.05, min(5.0, ratio * dist))
            factor = ov.scale_x / prev_x if prev_x else 1.0
            ov.scale_y = max(0.05, min(5.0, ov.scale_y * factor))
            ov.scale = ov.scale_x

    def move_selected_to(self, img_x, img_y, offset=None):
        """Move the selected element so its center is at (img_x, img_y)."""
        if not self.selected:
            return
        kind, i = self.selected
        if offset:
            img_x += offset[0]
            img_y += offset[1]
        img_x = max(0.0, min(1.0, img_x / self.width))
        img_y = max(0.0, min(1.0, img_y / self.height))
        if kind == "label" and i < len(self.labels):
            self.labels[i].x = img_x
            self.labels[i].y = img_y
        elif kind == "overlay" and i < len(self.overlays):
            self.overlays[i].x = img_x
            self.overlays[i].y = img_y

    # ------------------------------------------------------------- fonts
    def validate_font(self, path):
        """(ok, reason) - the font must load and carry Urdu/Arabic glyphs."""
        try:
            ImageFont.truetype(path, 24)
        except Exception:
            return False, "not a valid TTF/OTF font file"
        try:
            from fontTools.ttLib import TTFont
            cmap = TTFont(path).getBestCmap() or {}
            arabic = sum(1 for c in cmap if 0x0600 <= c <= 0x06FF)
            pf = sum(1 for c in cmap if 0xFB50 <= c <= 0xFDFF)
            if arabic < 3 and pf < 5:
                return False, "no Urdu / Arabic glyphs (not an Urdu font)"
        except Exception:
            pass
        return True, "ok"

    def _font_path_for(self, font_name):
        """Resolve a font name to an on-disk ttf/otf path ('' if none)."""
        if font_name and font_name in URDU_FONTS:
            return URDU_FONTS[font_name]
        return ""

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _font_lacks_pf_cached(font_path):
        """Cached cmap inspection (is the font missing Presentation-Forms?)."""
        if not font_path or not os.path.exists(font_path):
            return False
        try:
            from fontTools.ttLib import TTFont
            cmap = TTFont(font_path).getBestCmap()
            probe = [0xFB8E, 0xFB90, 0xFDA4, 0xFE8E, 0xFE91, 0xFE97, 0xFEDF,
                     0xFEE3, 0xFEEA, 0xFEFB, 0xFBFE]
            missing = [c for c in probe if c not in cmap]
            return len(missing) >= 8
        except Exception:
            return False

    def _get_font(self, name, size):
        """Return a PIL font for the requested Urdu font name."""
        if name and name in URDU_FONTS:
            try:
                return ImageFont.truetype(URDU_FONTS[name], int(size))
            except Exception:
                pass
        try:
            import fonts_res
            raw = fonts_res.NASKH_B64
            data = raw.encode("ascii") if isinstance(raw, str) else raw
            return ImageFont.truetype(io.BytesIO(base64.b64decode(data)), int(size))
        except Exception:
            pass
        if name and name in URDU_FONTS:
            try:
                return ImageFont.truetype(URDU_FONTS[name], int(size))
            except Exception:
                pass
        elif URDU_FONTS:
            try:
                return ImageFont.truetype(next(iter(URDU_FONTS.values())), int(size))
            except Exception:
                pass
        try:
            import fonts_res
            raw = fonts_res.NASTALIQ_B64
            data = raw.encode("ascii") if isinstance(raw, str) else raw
            return ImageFont.truetype(io.BytesIO(base64.b64decode(data)), int(size))
        except Exception:
            pass
        try:
            return ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()

    def _get_latin_font(self, size):
        """Reliable latin font (real file) for numbers / dashes."""
        if not getattr(self, "_latin_font", None) or \
           getattr(self, "_latin_font_size", None) != size:
            path = None
            cands = system_font_paths()
            if cands:
                path = cands[0]
            self._latin_font_size = size
            try:
                self._latin_font = ImageFont.truetype(path, size) if path \
                    else ImageFont.load_default()
            except Exception:
                self._latin_font = ImageFont.load_default()
        return self._latin_font

    # ------------------------------------------------------------ shaping
    @staticmethod
    def _split_logic_runs(text):
        """Split LOGICAL text into (is_urdu, segment) runs."""
        runs = []
        cur_urdu = None
        cur = []
        for ch in text:
            o = ord(ch)
            is_urdu_ch = (
                0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or
                0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF
            )
            if cur_urdu is not None and cur_urdu != is_urdu_ch:
                runs.append(("".join(cur), cur_urdu))
                cur = []
            cur_urdu = is_urdu_ch
            cur.append(ch)
        if cur:
            runs.append(("".join(cur), cur_urdu))
        if not runs:
            runs.append((text, False))
        return runs

    @staticmethod
    def _split_visual_runs(txt):
        """Split a visual-order string into (text, is_latin) runs."""
        runs = []
        cur_latin = None
        cur = []
        for ch in txt:
            o = ord(ch)
            is_urdu_char = (
                0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or
                0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF or
                o in (0x06D2, 0x06D0, 0x06CC, 0x0640)
            )
            is_latin = not is_urdu_char or ch == ' '
            if cur_latin is not None and cur_latin != is_latin:
                runs.append(("".join(cur), cur_latin))
                cur = []
            cur_latin = is_latin
            cur.append(ch)
        if cur:
            runs.append(("".join(cur), cur_latin))
        if not runs:
            runs.append((txt, False))
        runs = [(t.replace("\u2010", "-")
                 .replace("\u2013", "-")
                 .replace("\u0020", "\u2009")
                 if isl else t, isl) for t, isl in runs]
        runs = [(t.replace("\u0020", "\u200c") if not isl else t, isl)
                for t, isl in runs]
        return runs

    def _text_pieces(self, text, font, ws):
        """Split into drawable chunks; spaces become sized gaps."""
        td_tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        if not text:
            return []
        if "\u2009" not in text and " " not in text:
            t = text
            b = td_tmp.textbbox((0, 0), t, font=font)
            return [(t, b[2] - b[0], b)]
        parts = re.split(r"([\u2009 ]+)", text)
        out = []
        for part in parts:
            if not part:
                continue
            if re.fullmatch(r"[\u2009 ]+", part):
                b = td_tmp.textbbox((0, 0), part[0], font=font)
                out.append(("", max(b[2] - b[0], 0) + ws * len(part), b))
            else:
                b = td_tmp.textbbox((0, 0), part, font=font)
                out.append((part, b[2] - b[0], b))
        return out

    def _render_urdu_hb(self, font_path, size, text, color, alpha=255):
        """Render one logical Urdu text run via HarfBuzz+FreeType (optional)."""
        try:
            assert _HB_AVAILABLE, "harfbuzz fallback unavailable"
            return _urdu_render.render(font_path, text, max(int(size), 4),
                                       tuple(color), alpha)
        except Exception:
            return None

    def _arc_warp(self, img, arc_deg):
        """Bend a rendered text bitmap along a circular arc (mesh warp)."""
        arc_deg = int(arc_deg) % 360
        if arc_deg == 0:
            return img
        down = arc_deg < 0
        A = abs(arc_deg)
        if A < 2 or A > 180:
            A = min(max(A, 2), 180)
        W, H = img.size
        if W < 8 or H < 2:
            return img
        rad = math.radians
        Arad = rad(A)
        half = Arad / 2.0
        sin_h = math.sin(half)
        if sin_h < 1e-6:
            return img
        R = W / (2 * sin_h)
        pad = int(max(6, H * 0.2))
        Wo = int(2 * (R + H) * sin_h + 2 * pad)
        Ho = int(R + H + 2 * pad)
        cx = Wo / 2.0
        cy = float(R + H + pad)
        N = max(16, min(72, int(W / 28)))
        sw = W / float(N)

        def pt(phi, r):
            return (cx + r * math.sin(phi), cy - r * math.cos(phi))

        quads = []
        for i in range(N):
            p0 = -half + i * (Arad / N)
            p1 = p0 + Arad / N
            sx0 = int(i * sw)
            sx1 = int((i + 1) * sw)
            if sx1 >= W:
                sx1 = W - 1
            if sx1 <= sx0:
                continue
            bl = pt(p0, R)
            br = pt(p1, R)
            tr = pt(p1, R + H)
            tl = pt(p0, R + H)
            quads.append(([bl, br, tr, tl], [(sx0, 0), (sx1, 0), (sx1, H), (sx0, H)]))
        if not quads:
            return img
        try:
            out = img.transform((Wo, Ho), Image.MESH, quads, Image.BICUBIC)
        except Exception:
            return img
        if down:
            out = out.transpose(Image.FLIP_TOP_BOTTOM)
        return out

    def _render_label(self, img, draw, lbl, scale=1.0):
        """Compose one text layer onto a PIL image at given scale."""
        if not lbl.text.strip():
            return
        font_size = max(int(lbl.size * scale), 4)
        font_path = self._font_path_for(lbl.font_name)
        alpha = int(255 * lbl.opacity / 100)
        ws = max(-200, min(500, int(getattr(lbl, "word_spacing", 0))))

        needs_hb = _HB_AVAILABLE and font_path and self._font_lacks_pf_cached(font_path)

        if needs_hb:
            runs = self._split_logic_runs(lbl.text)
            all_parts = []
            tw = 0.0
            mh = 0
            for seg_text, is_urdu in runs:
                if is_urdu:
                    words = re.split(r"([ ]+)", seg_text)
                    for word in words:
                        if not word:
                            continue
                        if word.strip() == "":
                            try:
                                _im, adv = _urdu_render.render(font_path, " ", font_size,
                                                               tuple(lbl.color), 255)
                                gap = (adv + ws) * len(word)
                                all_parts.append((None, gap))
                                tw += gap
                            except Exception:
                                pass
                        else:
                            try:
                                part, adv = _urdu_render.render(font_path, word, font_size,
                                                                tuple(lbl.color), 255)
                                all_parts.append((part, adv))
                                tw += adv
                                mh = max(mh, part.height)
                            except Exception:
                                pass
                else:
                    f_latin = self._get_latin_font(font_size)
                    for pt, pw, pb in self._text_pieces(seg_text, f_latin, ws):
                        if pt:
                            lp_layer = Image.new("RGBA",
                                                 (int(pw) + 10, int(max(pb[3] - pb[1], 1)) + 10),
                                                 (0, 0, 0, 0))
                            ImageDraw.Draw(lp_layer).text((-pb[0] + 2, -pb[1] + 2), pt,
                                                          font=f_latin, fill=lbl.color + (255,))
                            all_parts.append((lp_layer, pw))
                        else:
                            all_parts.append((None, pw))
                        tw += pw
                        mh = max(mh, pb[3] - pb[1])

            if not all_parts:
                return
            text_layer = Image.new("RGBA", (max(int(tw), 1) + 100, max(int(mh), 1) + 200),
                                   (0, 0, 0, 0))
            curr_x = 50
            for part, adv in all_parts:
                if part:
                    text_layer.alpha_composite(part, (int(curr_x), 100 - part.height // 2))
                curr_x += adv
            if alpha < 255:
                a = text_layer.getchannel("A").point(lambda v: int(v * alpha / 255))
                text_layer.putalpha(a)
        else:
            txt = urdu_text.shape(lbl.text)
            if not txt:
                return
            runs = self._split_visual_runs(txt)
            f_urdu = self._get_font(lbl.font_name, font_size)
            f_latin = self._get_latin_font(font_size)
            segments = []
            tw = 0.0
            mh = 0
            for t, is_latin in runs:
                fo = f_latin if is_latin else f_urdu
                for pt, pw, pb in self._text_pieces(t, fo, ws):
                    segments.append((pt, fo, pw, pb))
                    tw += pw
                    mh = max(mh, pb[3] - pb[1])
            text_layer = Image.new("RGBA", (max(int(tw), 1) + 60, max(int(mh), 1) + 60),
                                   (0, 0, 0, 0))
            ld = ImageDraw.Draw(text_layer)
            curr_x = 30
            for pt, fo, w, b in segments:
                if pt:
                    ld.text((curr_x - b[0], 30 - b[1]), pt, font=fo,
                            fill=lbl.color + (alpha,))
                curr_x += w

        if lbl.arc_angle:
            text_layer = self._arc_warp(text_layer, lbl.arc_angle)
        if lbl.rotation:
            text_layer = text_layer.rotate(lbl.rotation, expand=True, resample=Image.BICUBIC)

        cx, cy = int(lbl.x * img.width), int(lbl.y * img.height)
        px, py = cx - text_layer.width // 2, cy - text_layer.height // 2
        img.paste(text_layer, (px, py), text_layer)

    def _draw_overlay(self, img, ov, scale=1.0):
        o = ov.open()
        base_w = max(img.width, 4) * 0.3
        bw = int(base_w * ov.scale_x)
        bh = int(o.height * (base_w / max(o.width, 1)) * ov.scale_y)
        bw = max(bw, 1)
        bh = max(bh, 1)
        o = o.resize((bw, bh), Image.LANCZOS)
        if ov.rotation:
            o = o.rotate(ov.rotation, expand=True, resample=Image.BICUBIC)
        if ov.flip_h:
            o = o.transpose(Image.FLIP_LEFT_RIGHT)
        if ov.flip_v:
            o = o.transpose(Image.FLIP_TOP_BOTTOM)
        if ov.opacity < 100:
            o = o.convert("RGBA")
            r, g, b, a = o.split()
            a = a.point(lambda p: int(p * ov.opacity / 100))
            o = Image.merge("RGBA", (r, g, b, a))
        ox = int(ov.x * img.width) - o.width // 2
        oy = int(ov.y * img.height) - o.height // 2
        if o.mode == "RGBA":
            img.paste(o, (ox, oy), o)
        else:
            img.paste(o.convert("RGB"), (ox, oy))

    def _draw_overlays_and_labels(self, img, scale=1.0):
        draw = ImageDraw.Draw(img)
        items = [("overlay", i, ov.z) for i, ov in enumerate(self.overlays)]
        items += [("label", i, lbl.z) for i, lbl in enumerate(self.labels)]
        items.sort(key=lambda it: it[2])
        for kind, idx, _z in items:
            try:
                if kind == "overlay":
                    self._draw_overlay(img, self.overlays[idx], scale)
                else:
                    self._render_label(img, draw, self.labels[idx], scale)
            except Exception:
                continue

    # ------------------------------------------------------------ renders
    def render_preview(self, dw=None, dh=None):
        """Fast on-screen preview at a target display size."""
        bw = self.width
        bh = self.height
        if not bw or not bh:
            return None
        if not dw and not dh:
            dw, dh = bw, bh
        if dw and not dh:
            dh = int(bh * dw / bw)
        if dh and not dw:
            dw = int(bw * dh / bh)
        dw = max(int(dw), 2)
        dh = max(int(dh), 2)
        prev = self.base_pil.convert("RGB").resize((dw, dh), Image.LANCZOS)
        self._draw_overlays_and_labels(prev, dw / bw)
        return prev

    def render_full(self):
        """High-res composed image (base + overlays + labels)."""
        img = self.base_pil.convert("RGB")
        self._draw_overlays_and_labels(img, 1.0)
        return img

    # ------------------------------------------------------------- save
    def save_image(self, fmt="png"):
        """Return PNG/JPEG bytes of the full render."""
        out = self.render_full()
        if str(fmt).lower() in ("jpg", "jpeg"):
            buf = io.BytesIO()
            out.convert("RGB").save(buf, "JPEG", quality=95)
        else:
            buf = io.BytesIO()
            out.save(buf, "PNG")
        return buf.getvalue()

    def pdf_bytes(self):
        """Return PDF bytes fitting the composed image onto an A4 page."""
        from reportlab.pdfgen import canvas as rlcanvas
        from reportlab.lib.pagesizes import A4
        img = self.render_full().convert("RGB")
        target_w, target_h = A4
        w, h = img.size
        ratio = min(target_w / w, target_h / h)
        draw_w = int(w * ratio)
        draw_h = int(h * ratio)
        buf = io.BytesIO()
        c = rlcanvas.Canvas(buf, pagesize=(target_w, target_h))
        x = (target_w - draw_w) // 2
        y = (target_h - draw_h) // 2
        c.drawInlineImage(img, x, y, width=draw_w, height=draw_h)
        c.setTitle("Qazi Urdu Poster Designer & Writer")
        c.setAuthor("Qazi Muhammad Umer Farooq Hajveri")
        c.showPage()
        c.save()
        return buf.getvalue()

    # ------------------------------------------------------------ project
    def project_json(self):
        """Serialize the whole design (with embedded background image)."""
        buffered = io.BytesIO()
        self.base_pil.save(buffered, format="PNG")
        base_b64 = base64.b64encode(buffered.getvalue()).decode()
        project = {
            "version": "1.2",
            "base_image_b64": base_b64,
            "canvas_color": self.canvas_color,
            "labels": [],
            "overlays": [],
        }
        for lbl in self.labels:
            project["labels"].append({
                "text": lbl.text,
                "font_name": lbl.font_name,
                "size": lbl.size,
                "color": list(lbl.color),
                "x": lbl.x,
                "y": lbl.y,
                "rotation": lbl.rotation,
                "opacity": lbl.opacity,
                "arc_angle": lbl.arc_angle,
                "word_spacing": getattr(lbl, "word_spacing", 0),
                "z": lbl.z,
            })
        for ov in self.overlays:
            ov_data = {
                "path": ov.path,
                "x": ov.x,
                "y": ov.y,
                "scale": ov.scale,
                "scale_x": ov.scale_x,
                "scale_y": ov.scale_y,
                "flip_h": ov.flip_h,
                "flip_v": ov.flip_v,
                "rotation": ov.rotation,
                "opacity": ov.opacity,
                "z": ov.z,
                "crop": ov.crop,
            }
            if ov.data is not None:
                buf = io.BytesIO()
                ov.data.save(buf, format="PNG")
                ov_data["data_b64"] = base64.b64encode(buf.getvalue()).decode()
            project["overlays"].append(ov_data)
        return project

    @classmethod
    def from_project_bytes(cls, raw):
        """Build a Poster from a serialized .qazip project (bytes)."""
        data = raw
        if isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        project = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
            try:
                project = json.loads(data.decode(enc))
                break
            except Exception:
                continue
        if project is None:
            raise ValueError("project file format not recognized")

        if "base_image_b64" in project:
            base_data = base64.b64decode(project["base_image_b64"])
            base_pil = Image.open(io.BytesIO(base_data)).convert("RGB")
        else:
            cc = project.get("canvas_color", (255, 255, 255))
            base_pil = Image.new("RGB", (1050, 660), tuple(cc))

        poster = cls(base_pil.width, base_pil.height, (255, 255, 255))
        poster.base_pil = base_pil
        poster.labels = []
        poster.overlays = []
        poster.selected = None
        poster._z_counter = 1
        used_z = set()
        poster.canvas_color = tuple(project.get("canvas_color", (255, 255, 255)))

        for o_data in project.get("overlays", []):
            ov_img = None
            if "data_b64" in o_data:
                img_data = base64.b64decode(o_data["data_b64"])
                ov_img = Image.open(io.BytesIO(img_data)).convert("RGBA")
            ov = OverlayImage(
                path=o_data.get("path", ""),
                x=o_data["x"],
                y=o_data["y"],
                scale=o_data["scale"],
                flip_h=o_data["flip_h"],
                flip_v=o_data["flip_v"],
                rotation=o_data.get("rotation", 0),
                opacity=o_data.get("opacity", 100),
                data=ov_img,
                crop=o_data.get("crop"),
                scale_x=o_data.get("scale_x"),
                scale_y=o_data.get("scale_y"),
            )
            z = o_data.get("z")
            if z is None or z in used_z:
                z = poster._next_z()
            else:
                used_z.add(z)
                poster._z_counter = max(poster._z_counter, z + 1)
            ov.z = z
            poster.overlays.append(ov)

        for l_data in project.get("labels", []):
            lbl = TextLabel(
                text=l_data["text"],
                font_name=l_data["font_name"],
                size=l_data["size"],
                color=tuple(l_data["color"]),
                x=l_data["x"],
                y=l_data["y"],
                rotation=l_data["rotation"],
                opacity=l_data.get("opacity", 100),
                arc_angle=l_data.get("arc_angle", 0),
                word_spacing=l_data.get("word_spacing", 0),
            )
            z = l_data.get("z")
            if z is None or z in used_z:
                z = poster._next_z()
            else:
                used_z.add(z)
                poster._z_counter = max(poster._z_counter, z + 1)
            lbl.z = z
            poster.labels.append(lbl)
        return poster


# ------------------------------------------------------------------ fonts
def refresh_font_list():
    global URDU_FONTS
    URDU_FONTS = discover_fonts()
    clear_render_caches()


def clear_render_caches():
    """Drop cached shaped glyphs so freshly installed fonts take effect."""
    try:
        if _HB_AVAILABLE:
            _urdu_render.clear_caches()
    except Exception:
        pass


def remove_font_file(path):
    """Delete a user font file best-effort."""
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception as e:
        log_error(f"remove_font_file {path}: {e}")
    return False


# ---------------------------------------------------------------- background eraser
def strip_background_edges(img, thresh=24):
    """Remove a near-uniform border background without any AI dependency.

    Flood-fills transparency inward from the four image corners so solid or
    softly-varying backdrops (the common logo case) become transparent. Works
    fully offline on both desktop and Android.
    """
    try:
        from PIL import ImageDraw
        weight = max(16, min(80, max(img.size) // 30))
        rgba = img.convert("RGBA")
        w, h = rgba.size
        if min(w, h) < 4:
            return rgba
        corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
        thresh = max(18, thresh * weight // 40)
        for cx, cy in corners:
            try:
                ImageDraw.floodfill(rgba, (cx, cy), (0, 0, 0, 0), thresh=thresh)
            except Exception:
                continue
        return rgba
    except Exception as e:
        log_error(f"strip_background_edges: {e}")
        return img.convert("RGBA")