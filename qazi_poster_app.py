"""Qazi Urdu Poster Designer & Writer

Standalone Urdu poster designer.
Features:
  - Upload picture (background) from PC
  - Write Urdu text on the picture (multi-layer text labels)
  - Add/upload logo / overlay images
  - Input RTL Urdu fields rendered correctly
  - Save final design as JPG / PNG image
  - Save final design as PDF
  - Drag text labels / overlays to reposition on the canvas
  - Change font size, color, rotation and style per label

Developed by Qazi Muhammad Umer Farooq Hajveri
"""
import os
import sys
import json
import base64
import io
import re
import time
import functools
import threading
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox, simpledialog
from tkinter.font import Font, families

from PIL import Image, ImageTk, ImageDraw, ImageFont

import urdu_text
import urdu_kb
import fonts_res
from pdf_export import save_as_pdf

# Optional HarfBuzz+FreeType fallback renderer for fonts whose cmap does not
# expose Arabic Presentation-Forms (e.g. Jameel Noori Nastaleeq, Uthmanic Hafs).
try:
    import urdu_render
    _HB_AVAILABLE = True
except Exception:
    _HB_AVAILABLE = False

APP_TITLE = "Qazi Urdu Poster Designer & Writer"

def _install_exception_logger():
    """Log any uncaught exception to a file next to the executable."""
    import traceback as _tb
    try:
        log_path = os.path.join(os.path.dirname(sys.executable)
                                if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)),
                                "QaziUrduPosterDesigner_error.log")

        def _hook(exc_type, exc_value, exc_tb):
            try:
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write("=" * 60 + "\n")
                    _tb.print_exception(exc_type, exc_value, exc_tb, file=fh)
            except Exception:
                pass
            try:
                import tkinter.messagebox as _mb
                _mb.showerror("Qazi Urdu Poster Designer - Unhandled Error",
                              "An error occurred. Details saved to:\n" + log_path)
            except Exception:
                pass

        sys.excepthook = _hook
    except Exception:
        pass

_install_exception_logger()

def log_error(msg):
    """Append a message to the error log that sits next to the executable."""
    import traceback as _tb
    try:
        log_path = os.path.join(os.path.dirname(sys.executable)
                                if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)),
                                "QaziUrduPosterDesigner_error.log")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("=" * 60 + "\n" + str(msg) + "\n" + _tb.format_exc() + "\n")
    except Exception:
        pass


def _base_resource_dir():
    """Directory containing bundled resources (works when frozen by PyInstaller)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_font_dir():
    """Locate a directory containing bundled TTF/OTF fonts from several places."""
    candidates = []
    if getattr(sys, "frozen", False):
        meip = getattr(sys, "_MEIPASS", None)
        if meip:
            candidates.append(os.path.join(meip, "fonts"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "fonts"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "_internal", "fonts"))
    candidates.append(os.path.join(APP_DIR, "fonts"))
    for d in candidates:
        try:
            if os.path.isdir(d) and any(f.lower().endswith((".ttf", ".otf"))
                                        for f in os.listdir(d)):
                return d
        except Exception:
            continue
    return candidates[0] if candidates else os.path.join(APP_DIR, "fonts")


FONT_DIR = _find_font_dir()

# User-writable folder where downloaded / imported fonts are stored.
# (The bundled fonts folder can be read-only when the app is frozen.)
USER_FONT_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "QaziUrduPosterDesigner", "fonts")
try:
    os.makedirs(USER_FONT_DIR, exist_ok=True)
except Exception:
    pass


def _scan_font_dir(fonts, d, skip=("_internal", "build", "__pycache__",
                                   ".idea", ".git", "dist", "output")):
    """Add every *.ttf / *.otf from folder d into the {name: path} map."""
    if not d or not os.path.isdir(d):
        return
    try:
        for fname in os.listdir(d):
            if fname.lower().endswith((".ttf", ".otf")):
                fonts[os.path.splitext(fname)[0]] = os.path.join(d, fname)
    except Exception:
        pass
    # one level deep (users often drop fonts inside sub-folders)
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


def _collect_fonts():
    """Return {font_name: path} merging fonts from every location the app
    looks in: bundled fonts, the user fonts folder, and any folder next to
    the app (so a font simply copied near the program gets picked up)."""
    fonts = {}
    _scan_font_dir(fonts, FONT_DIR)
    _scan_font_dir(fonts, USER_FONT_DIR)
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else APP_DIR
    _scan_font_dir(fonts, base)
    _scan_font_dir(fonts, os.path.join(base, "fonts"))
    return fonts


# Font name -> file mapping (preferred Urdu fonts bundled with the app)
URDU_FONTS = _collect_fonts()

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


class TextLabel:
    """A logical text layer placed on the poster."""

    def __init__(self, text="", font_name=DEFAULT_FONT, size=60, color=(0, 0, 0),
                 x=0.5, y=0.5, rotation=0, opacity=100, arc_angle=0, z=0,
                 word_spacing=0):
        self.text = text
        self.font_name = font_name
        self.size = size
        self.color = color          # (r,g,b)
        self.x = x                  # normalized 0..1 (center)
        self.y = y                  # normalized 0..1 (center)
        self.rotation = rotation    # degrees
        self.opacity = max(0, min(100, int(opacity)))   # 0..100 %
        self.arc_angle = int(arc_angle)                 # 0=straight, +/- degrees
        self.z = z                  # layer order (higher = on top)
        self.word_spacing = int(word_spacing)           # extra px between words


class OverlayImage:
    """A placed image (logo / photo) over the base picture."""

    def __init__(self, path, x=0.5, y=0.5, scale=1.0, flip_h=False, flip_v=False,
                 data=None, crop=None, rotation=0, opacity=100, z=0,
                 scale_x=None, scale_y=None):
        self.path = path
        self.x = x
        self.y = y
        self.scale = scale          # uniform reference (corner-drag resizing)
        self.scale_x = scale if scale_x is None else scale_x   # horizontal multiplier
        self.scale_y = scale if scale_y is None else scale_y   # vertical multiplier
        self.flip_h = flip_h
        self.flip_v = flip_v
        self.rotation = int(rotation)   # degrees
        self.opacity = max(0, min(100, int(opacity)))   # 0..100 %
        self.z = z                      # layer order (higher = on top)
        self.data = data            # optional processed PIL image (crop/rembg result)
        self.crop = crop            # optional (l,t,r,b) pre-crop box in source coords

    def open(self):
        """Return the base PIL image (processed data if available, else the file)."""
        if self.data is not None:
            img = self.data.convert("RGBA")
        else:
            img = Image.open(self.path).convert("RGBA")
        if self.crop:
            l, t, r, b = [int(v) for v in self.crop]
            img = img.crop((l, t, r, b))
        return img


class ImageRegistry:
    """Caches loaded PIL images + Tk PhotoImage references (to avoid GC)."""

    def __init__(self):
        self._refs = {}

    def keep(self, key, photo):
        self._refs[key] = photo

    def clear(self):
        self._refs.clear()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x820")
        self.minsize(1000, 700)

        self.base_pil = None            # current base background image (PIL)
        self.base_tk = None             # Tk photo of base (scaled)
        self.canvas_image_id = None

        self.current_scale = 1.0        # canvas px per base px
        self.offset_x = 0
        self.offset_y = 0

        self.labels = []                # list[TextLabel]
        self.overlays = []              # list[OverlayImage]
        self._z_counter = 1
        self.registry = ImageRegistry()

        self.selected = None            # ("label", index) or ("overlay", index)
        self.dragging = None
        self.last_mouse = None

        self.default_text_color = (0, 0, 0)
        self.drag_label = None

        self._setup_fonts()
        self._build_ui()
        self._set_window_icon()
        self._cleanup_pending_fonts()
        self._new_canvas(1600, 2200, fill=(255, 255, 255))

    def _set_window_icon(self):
        try:
            icon_path = os.path.join(_base_resource_dir(), "icon.png")
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                # Set window icon for taskbar and window header
                photo = ImageTk.PhotoImage(img)
                self.iconphoto(True, photo)
                self.registry.keep("window_icon", photo)
        except Exception as e:
            log_error(f"Error setting icon: {e}")

    # ------------------------------------------------------------------ UI
    def _setup_fonts(self):
        self.system_fonts = sorted(families(self))

    def _build_ui(self):
        # ---------- Header ----------
        header = tk.Frame(self, bg="#0b3d2e", height=64)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        try:
            icon = ImageTk.PhotoImage(Image.open(os.path.join(_base_resource_dir(), "icon.png"))
                                      .resize((44, 44)))
            self.registry.keep("appicon", icon)
            tk.Label(header, image=icon, bg="#0b3d2e").pack(side="left", padx=10, pady=10)
        except Exception:
            pass

        tk.Label(header, text=APP_TITLE,
                 font=Font(family="Segoe UI", size=16, weight="bold"),
                 fg="white", bg="#0b3d2e").pack(side="left", padx=6)

        tk.Label(header, text="Developed by Qazi Muhammad Umer Farooq Hajveri",
                 font=Font(family="Segoe UI", size=10), fg="#cfe9df",
                 bg="#0b3d2e").pack(side="right", padx=14)

        # ---------- Main split ----------
        main = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6)
        main.pack(fill="both", expand=True)

        self._build_control_panel(main)
        self._build_canvas_area(main)

    def _build_control_panel(self, parent):
        panel = tk.Frame(parent, bg="#f2f4f3", width=330)
        parent.add(panel, minsize=320)

        # --- Notebook modes ---
        self.notebook = ttk.Notebook(panel)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_poster = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_poster, text="  Poster  ")

        self.tab_fonts = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_fonts, text="  Fonts & Install  ")

        self._build_poster_tab()
        self._build_fonts_tab()

    def _build_fonts_tab(self):
        t = self._scrollable_tab(self.tab_fonts)
        pad = {"padx": 10, "pady": 8}

        tk.Label(t, text="Font Management (Urdu/Arabic)", bg="#f2f4f3",
                 font=Font(size=12, weight="bold")).pack(anchor="w", **pad)

        tk.Button(t, text="◉ Download & Install New Urdu Fonts", command=self.font_downloader,
                  bg="#2a5a9a", fg="white", font=Font(size=10, weight="bold"),
                  height=2).pack(fill="x", **pad)

        tk.Button(t, text="📁 Install Font File (.ttf/.otf) from PC", command=self.install_font_from_pc,
                  bg="#166f52", fg="white", font=Font(size=10)).pack(fill="x", **pad)

        tk.Button(t, text="❌ Remove / Uninstall Font", command=self.font_uninstaller,
                  bg="#b33b3b", fg="white", font=Font(size=10)).pack(fill="x", **pad)

        tk.Button(t, text="🔄 Refresh Font List", command=self._refresh_font_list,
                  bg="#888", fg="white").pack(fill="x", **pad)

        tk.Label(t, text="(Bundled fonts like Jameel Noori Nastaleeq are permanent)",
                 bg="#f2f4f3", fg="#666", font=Font(size=9)).pack(anchor="w", padx=12, pady=10)

    # ------------------------------------------------------------- POSTER
    def _scrollable_tab(self, parent):
        outer = tk.Frame(parent, bg="#f2f4f3")
        outer.pack(fill="both", expand=True)
        cv = tk.Canvas(outer, bg="#f2f4f3", highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        inner = tk.Frame(cv, bg="#f2f4f3")
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")

        def _config(e):
            cv.configure(scrollregion=cv.bbox("all"))
            cv.itemconfig(win_id, width=cv.winfo_width())

        def _wheel(e):
            cv.yview_scroll(int(-e.delta / 120), "units")

        inner.bind("<Configure>", _config)
        cv.bind("<MouseWheel>", _wheel)
        return inner

    def _build_poster_tab(self):
        t = self._scrollable_tab(self.tab_poster)
        pad = {"padx": 8, "pady": 4}

        tk.Button(t, text="1. Upload Picture (New Project)", command=self.upload_background,
                  bg="#0b3d2e", fg="white", font=Font(size=10, weight="bold")).pack(fill="x", **pad)

        tk.Button(t, text="Replace Background (Keep Design)", command=self.replace_background,
                  bg="#166f52", fg="white").pack(fill="x", **pad)

        tk.Button(t, text="2. Add Urdu Text", command=lambda: self.add_label(),
                  bg="#166f52", fg="white").pack(fill="x", **pad)

        tk.Button(t, text="3. Upload Logo / Overlay Image", command=self.upload_overlay,
                  bg="#b8860b", fg="white").pack(fill="x", **pad)

        # Overlay image size control (applies to the selected overlay image)
        osz = ttk.Frame(t)
        osz.pack(fill="x", **pad)
        tk.Label(osz, text="Image Size:", bg="#f2f4f3").pack(side="left")
        self.over_scale_var = tk.StringVar(value="1.00")
        ttk.Spinbox(osz, from_=0.1, to=5.0, increment=0.1, width=7,
                    textvariable=self.over_scale_var).pack(side="left", padx=4)
        tk.Button(osz, text="Apply", command=self.apply_overlay_scale).pack(side="left", padx=2)
        tk.Label(t, text="(selected image: drag its corner to resize too)",
                 bg="#f2f4f3", fg="#666", font=Font(size=8)).pack(anchor="w", padx=8)

        # Overlay independent horizontal/vertical size (applies to the selected image)
        owh = ttk.Frame(t)
        owh.pack(fill="x", **pad)
        tk.Label(owh, text="Width:", bg="#f2f4f3").pack(side="left")
        self.over_w_var = tk.StringVar(value="1.00")
        ttk.Spinbox(owh, from_=0.05, to=5.0, increment=0.05, width=5,
                    textvariable=self.over_w_var).pack(side="left", padx=2)
        tk.Label(owh, text="  Height:", bg="#f2f4f3").pack(side="left")
        self.over_h_var = tk.StringVar(value="1.00")
        ttk.Spinbox(owh, from_=0.05, to=5.0, increment=0.05, width=5,
                    textvariable=self.over_h_var).pack(side="left", padx=2)
        tk.Button(owh, text="Apply",
                  command=self.apply_overlay_size, bg="#b8860b", fg="white").pack(side="left", padx=2)
        tk.Label(t, text="(set horizontal / vertical size separately)",
                 bg="#f2f4f3", fg="#666", font=Font(size=8)).pack(anchor="w", padx=8)

        # Flip controls (apply to the selected overlay image)
        fl = ttk.Frame(t)
        fl.pack(fill="x", **pad)
        tk.Label(fl, text="Flip:", bg="#f2f4f3").pack(side="left")
        self.flip_h_var = tk.BooleanVar(value=False)
        self.flip_v_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(fl, text="Horizontal", variable=self.flip_h_var,
                        command=self.apply_overlay_flip).pack(side="left", padx=2)
        ttk.Checkbutton(fl, text="Vertical", variable=self.flip_v_var,
                        command=self.apply_overlay_flip).pack(side="left", padx=2)

        # Overlay rotation (applies to selected overlay image)
        orot = ttk.Frame(t)
        orot.pack(fill="x", **pad)
        tk.Label(orot, text="Rotate (deg):", bg="#f2f4f3").pack(side="left")
        self.over_rot_var = tk.IntVar(value=0)
        ttk.Spinbox(orot, from_=-180, to=180, textvariable=self.over_rot_var,
                    command=self.apply_overlay_rot, width=6).pack(side="left", padx=4)
        for d in (0, -90, 90, 180):
            tk.Button(orot, text=str(d), width=3,
                      command=lambda v=d: (self.over_rot_var.set(v), self.apply_overlay_rot())
                      ).pack(side="left", padx=1)

        # Overlay opacity (applies to selected overlay image)
        oop = ttk.Frame(t)
        oop.pack(fill="x", **pad)
        tk.Label(oop, text="Overlay Opacity %:", bg="#f2f4f3").pack(side="left")
        self.over_opacity_var = tk.IntVar(value=100)
        ttk.Spinbox(oop, from_=0, to=100, textvariable=self.over_opacity_var,
                    command=self.apply_overlay_opacity, width=5).pack(side="left", padx=4)

        # Crop + Background removal (apply to the selected overlay image)
        cc = ttk.Frame(t)
        cc.pack(fill="x", **pad)
        tk.Button(cc, text="Crop ...",
                  command=self.crop_overlay,
                  bg="#166f52", fg="white").pack(side="left", padx=2)
        tk.Button(cc, text="Remove Background",
                  command=self.remove_background,
                  bg="#e35f5f", fg="white").pack(side="left", padx=2)
        tk.Button(cc, text="Replace Image",
                  command=self.replace_overlay,
                  bg="#2a5a9a", fg="white").pack(side="left", padx=2)

        # Layer order (applies to the selected element)
        lr = ttk.Frame(t)
        lr.pack(fill="x", **pad)
        tk.Label(lr, text="Layer:", bg="#f2f4f3").pack(side="left")
        tk.Button(lr, text="To Front", command=lambda: self._layer_move("front"),
                  bg="#166f52", fg="white", width=8).pack(side="left", padx=2)
        tk.Button(lr, text="Forward", command=lambda: self._layer_move("forward"),
                  bg="#4a8c6f", fg="white", width=7).pack(side="left", padx=1)
        tk.Button(lr, text="Backward", command=lambda: self._layer_move("backward"),
                  bg="#4a8c6f", fg="white", width=7).pack(side="left", padx=1)
        tk.Button(lr, text="To Back", command=lambda: self._layer_move("back"),
                  bg="#166f52", fg="white", width=7).pack(side="left", padx=1)
        tk.Label(t, text="(text and images are stacked; highest layer shows on top)",
                 bg="#f2f4f3", fg="#666", font=Font(size=8)).pack(anchor="w", padx=8)


        # --- Selected label editor ---
        tk.Label(t, text="Selected Text Settings (click a label on canvas)",
                 bg="#f2f4f3", font=Font(size=9, weight="bold")).pack(anchor="w", **pad)

        # Font management (download / install / uninstall) - PROMINENT
        fmt = tk.LabelFrame(t, text=" Font Management (New) ", bg="#f2f4f3", padx=5, pady=5)
        fmt.pack(fill="x", **pad)

        tk.Button(fmt, text="◉ Download Urdu Fonts", command=self.font_downloader,
                  bg="#2a5a9a", fg="white", font=Font(size=10, weight="bold")).pack(
                  side="top", fill="x", pady=2)

        btn_row = ttk.Frame(fmt)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="Install from PC", command=self.install_font_from_pc,
                  bg="#166f52", fg="white", font=Font(size=8)).pack(
                  side="left", fill="x", expand=True, padx=(0, 1))
        tk.Button(btn_row, text="Remove Font", command=self.font_uninstaller,
                  bg="#b33b3b", fg="white", font=Font(size=8)).pack(
                  side="left", fill="x", expand=True, padx=(1, 0))

        tf = ttk.Frame(t)
        tf.pack(fill="x", **pad)
        tk.Label(tf, text="Text:", bg="#f2f4f3").pack(side="left")
        self.text_entry = ttk.Entry(tf)
        self.text_entry.pack(side="left", fill="x", expand=True)
        tk.Button(tf, text="Ø§Ø±Ø¯Ùˆ â‡—", command=lambda: self.open_urdu_keypad(
            self.text_entry, self.update_selected_text, self._update_text_preview),
            bg="#166f52", fg="white").pack(side="left", padx=2)
        tk.Button(tf, text="Set", command=self.update_selected_text).pack(side="left", padx=4)
        tk.Button(tf, text="+ New", command=self.add_new_text,
                  bg="#b8860b", fg="white", font=Font(size=9, weight="bold")).pack(side="left", padx=2)
        self.text_entry.bind("<Return>", lambda e: self.update_selected_text())
        self.text_entry.bind("<KeyRelease>", lambda e: self._update_text_preview())

        self.preview_var = tk.StringVar(value="")
        tk.Label(t, textvariable=self.preview_var, anchor="e",
                 bg="#ffffff", fg="#0b3d2e", font=Font(size=13),
                 wraplength=300, justify="right").pack(fill="x", padx=8, pady=2)
        self.preview_hint = tk.Label(t, text="â†‘ Ø§Ø±Ø¯Ùˆ (Ù¾ÛŒØ´ Ù†Ø¸Ø§Ø±Û) â€” Ù¾ÙˆØ³Ù¹Ø± Ù¾Ø± Ø§ÛŒØ³Û’ Ù„Ú¯Û’ Ú¯ÛŒ",
                                     bg="#f2f4f3", fg="#666", font=Font(size=8)).pack(anchor="e", padx=8)

        tk.Button(t, text="â—‰ Open Urdu Keypad (Ø§Ø±Ø¯Ùˆ Ù¾ÛŒÚˆ)",
                  command=lambda: self.open_urdu_keypad(self.text_entry, self.update_selected_text,
                                                        self._update_text_preview),
                  bg="#0b3d2e", fg="white", font=Font(size=9, weight="bold")).pack(fill="x", **pad)

        # Font selector
        self.font_var = tk.StringVar(value=DEFAULT_FONT)
        tk.Label(t, text="Font Selection (Urdu/Arabic):", bg="#f2f4f3", font=Font(size=9, weight="bold")).pack(anchor="w", **pad)
        f_list = sorted(list(URDU_FONTS.keys())) + self.system_fonts
        self.font_combo = ttk.Combobox(t, textvariable=self.font_var,
                                       values=f_list,
                                       state="readonly")
        self.font_combo.pack(fill="x", **pad)
        self.font_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_label_prop())

        # Size row
        sz = ttk.Frame(t)
        sz.pack(fill="x", **pad)
        tk.Label(sz, text="Size:", bg="#f2f4f3").pack(side="left")
        self.size_var = tk.IntVar(value=120)
        self.size_spin = ttk.Spinbox(sz, from_=8, to=1000, textvariable=self.size_var,
                                     command=self.apply_label_prop, increment=1, width=8)
        self.size_spin.pack(side="left", padx=4)
        tk.Button(sz, text="Color", command=self.pick_label_color).pack(side="left", padx=4)

        # Rotation
        rot = ttk.Frame(t)
        rot.pack(fill="x", **pad)
        tk.Label(rot, text="Rotate (deg):", bg="#f2f4f3").pack(side="left")
        self.rot_var = tk.IntVar(value=0)
        ttk.Spinbox(rot, from_=-90, to=90, textvariable=self.rot_var,
                    command=self.apply_label_prop, width=6).pack(side="left", padx=4)
        for d in (0, -90, 90):
            tk.Button(rot, text=str(d), width=3,
                      command=lambda v=d: (self.rot_var.set(v), self.apply_label_prop())
                      ).pack(side="left", padx=2)

        # Text opacity
        op = ttk.Frame(t)
        op.pack(fill="x", **pad)
        tk.Label(op, text="Text Opacity %:", bg="#f2f4f3").pack(side="left")
        self.opacity_var = tk.IntVar(value=100)
        ttk.Spinbox(op, from_=0, to=100, textvariable=self.opacity_var,
                    command=self.apply_label_prop, width=5).pack(side="left", padx=4)

        # Arc (curved) text
        ar = ttk.Frame(t)
        ar.pack(fill="x", **pad)
        tk.Label(ar, text="Arc (deg):", bg="#f2f4f3").pack(side="left")
        self.arc_var = tk.IntVar(value=0)
        ttk.Spinbox(ar, from_=-180, to=180, textvariable=self.arc_var,
                    command=self.apply_label_prop, increment=5, width=6).pack(side="left", padx=4)
        for d in (0, -45, 90, 180):
            tk.Button(ar, text=str(d), width=3,
                      command=lambda v=d: (self.arc_var.set(v), self.apply_label_prop())
                      ).pack(side="left", padx=1)
        tk.Label(t, text="(Arc bends the text into a curve: + up / - down)",
                 bg="#f2f4f3", fg="#666", font=Font(size=8)).pack(anchor="w", padx=8)

        # Word spacing
        ws = ttk.Frame(t)
        ws.pack(fill="x", **pad)
        tk.Label(ws, text="Word Spacing:", bg="#f2f4f3").pack(side="left")
        self.word_spacing_var = tk.IntVar(value=0)
        ttk.Spinbox(ws, from_=-100, to=500, textvariable=self.word_spacing_var,
                    command=self.apply_label_prop, increment=1, width=6).pack(side="left", padx=4)
        for v in (-10, 0, 10, 20):
            tk.Button(ws, text=str(v), width=3,
                      command=lambda val=v: (self.word_spacing_var.set(val), self.apply_label_prop())
                      ).pack(side="left", padx=1)
        tk.Label(t, text="(Extra space between words: negative = tighter)",
                 bg="#f2f4f3", fg="#666", font=Font(size=8)).pack(anchor="w", padx=8)

        tk.Button(t, text="Delete Selected", command=self.delete_selected,
                  bg="#b33b3b", fg="white").pack(fill="x", **pad)

        # --- Canvas background color ---
        ttk.Separator(t, orient="horizontal").pack(fill="x", padx=8, pady=8)
        bgrow = ttk.Frame(t)
        bgrow.pack(fill="x", **pad)
        tk.Label(bgrow, text="Blank canvas:\n", bg="#f2f4f3").pack(side="left")
        tk.Label(bgrow, text="Back color", bg="#f2f4f3").pack(side="left", padx=4)
        tk.Button(bgrow, text="\U000025a0", command=self.pick_canvas_color).pack(side="left")

    # ------------------------------------------------------------ CANVAS
    def _build_canvas_area(self, parent):
        wrap = tk.Frame(parent, bg="#4a4a4a")
        parent.add(wrap, minsize=600)

        toolbar = tk.Frame(wrap, bg="#dde5e1")
        toolbar.pack(side="top", fill="x")

        tk.Button(toolbar, text="Save JPG", command=lambda: self.save_image("jpg"),
                  bg="#166f52", fg="white", font=Font(size=10, weight="bold")).pack(side="left", padx=6, pady=6)
        tk.Button(toolbar, text="Save PNG", command=lambda: self.save_image("png"),
                  bg="#166f52", fg="white", font=Font(size=10, weight="bold")).pack(side="left", pady=6)
        tk.Button(toolbar, text="Save PDF", command=self.save_pdf,
                  bg="#b33b3b", fg="white", font=Font(size=10, weight="bold")).pack(side="left", padx=6, pady=6)
        tk.Button(toolbar, text="Save Project", command=self._save_project,
                  bg="#2a5a9a", fg="white", font=Font(size=10, weight="bold")).pack(side="left", padx=6, pady=6)
        tk.Button(toolbar, text="Open Project", command=self._load_project,
                  bg="#2a5a9a", fg="white", font=Font(size=10, weight="bold")).pack(side="left", pady=6)
        tk.Button(toolbar, text="New Canvas", command=self.new_canvas_prompt,
                  bg="#888").pack(side="left", padx=6, pady=6)
        tk.Button(toolbar, text="New Blank Card", command=lambda: self._new_canvas(1050, 660, fill=(235,240,244)),
                  bg="#888").pack(side="left", padx=6, pady=6)

        self.canvas = tk.Canvas(wrap, bg="#5a5a5a", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<KeyPress-Up>", lambda e: self._arrow_size(1, e.state))
        self.canvas.bind("<KeyPress-Right>", lambda e: self._arrow_size(1, e.state))
        self.canvas.bind("<KeyPress-Down>", lambda e: self._arrow_size(-1, e.state))
        self.canvas.bind("<KeyPress-Left>", lambda e: self._arrow_size(-1, e.state))

        tk.Label(wrap, text="Shortcut: click an element, then Arrow keys  /  -> + to resize  (Shift = big steps)",
                 bg="#dde5e1", fg="#445", font=Font(size=8)).pack(side="bottom", fill="x")

    # --------------------------------------------------------- CANVAS OPS
    def _new_canvas(self, w, h, fill=(255, 255, 255)):
        self.base_pil = Image.new("RGB", (w, h), fill)
        self.base_tk = None
        self.labels = []
        self.overlays = []
        self.selected = None
        self._refresh_canvas()

    def new_canvas_prompt(self):
        w = simpledialog.askinteger("New Canvas", "Width (px):", initialvalue=1600, parent=self)
        h = simpledialog.askinteger("New Canvas", "Height (px):", initialvalue=2200, parent=self)
        if w and h:
            self._new_canvas(w, h)

    def upload_background(self):
        path = filedialog.askopenfilename(
            title="Select background picture", parent=self,
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp")])
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image:\n{e}", parent=self)
            return
        self.base_pil = img
        self.labels = []
        self.overlays = []
        self.selected = None
        self._refresh_canvas()

    def replace_background(self):
        """Change the background image but KEEP labels and overlays."""
        if self.base_pil is None:
            self.upload_background()
            return

        path = filedialog.askopenfilename(
            title="Select replacement background", parent=self,
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp")])
        if not path:
            return
        try:
            # Load new background
            new_bg = Image.open(path).convert("RGB")
            # We preserve current design elements (labels and overlays)
            self.base_pil = new_bg
            self._refresh_canvas()
            messagebox.showinfo("Success", "Background replaced. Design preserved.")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image:\n{e}", parent=self)

    def upload_overlay(self):
        path = filedialog.askopenfilename(
            title="Select logo / overlay image", parent=self,
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if not path:
            return
        try:
            Image.open(path)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image:\n{e}", parent=self)
            return
        self.overlays.append(OverlayImage(path))
        self.overlays[-1].z = self._next_z()
        self.selected = ("overlay", len(self.overlays) - 1)
        self._sync_editor_from_selection()
        self._refresh_canvas()

    def replace_overlay(self):
        """Replace the source file of the selected overlay image."""
        ov, _ = self._selected_overlay()
        if ov is None:
            messagebox.showinfo("Replace", "پہلے پوسٹر پر ایک تصویر منتخب کریں جسے بدلنا چاہتے ہیں", parent=self)
            return
        path = filedialog.askopenfilename(
            title="Select replacement image", parent=self,
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if not path:
            return
        try:
            Image.open(path)
            ov.path = path
            ov.data = None  # Reset any previous crop/bg removal
            self._refresh_canvas()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image:\n{e}", parent=self)

    def pick_canvas_color(self):
        c = colorchooser.askcolor((255, 255, 255), title="Canvas background color", parent=self)
        if c and c[1] and self.base_pil:
            self.base_pil = Image.new("RGB", self.base_pil.size, c[0])
            self._refresh_canvas()
        elif c and c[1]:
            self.base_pil = Image.new("RGB", (1600, 2200), c[0])
            self._refresh_canvas()

    # ------------------------------------------------------------- LABELS
    def add_label(self):
        lbl = TextLabel(text="Ù†Ø¦ÛŒ ØªØ­Ø±ÛŒØ±", x=0.5, y=0.5,
                        size=self.size_var.get() or 60,
                        font_name=self._current_font_name(), z=self._next_z())
        lbl.opacity = self.opacity_var.get()
        lbl.arc_angle = self.arc_var.get()
        lbl.word_spacing = self.word_spacing_var.get()
        self.labels.append(lbl)
        self.selected = ("label", len(self.labels) - 1)
        self._sync_editor_from_selection()
        self._refresh_canvas()

    def open_urdu_keypad(self, target, apply_cb=None, on_change=None):
        """Open the Urdu on-screen keypad bound to a target widget."""
        try:
            kb = urdu_kb.UrduKeypad(self, target)
            if apply_cb:
                kb.set_apply_callback(apply_cb)
            if on_change:
                kb.set_on_change(on_change)
            self.update_idletasks()
            try:
                x = self.winfo_rootx() + self.winfo_width() - kb.winfo_reqwidth() - 20
                y = self.winfo_rooty() + 60
                kb.geometry(f"+{int(x)}+{int(y)}")
            except Exception:
                pass
            if not hasattr(self, "_keypads"):
                self._keypads = []
            self._keypads.append(kb)
        except Exception as e:
            messagebox.showerror("Keypad Error", str(e), parent=self)

    def _current_font_name(self):
        """Return the font selected in the combo if valid, else the default."""
        fn = self.font_var.get() if hasattr(self, "font_var") else DEFAULT_FONT
        if fn and (fn in URDU_FONTS or fn in self.system_fonts):
            return fn
        return DEFAULT_FONT

    # ------------------------------------------------------ FONT MANAGER
    def _refresh_font_list(self):
        """Re-scan installed fonts and update the font dropdown."""
        global URDU_FONTS
        URDU_FONTS = _collect_fonts()
        if hasattr(self, "font_combo") and self.font_combo.winfo_exists():
            self.font_combo["values"] = list(URDU_FONTS.keys()) + self.system_fonts
            cur = self.font_var.get()
            if cur not in URDU_FONTS and cur not in self.system_fonts:
                self.font_var.set(DEFAULT_FONT)

    def _validate_font(self, path):
        """Return (ok, reason) - a font is kept only when it loads and has
        Urdu/Arabic glyphs so it will actually render text."""
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

    def font_downloader(self):
        """Window to download free Urdu fonts and add them to the app."""
        win = tk.Toplevel(self)
        win.title("Download Urdu Fonts")
        win.geometry("560x480")
        win.transient(self)
        try:
            win.iconphoto(True, self.registry._refs.get("window_icon"))
        except Exception:
            pass

        tk.Label(win, text="Moft (free) Urdu / Arabic fonts - select one or more:",
                 anchor="w", font=Font(size=10, weight="bold")).pack(fill="x", padx=10, pady=(10, 4))
        lb = tk.Listbox(win, selectmode="extended", width=80, height=12, font=Font(size=10))
        lb.pack(fill="both", expand=True, padx=10)
        for f in ONLINE_FONTS:
            lb.insert("end", f["name"])
        lb.selection_set(0)

        self._font_status = tk.Label(win, text="Internet darkar hai (backend validation kar ke sahi font hi rakhe jayenge).",
                                     fg="#666", anchor="w", wraplength=520, justify="left",
                                     font=Font(size=9))
        self._font_status.pack(fill="x", padx=10, pady=4)

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=(2, 10))

        def start():
            names = [lb.get(i) for i in lb.curselection()]
            if not names:
                messagebox.showinfo("Download", "Koi font select nahi kiya.", parent=win)
                return
            self._font_status.config(text="Download ho rahe hain... thora intezar karein.", fg="#166f52")
            threading.Thread(target=self._download_worker, args=(names,), daemon=True).start()

        ttk.Button(bar, text="Download & Install", command=start).pack(side="left", padx=2)
        ttk.Button(bar, text="Install from PC...",
                   command=lambda: (self.install_font_from_pc(), win.destroy())).pack(side="left", padx=2)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right", padx=2)

        self._font_dl_win = win

    def _download_worker(self, names):
        """Background thread: download each font, validate, keep only good ones."""
        import urllib.request
        ok_list = []
        bad_list = []
        for name in names:
            entry = next((e for e in ONLINE_FONTS if e["name"] == name), None)
            if not entry:
                continue
            for fname, url in entry["files"]:
                dest = os.path.join(USER_FONT_DIR, fname)
                tmp = dest + ".part"
                try:
                    with urllib.request.urlopen(url, timeout=45) as r:
                        data = r.read()
                    with open(tmp, "wb") as fh:
                        fh.write(data)
                    good, reason = self._validate_font(tmp)
                    if good:
                        if os.path.exists(dest):
                            os.remove(dest)
                        os.replace(tmp, dest)
                        ok_list.append(fname)
                        self._ui_font_status(f"Installed: {fname}", "#166f52")
                    else:
                        self._cleanup_font(tmp)
                        bad_list.append(f"{name} ({reason})")
                except Exception as e:
                    self._cleanup_font(tmp)
                    bad_list.append(f"{name} ({e})")
        self.after(0, self._refresh_font_list)
        msg = f"Done! Installed: {', '.join(ok_list) if ok_list else 'kuch nahi'}"
        if bad_list:
            msg += f"\nNakam (rejected): {', '.join(bad_list)}"
        self._ui_font_status(msg, "#0b3d2e" if ok_list else "#b33b3b")

    def _ui_font_status(self, msg, color="#166f52"):
        def _apply():
            try:
                if hasattr(self, "_font_status") and self._font_status.winfo_exists():
                    self._font_status.config(text=msg, fg=color)
            except Exception:
                pass
        try:
            self.after(0, _apply)
        except Exception:
            pass

    @staticmethod
    def _cleanup_font(path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def install_font_from_pc(self):
        """Import a .ttf/.otf from disk and add it to the app's user fonts."""
        path = filedialog.askopenfilename(
            title="Select font file (.ttf / .otf)", parent=self,
            filetypes=[("Font files", "*.ttf *.otf"), ("All files", "*.*")])
        if not path:
            return
        try:
            good, reason = self._validate_font(path)
        except Exception as e:
            messagebox.showerror("Font", str(e), parent=self)
            return
        if not good:
            messagebox.showwarning("Invalid Font",
                                   f"Yeh font use nahi ho sakta:\n{reason}", parent=self)
            return
        fname = os.path.basename(path)
        dest = os.path.join(USER_FONT_DIR, fname)
        try:
            import shutil
            shutil.copyfile(path, dest)
        except Exception as e:
            messagebox.showerror("Error", f"Font install nahi hua:\n{e}", parent=self)
            return
        self._refresh_font_list()
        messagebox.showinfo("Font", f"Font install ho gaya:\n{fname}", parent=self)

    def font_uninstaller(self):
        """Window to remove a downloaded / imported font (bundled fonts stay)."""
        user_fonts = [(nm, p) for nm, p in URDU_FONTS.items()
                      if p and os.path.normpath(os.path.dirname(p)).lower()
                      == os.path.normpath(USER_FONT_DIR).lower()]

        win = tk.Toplevel(self)
        win.title("Uninstall Font")
        win.geometry("430x360")
        win.transient(self)
        try:
            win.iconphoto(True, self.registry._refs.get("window_icon"))
        except Exception:
            pass

        tk.Label(win, text="User fonts (download/import kare hue) - remove karne ke liye select karein:",
                 anchor="w", wraplength=400, font=Font(size=9)).pack(fill="x", padx=10, pady=(10, 4))
        lb = tk.Listbox(win, height=10, font=Font(size=10))
        lb.pack(fill="both", expand=True, padx=10)
        if not user_fonts:
            lb.insert("end", "(koi user font installed nahi hai)")
            lb.config(state="disabled")
        else:
            for nm, _p in user_fonts:
                lb.insert("end", nm)
            lb.selection_set(0)

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=8)

        def remove():
            sel = lb.curselection()
            if not user_fonts or not sel:
                return
            nm, p = user_fonts[sel[0]]
            if not messagebox.askyesno("Uninstall", f"'{nm}' ko remove karein?", parent=win):
                return
            # Drop our own memory-mapped font handles first (HarfBuzz/FreeType
            # lock the font file, which causes "access denied" / WinError 5).
            try:
                import urdu_render
                urdu_render.clear_caches()
            except Exception:
                pass
            result = self._force_delete_font(p)
            if result == "deleted":
                self._refresh_font_list()
                messagebox.showinfo("Uninstall", f"'{nm}' remove ho gaya.", parent=win)
                win.destroy()
            elif result == "restart":
                self._refresh_font_list()
                messagebox.showinfo("Uninstall",
                                    f"'{nm}' ke file par lock hai.\n"
                                    "Computer restart karne par ye automatic delete ho jayega.", parent=win)
                win.destroy()
            else:
                messagebox.showerror("Error",
                                     f"'{nm}' remove nahi ho saka (Windows error 5).\n"
                                     "App use karte waqt yahi font select na ho aur dobara koshish karein.", parent=win)

        ttk.Button(bar, text="Uninstall", command=remove).pack(side="left", padx=2)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right", padx=2)

    @staticmethod
    def _force_delete_font(path):
        """Delete a locked font file. Returns 'deleted' | 'restart' | 'failed'."""
        if not os.path.exists(path):
            return "deleted"
        # 1) Clear read-only attribute (fonts can arrive with ATTRIBUTE_READONLY).
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(path, 0x80)  # FILE_ATTRIBUTE_NORMAL
        except Exception:
            pass
        # 2) Retry a few times (gives the OS a moment to release the handle).
        for _ in range(6):
            try:
                os.remove(path)
                time.sleep(0.2)
                if not os.path.exists(path):
                    return "deleted"
            except Exception:
                time.sleep(0.3)
        # 3) Last resort: mark it for deletion on next reboot.
        try:
            import ctypes
            MOVEFILE_REPLACE_EXISTING = 0x1
            MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
            k32 = ctypes.windll.kernel32
            tmp = path + ".to_delete"
            if not k32.MoveFileExW(path, tmp, MOVEFILE_REPLACE_EXISTING):
                return "failed"
            if k32.MoveFileExW(tmp, None, MOVEFILE_DELAY_UNTIL_REBOOT):
                return "restart"
            # failed to schedule; move it back
            k32.MoveFileExW(tmp, path, MOVEFILE_REPLACE_EXISTING)
            return "failed"
        except Exception:
            return "failed"

    @staticmethod
    def _cleanup_pending_fonts():
        """On startup, finish deleting leftover font files queued for removal."""
        try:
            for root, _dirs, files in os.walk(USER_FONT_DIR):
                for fn in files:
                    if fn.endswith(".to_delete"):
                        try:
                            os.remove(os.path.join(root, fn))
                        except Exception:
                            pass
        except Exception:
            pass

    def update_selected_text(self):
        txt = self.text_entry.get()
        if self.selected and self.selected[0] == "label":
            i = self.selected[1]
            lbl = self.labels[i]
            lbl.text = urdu_text.normalize(txt)
            # Apply the currently-selected font/size to this label too.
            try:
                lbl.size = int(self.size_var.get())
            except Exception:
                pass
            try:
                lbl.word_spacing = int(self.word_spacing_var.get())
            except Exception:
                pass
            fn = self._current_font_name()
            self.labels[i].font_name = fn
            self._refresh_canvas()
        elif not self.selected:
            self.add_label_to_text(txt)
        self._update_text_preview()

    def _update_text_preview(self):
        try:
            txt = self.text_entry.get()
            self.preview_var.set(urdu_text.plain(txt))
        except Exception:
            pass

    def add_label_to_text(self, txt):
        txt = urdu_text.normalize(txt)
        lbl = TextLabel(text=txt, x=0.5, y=0.5, size=self.size_var.get() or 60,
                        font_name=self._current_font_name(), z=self._next_z())
        lbl.opacity = self.opacity_var.get()
        lbl.arc_angle = self.arc_var.get()
        lbl.word_spacing = self.word_spacing_var.get()
        self.labels.append(lbl)
        self.selected = ("label", len(self.labels) - 1)
        self._refresh_canvas()

    def add_new_text(self):
        """Always create a NEW text label (a new column/box), stacking below the
        previous one so several independent Urdu texts can be written."""
        txt = self.text_entry.get() or "Ù†Ø¦ÛŒ ØªØ­Ø±ÛŒØ±"
        txt = urdu_text.normalize(txt)
        # place new label slightly below the most recent one
        i = len(self.labels)
        x = 0.5
        y = 0.5 + i * 0.08
        if y > 0.9:
            y = 0.9
        lbl = TextLabel(text=txt, x=x, y=y, size=self.size_var.get() or 60,
                        font_name=self._current_font_name(), z=self._next_z())
        lbl.opacity = self.opacity_var.get()
        lbl.arc_angle = self.arc_var.get()
        lbl.word_spacing = self.word_spacing_var.get()
        self.labels.append(lbl)
        self.selected = ("label", len(self.labels) - 1)
        self._sync_editor_from_selection()
        self._refresh_canvas()

    def pick_label_color(self):
        cur = self.default_text_color
        if self.selected and self.selected[0] == "label":
            cur = self.labels[self.selected[1]].color
        c = colorchooser.askcolor(cur, title="Text color", parent=self)
        if c and c[0]:
            self.default_text_color = tuple(int(v) for v in c[0])
            if self.selected and self.selected[0] == "label":
                self.labels[self.selected[1]].color = self.default_text_color
                self._refresh_canvas()

    def apply_label_prop(self):
        if self.selected and self.selected[0] == "label":
            i = self.selected[1]
            lbl = self.labels[i]
            try:
                lbl.size = int(self.size_var.get())
            except Exception:
                pass
            try:
                lbl.rotation = int(self.rot_var.get())
            except Exception:
                pass
            try:
                lbl.opacity = max(0, min(100, int(self.opacity_var.get())))
            except Exception:
                pass
            try:
                lbl.arc_angle = int(self.arc_var.get())
            except Exception:
                pass
            try:
                lbl.word_spacing = int(self.word_spacing_var.get())
            except Exception:
                pass
            fn = self.font_var.get()
            if fn and (fn in URDU_FONTS or fn in self.system_fonts):
                lbl.font_name = fn
            self._refresh_canvas()

    def apply_overlay_scale(self):
        if self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if i < len(self.overlays):
                try:
                    v = max(0.05, min(5.0, float(self.over_scale_var.get())))
                    self.overlays[i].scale = v
                    self.overlays[i].scale_x = v
                    self.overlays[i].scale_y = v
                    self.over_w_var.set(f"{v:.2f}")
                    self.over_h_var.set(f"{v:.2f}")
                except Exception:
                    pass
                self._refresh_canvas()

    def apply_overlay_size(self):
        """Apply independent horizontal/vertical scale to the selected overlay."""
        if self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if i < len(self.overlays):
                try:
                    wx = max(0.05, min(5.0, float(self.over_w_var.get())))
                    wy = max(0.05, min(5.0, float(self.over_h_var.get())))
                    self.overlays[i].scale_x = wx
                    self.overlays[i].scale_y = wy
                except Exception:
                    pass
                self._refresh_canvas()

    def apply_overlay_flip(self):
        """Apply flip checkboxes to the selected overlay image."""
        if self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if i < len(self.overlays):
                self.overlays[i].flip_h = bool(self.flip_h_var.get())
                self.overlays[i].flip_v = bool(self.flip_v_var.get())
                self._refresh_canvas()

    def _selected_overlay(self):
        """Return the selected OverlayImage and its index, or (None, -1)."""
        if self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if 0 <= i < len(self.overlays):
                return self.overlays[i], i
        return None, -1

    def _show_ov_message(self, msg):
        messagebox.showinfo("Overlay Image", msg, parent=self)

    def crop_overlay(self):
        """Open a window to draw a crop box over the selected overlay image."""
        ov, _ = self._selected_overlay()
        if ov is None:
            messagebox.showinfo("Crop", "پہلے پوسٹر پر ایک تصویر منتخب کریں", parent=self)
            return
        try:
            src = ov.open()
        except Exception as e:
            messagebox.showerror("Crop", f"Cannot load image:\n{e}", parent=self)
            return

        win = tk.Toplevel(self)
        win.title("Crop Image - draw a box then press OK")
        maxw, maxh = 700, 500
        s = min(maxw / src.width, maxh / src.height, 3.0)
        disp = (int(src.width * s), int(src.height * s))
        disp = (max(disp[0], 20), max(disp[1], 20))
        canvas = tk.Canvas(win, width=disp[0] + 20, height=disp[1] + 20, bg="#444")
        canvas.pack()
        tb = {}
        try:
            base_tk = self.registry.keep("crop_base",
                                         ImageTk.PhotoImage(src.resize(disp, Image.LANCZOS)))
        except Exception:
            base_tk = self.registry.keep("crop_base", ImageTk.PhotoImage(src))
        rect_id = [None]
        start = {"x": 0, "y": 0}
        box = {"l": 0, "t": 0, "r": src.width, "b": src.height}

        def disp_pos(cv):
            return cv.winfo_pointerx() - cv.winfo_rootx() - 10, \
                   cv.winfo_pointery() - cv.winfo_rooty() - 10

        def on_down(e):
            start["x"], start["y"] = e.x - 10, e.y - 10

        def on_move(e):
            x, y = e.x - 10, e.y - 10
            if rect_id[0] is not None:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(start["x"], start["y"], x, y,
                                                 outline="#ff2d55", width=2)

        def on_up(e):
            x, y = e.x - 10, e.y - 10
            l = min(start["x"], x) / disp[0] * src.width
            t = min(start["y"], y) / disp[1] * src.height
            r = max(start["x"], x) / disp[0] * src.width
            b = max(start["y"], y) / disp[1] * src.height
            box["l"], box["t"], box["r"], box["b"] = \
                int(max(l, 0)), int(max(t, 0)), int(min(r, src.width)), int(min(b, src.height))
            if box["r"] - box["l"] < 2 or box["b"] - box["t"] < 2:
                # reset to full image
                box["l"], box["t"], box["r"], box["b"] = 0, 0, src.width, src.height

        canvas.create_image(10, 10, image=base_tk, anchor="nw")
        canvas.bind("<ButtonPress-1>", on_down)
        canvas.bind("<B1-Motion>", on_move)
        canvas.bind("<ButtonRelease-1>", on_up)

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=6, pady=6)

        def apply_crop():
            if box["r"] - box["l"] >= 2 and box["b"] - box["t"] >= 2:
                ov.crop = (box["l"], box["t"], box["r"], box["b"])
                self._refresh_canvas()
                self._show_ov_message("تصویر کاٹ دی گئی (crop)۔")
            win.destroy()

        ttk.Button(bar, text="OK (Apply Crop)", command=apply_crop).pack(side="left")
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left", padx=6)
        if ov.data is not None or ov.crop is not None:
            ttk.Button(bar, text="Reset Crop", command=lambda: (
                setattr(ov, "crop", None), self._refresh_canvas(), win.destroy())).pack(
                side="left", padx=6)

    def remove_background(self):
        """Remove the background of the selected overlay using rembg (u2netp)."""
        ov, _ = self._selected_overlay()
        if ov is None:
            messagebox.showinfo("Remove Background", "پہلے پوسٹر پر ایک تصویر منتخب کریں", parent=self)
            return
        try:
            import rembg
        except Exception as e:
            log_error(f"remove_background import rembg: {e}")
            messagebox.showerror("Remove Background",
                                 f"Background removal module is not available:\n{e}", parent=self)
            return
        # Point rembg at the bundled u2netp model so it works fully offline.
        try:
            meipass = getattr(sys, "_MEIPASS", None) or (
                os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None)
            if meipass:
                bundled = os.path.join(meipass, "models", "u2netp", "u2netp.onnx")
                if os.path.exists(bundled):
                    os.environ["U2NET_HOME"] = meipass
        except Exception:
            pass
        try:
            src = ov.open()
        except Exception as e:
            messagebox.showerror("Remove Background", f"Cannot load image:\n{e}", parent=self)
            return
        messagebox.showinfo("Remove Background",
                            "پس منظر ہٹایا جا رہا ہے، براہ کرم چند سیکنڈ انتظار کریں...", parent=self)
        try:
            # small fast model; session is cached across calls for speed
            if not getattr(self, "_rembg_session", None):
                self._rembg_session = rembg.new_session("u2netp")
            result = rembg.remove(src, session=self._rembg_session)
            result = result.convert("RGBA")
        except Exception as e:
            log_error(f"remove_background: {e}")
            messagebox.showerror("Remove Background",
                                 f"پس منظر ہٹانے میں خرابی (انٹرنیٹ درکار ہو سکتا ہے):\n{e}", parent=self)
            return
        ov.data = result
        ov.crop = None
        self._refresh_canvas()
        self._show_ov_message("پس منظر کامیابی سے ہٹا دیا گیا — تصویر اب شفاف ہے۔")

    def delete_selected(self):
        if not self.selected:
            return
        kind, i = self.selected
        if kind == "label" and i < len(self.labels):
            del self.labels[i]
        elif kind == "overlay" and i < len(self.overlays):
            del self.overlays[i]
        self.selected = None
        self._refresh_canvas()

    # ------------------------------------------------------------ LAYERS
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

    def _layer_move(self, mode):
        if not self.selected:
            return
        kind, idx = self.selected
        el = self._get_element(kind, idx)
        if el is None:
            return
        others = []
        for j, o in enumerate(self.overlays):
            if not (kind == "overlay" and j == idx):
                others.append(o)
        for j, l in enumerate(self.labels):
            if not (kind == "label" and j == idx):
                others.append(l)
        self._layer_adjust(el, others, mode)
        self._refresh_canvas()

    def apply_overlay_rot(self):
        if self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if i < len(self.overlays):
                try:
                    self.overlays[i].rotation = int(self.over_rot_var.get())
                except Exception:
                    pass
                self._refresh_canvas()

    def apply_overlay_opacity(self):
        if self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if i < len(self.overlays):
                try:
                    self.overlays[i].opacity = max(0, min(100, int(self.over_opacity_var.get())))
                except Exception:
                    pass
                self._refresh_canvas()

    # ------------------------------------------------------------ RENDER
    def _load_font(self, size):
        name = self.font_var.get() if hasattr(self, "font_var") else DEFAULT_FONT
        return self._get_font(name, size)

    def _get_font(self, name, size):
        # Honour an explicitly selected bundled font so the font picker is real.
        if name and name in URDU_FONTS:
            try:
                return ImageFont.truetype(URDU_FONTS[name], int(size))
            except Exception:
                pass
        # Otherwise use the safe, always-available embedded Naskh as default
        # (thin, readable Urdu - never a solid black block). Nastaliq is
        # heavy/wide and at big sizes can look like a solid black box.
        try:
            import io, base64 as _b64
            raw = fonts_res.NASKH_B64
            data = raw.encode("ascii") if isinstance(raw, str) else raw
            return ImageFont.truetype(io.BytesIO(_b64.b64decode(data)), int(size))
        except Exception:
            pass
        # try the named bundled font as a fallback
        if name and name in URDU_FONTS:
            try:
                return ImageFont.truetype(URDU_FONTS[name], int(size))
            except Exception:
                pass
        elif URDU_FONTS:
            # fallback to any bundled Urdu font so Urdu never becomes tofu boxes
            try:
                return ImageFont.truetype(next(iter(URDU_FONTS.values())), int(size))
            except Exception:
                pass
        # embedded Nastaliq as a last backup
        try:
            import io, base64 as _b64
            raw = fonts_res.NASTALIQ_B64
            data = raw.encode("ascii") if isinstance(raw, str) else raw
            return ImageFont.truetype(io.BytesIO(_b64.b64decode(data)), int(size))
        except Exception:
            pass
        # system font fallback
        try:
            from tkinter import font as tkfont
            return ImageFont.truetype(tkfont.nametofont(name).actual("family") + ".ttf", int(size))
        except Exception:
            return ImageFont.load_default()

    def _font_path_for(self, font_name):
        """Resolve a font name to an on-disk ttf/otf path ('' if none)."""
        if font_name and font_name in URDU_FONTS:
            return URDU_FONTS[font_name]
        return ""

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _font_lacks_pf_cached(font_path):
        """Cached cmap inspection (TTFont parse is costly on 10+ MB fonts)."""
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

    def _split_logic_runs(self, text):
        """Split LOGICAL (base) text into (is_urdu, segment) runs for
        mixed Urdu/Latin labels rendered through the HarfBuzz fallback."""
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

    def _render_urdu_hb(self, font_path, size, text, color, alpha=255):
        """Render one logical Urdu text run via HarfBuzz+FreeType.

        Returns a transparent RGBA image and (advance, height).
        """
        try:
            assert _HB_AVAILABLE, "harfbuzz fallback unavailable"
            return urdu_render.render(font_path, text, max(int(size), 4),
                                      tuple(color), alpha)
        except Exception:
            return None

    def _render_label(self, img, draw, lbl, scale=1.0):
        if not lbl.text.strip():
            return

        font_size = max(int(lbl.size * scale), 4)
        font_path = self._font_path_for(lbl.font_name)
        alpha = int(255 * lbl.opacity / 100)
        ws = max(-200, min(500, int(getattr(lbl, "word_spacing", 0))))

        # Detect if font needs HarfBuzz (Nastaliq) or can use fast legacy path (Naskh/Arabic)
        needs_hb = _HB_AVAILABLE and font_path and self._font_lacks_pf_cached(font_path)

        if needs_hb:
            # --- HarfBuzz Path (for Nastaliq) ---
            runs = self._split_logic_runs(lbl.text)
            all_parts = []
            tw = 0
            mh = 0

            for seg_text, is_urdu in runs:
                if is_urdu:
                    # For Nastaliq, we shape word-by-word to support word spacing
                    words = re.split(r"([ ]+)", seg_text)
                    for word in words:
                        if not word: continue
                        if word.strip() == "":
                            try:
                                _, adv = urdu_render.render(font_path, " ", font_size, tuple(lbl.color), 255)
                                gap = (adv + ws) * len(word)
                                all_parts.append((None, gap))
                                tw += gap
                            except Exception: pass
                        else:
                            try:
                                part, adv = urdu_render.render(font_path, word, font_size, tuple(lbl.color), 255)
                                all_parts.append((part, adv))
                                tw += adv
                                mh = max(mh, part.height)
                            except Exception: pass
                else:
                    # Latin run
                    f_latin = self._get_latin_font(font_size)
                    for pt, pw, pb in self._text_pieces(seg_text, f_latin, ws):
                        if pt:
                            lp_layer = Image.new("RGBA", (int(pw) + 10, int(max(pb[3]-pb[1], 1)) + 10), (0,0,0,0))
                            ImageDraw.Draw(lp_layer).text((-pb[0]+2, -pb[1]+2), pt, font=f_latin, fill=lbl.color + (255,))
                            all_parts.append((lp_layer, pw))
                        else:
                            all_parts.append((None, pw))
                        tw += pw
                        mh = max(mh, pb[3] - pb[1])

            if not all_parts: return
            text_layer = Image.new("RGBA", (max(int(tw), 1) + 100, max(int(mh), 1) + 200), (0, 0, 0, 0))
            curr_x = 50
            for part, adv in all_parts:
                if part:
                    # Nastaliq baseline can vary, we try to align at center of the 200px vertical space
                    text_layer.alpha_composite(part, (int(curr_x), 100 - part.height // 2))
                curr_x += adv
            if alpha < 255:
                a = text_layer.getchannel("A").point(lambda v: int(v * alpha / 255))
                text_layer.putalpha(a)
        else:
            # --- Legacy Path (for Naskh/Arabic/Latin) ---
            txt = urdu_text.shape(lbl.text)
            if not txt: return
            runs = self._split_visual_runs(txt)
            f_urdu = self._get_font(lbl.font_name, font_size)
            f_latin = self._get_latin_font(font_size)
            segments = []
            tw = 0
            mh = 0
            for t, is_latin in runs:
                fo = f_latin if is_latin else f_urdu
                for pt, pw, pb in self._text_pieces(t, fo, ws):
                    segments.append((pt, fo, pw, pb))
                    tw += pw
                    mh = max(mh, pb[3] - pb[1])
            text_layer = Image.new("RGBA", (max(int(tw), 1) + 60, max(int(mh), 1) + 60), (0, 0, 0, 0))
            ld = ImageDraw.Draw(text_layer)
            curr_x = 30
            for pt, fo, w, b in segments:
                if pt:
                    ld.text((curr_x - b[0], 30 - b[1]), pt, font=fo, fill=lbl.color + (alpha,))
                curr_x += w

        if lbl.arc_angle:
            text_layer = self._arc_warp(text_layer, lbl.arc_angle)
        if lbl.rotation:
            text_layer = text_layer.rotate(lbl.rotation, expand=True, resample=Image.BICUBIC)

        cx, cy = int(lbl.x * img.width), int(lbl.y * img.height)
        px, py = cx - text_layer.width // 2, cy - text_layer.height // 2
        img.paste(text_layer, (px, py), text_layer)

    def _arc_warp(self, img, arc_deg):
        """Bend a rendered text bitmap along a circular arc.

        Uses a multi-strip MESH transform so joined Urdu letters stay
        connected (a geometric warp, not per-glyph redraw). Positive angle
        arches upward, negative arches downward.
        """
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
        import math
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

    def _split_visual_runs(self, txt):
        """Split a visual-order string into (text, is_latin) runs.

        Urdu/Arabic code points are kept together (rendered with the Urdu
        font); Latin letters, digits and punctuation (especially dashes) are
        merged so they render with a latin font and never appear as boxes.

        The two Urdu fonts and Arial prefer OPPOSITE dash code points:
          - NotoNaskhArabic renders U+2010 (HYPHEN) as a thin line but the
            ASCII U+002D as a solid box.
          - Arial renders U+002D as a thin line but U+2010 as a wide box.
        ``text.shape()`` normalizes every dash to U+2010 (good for the Urdu
        font), so we convert it back to U+002D for latin runs rendered with
        the latin font.
        """
        runs = []
        cur_latin = None
        cur = []
        for ch in txt:
            o = ord(ch)
            # Urdu/Arabic blocks + common Urdu letters
            is_urdu_char = (
                0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or
                0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF or
                o in (0x06D2, 0x06D0, 0x06CC, 0x0640)
            )
            # TREAT SPACES AS LATIN: This prevents the vertical bar artifacts
            # found in many Urdu fonts when rendering the space character.
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
        # Re-map dashes for latin runs: the latin font wants ASCII U+002D.
        runs = [(t.replace("\u2010", "-")
                 .replace("\u2013", "-")
                 .replace("\u0020", "\u2009")   # Urdu word gap -> thin space (less margin)
                 if isl else t, isl) for t, isl in runs]
        # Urdu runs: make inter-word space near-zero so gaps disappear (user
        # requested 0 margin). ZWNJ (U+200C) separates letters without spacing
        # them apart and without joining them.
        runs = [(t.replace("\u0020", "\u200c") if not isl else t, isl)
                for t, isl in runs]
        return runs

    def _text_pieces(self, text, font, ws):
        """Split text into drawable chunks; every space becomes a gap whose
        width is the natural space width plus the word-spacing offset ws
        (negative = tighter, positive = wider). Returns (text, w, bbox)."""
        import re
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

    def _get_latin_font(self, size):
        """Return a reliable latin font (real file) for numbers/dashes."""
        if not getattr(self, "_latin_font", None) or \
           getattr(self, "_latin_font_size", None) != size:
            path = None
            for cand in (r"C:\Windows\Fonts\arial.ttf",
                         r"C:\Windows\Fonts\segoeui.ttf",
                         r"C:\Windows\Fonts\calibri.ttf",
                         r"C:\Windows\Fonts\verdana.ttf"):
                if os.path.exists(cand):
                    path = cand
                    break
            self._latin_font_size = size
            try:
                self._latin_font = ImageFont.truetype(path, size) if path \
                    else ImageFont.load_default()
            except Exception:
                self._latin_font = ImageFont.load_default()
        return self._latin_font

    def _draw_overlays_and_labels(self, img, scale):
        draw = ImageDraw.Draw(img)
        items = [("overlay", i, ov.z) for i, ov in enumerate(self.overlays)]
        items += [("label", i, lbl.z) for i, lbl in enumerate(self.labels)]
        items.sort(key=lambda it: it[2])
        for kind, idx, _z in items:
            if kind == "overlay":
                try:
                    self._draw_overlay(img, self.overlays[idx], scale)
                except Exception:
                    continue
            else:
                try:
                    self._render_label(img, draw, self.labels[idx], scale)
                except Exception:
                    continue

    def _draw_overlay(self, img, ov, scale):
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

    def _refresh_canvas(self):
        """Redraw the on-screen preview (fast: renders at screen size only)."""
        if self.base_pil is None:
            return
        cav = self.canvas
        cav_w = max(cav.winfo_width(), 400)
        cav_h = max(cav.winfo_height(), 500)

        self.current_scale = min(cav_w / self.base_pil.width, cav_h / self.base_pil.height)
        self.current_scale = max(self.current_scale, 0.05)
        disp_w = int(self.base_pil.width * self.current_scale)
        disp_h = int(self.base_pil.height * self.current_scale)
        disp_w = max(disp_w, 1)
        disp_h = max(disp_h, 1)

        preview = self._render_preview(disp_w, disp_h)
        self.base_tk = ImageTk.PhotoImage(preview)
        self.registry.keep("preview", self.base_tk)

        self.offset_x = (cav_w - disp_w) // 2
        self.offset_y = (cav_h - disp_h) // 2

        cav.delete("all")
        self.canvas_image_id = cav.create_image(self.offset_x, self.offset_y,
                                                image=self.base_tk, anchor="nw")
        self._draw_selection_outline(cav)

    def _draw_selection_outline(self, cav):
        """Draw a bounding box + corner handles around the selected element (subtle)."""
        if not self.selected:
            return
        kind, i = self.selected
        if kind not in ("label", "overlay"):
            return
        box = self._element_box(kind, i)
        if box is None:
            return
        cx, cy, hw, hh = box
        x0, y0 = self._img_to_canvas(cx - hw, cy - hh)
        x1, y1 = self._img_to_canvas(cx + hw, cy + hh)
        # Subtle selection outline
        cav.create_rectangle(x0, y0, x1, y1, outline="#cccccc", width=1, dash=(2, 4))
        s = 3
        for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            cav.create_rectangle(px - s, py - s, px + s, py + s, fill="#ffffff",
                                 outline="#999999", width=1)

    def _render_preview(self, dw, dh):
        """Render at a given display size (fast path for on-screen preview)."""
        scale = dw / self.base_pil.width
        try:
            img = self.base_pil.convert("RGB").resize((dw, dh), Image.LANCZOS)
        except Exception:
            img = self.base_pil.convert("RGB")
        self._draw_overlays_and_labels(img, scale)
        return img

    def _img_to_canvas(self, img_x, img_y):
        return (self.offset_x + img_x * self.current_scale,
                self.offset_y + img_y * self.current_scale)

    def _canvas_to_img(self, cx, cy):
        return ((cx - self.offset_x) / self.current_scale,
                (cy - self.offset_y) / self.current_scale)

    # -------------------------------------------------------------- EVENTS
    def _on_configure(self, e):
        self._refresh_canvas()

    def _hit_test(self, cx, cy):
        best = None
        best_d = 1e9
        # overlays (grab over the whole rendered image area, not just centre)
        for i, ov in enumerate(self.overlays):
            img_x, img_y = self._canvas_to_img(cx, cy)
            try:
                _o = ov.open()
                ow = max(self.base_pil.width, 4) * 0.3 * ov.scale_x
                oh = _o.height * (max(self.base_pil.width, 4) * 0.3 / max(_o.width, 1)) * ov.scale_y
            except Exception:
                ow = oh = 80
            if abs(img_x - ov.x * self.base_pil.width) < ow / 2 and \
               abs(img_y - ov.y * self.base_pil.height) < oh / 2:
                d = (img_x - ov.x * self.base_pil.width) ** 2 + (img_y - ov.y * self.base_pil.height) ** 2
                if d < best_d:
                    best_d = d
                    best = ("overlay", i)
        for i, lbl in enumerate(self.labels):
            img_x, img_y = self._canvas_to_img(cx, cy)
            d = (img_x - lbl.x * self.base_pil.width) ** 2 + (img_y - lbl.y * self.base_pil.height) ** 2
            if d < best_d and d < (max(lbl.size * 2, 40) ** 2):
                best_d = d
                best = ("label", i)
        return best

    def _on_press(self, e):
        self.canvas.focus_set()
        self.resizing = False
        corner = self._hit_corner(e.x, e.y)
        if corner:
            kind, i = corner
            self.selected = corner
            self.dragging = (kind, i)
            self.resizing = True
            self._resize_ratio = self._resize_ratio_for(kind, i)
            self.canvas.config(cursor="fleur")
            self._sync_editor_from_selection()
            return
        hit = self._hit_test(e.x, e.y)
        if hit:
            self.selected = hit
            self.dragging = hit
            img_x, img_y = self._canvas_to_img(e.x, e.y)
            kind, i = hit
            if kind == "label" and i < len(self.labels):
                lbl = self.labels[i]
                self.drag_off = (lbl.x * self.base_pil.width - img_x,
                                 lbl.y * self.base_pil.height - img_y)
            elif kind == "overlay" and i < len(self.overlays):
                ov = self.overlays[i]
                self.drag_off = (ov.x * self.base_pil.width - img_x,
                                 ov.y * self.base_pil.height - img_y)
            self.canvas.config(cursor="fleur")
            self._sync_editor_from_selection()
        else:
            self.selected = None
            self._refresh_canvas()

    def _on_motion(self, e):
        if self.dragging is None:
            return
        kind, i = self.dragging
        img_x, img_y = self._canvas_to_img(e.x, e.y)
        if getattr(self, "resizing", False):
            self._do_resize(i, img_x, img_y)
            self._schedule_refresh()
            return
        offx, offy = self.drag_off
        if kind == "label" and i < len(self.labels):
            lbl = self.labels[i]
            lbl.x = max(0.0, min(1.0, (img_x + offx) / self.base_pil.width))
            lbl.y = max(0.0, min(1.0, (img_y + offy) / self.base_pil.height))
        elif kind == "overlay" and i < len(self.overlays):
            ov = self.overlays[i]
            ov.x = max(0.0, min(1.0, (img_x + offx) / self.base_pil.width))
            ov.y = max(0.0, min(1.0, (img_y + offy) / self.base_pil.height))
        self._schedule_refresh()

    # --- resize helpers -------------------------------------------------
    def _element_box(self, kind, i):
        """Return (cx, cy, half_w, half_h) in full-image pixels for an element."""
        w = self.base_pil.width
        h = self.base_pil.height
        if kind == "label" and i < len(self.labels):
            lbl = self.labels[i]
            cx, cy, half_w, half_h = lbl.x * w, lbl.y * h, \
                max(lbl.size * 1.4, 30) / 2, max(lbl.size * 0.45, 14) / 2
        elif kind == "overlay" and i < len(self.overlays):
            ov = self.overlays[i]
            cx, cy = ov.x * w, ov.y * h
            try:
                _o = ov.open()
                base_w = max(w, 4) * 0.3
                half_w = (base_w * ov.scale_x) / 2
                half_h = (_o.height * (base_w / max(_o.width, 1)) * ov.scale_y) / 2
            except Exception:
                half_w = half_h = 40
        else:
            return None
        return (cx, cy, half_w, half_h)

    def _hit_corner(self, cx, cy):
        """If click is near a corner of the currently selected element, return it."""
        if not self.selected:
            return None
        kind, i = self.selected
        if kind not in ("label", "overlay"):
            return None
        box = self._element_box(kind, i)
        if box is None:
            return None
        cx0, cy0, hw, hh = box
        img_x, img_y = self._canvas_to_img(cx, cy)
        thr = max(30 * self.current_scale, 12)
        # four corners
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            if abs(img_x - (cx0 + sx * hw)) < thr and abs(img_y - (cy0 + sy * hh)) < thr:
                return (kind, i)
        return None

    def _read_size(self, sel):
        kind, i = sel
        if kind == "label" and i < len(self.labels):
            return self.labels[i].size
        if kind == "overlay" and i < len(self.overlays):
            return self.overlays[i].scale
        return None

    def _resize_ratio_for(self, kind, i):
        """Fixed multiplier from element's current size to its corner half-width,
        so corner-drag resizing stays stable."""
        if kind == "label" and i < len(self.labels):
            halfw = max(self.labels[i].size * 1.4, 30) / 2
            return self.labels[i].size / max(halfw, 1)
        if kind == "overlay" and i < len(self.overlays):
            ov = self.overlays[i]
            halfw = (max(self.base_pil.width, 4) * 0.3 * ov.scale_x) / 2
            return ov.scale_x / max(halfw, 1)
        return 1.0

    def _do_resize(self, i, img_x, img_y):
        sel = self.selected
        if not sel:
            return
        kind, idx = sel
        if idx != i:
            return
        box = self._element_box(kind, idx)
        if box is None:
            return
        cx0, cy0, hw, hh = box
        dist = abs(img_x - cx0)
        # keep it from collapsing
        dist = max(dist, 12)
        ratio = self._resize_ratio
        if kind == "label" and idx < len(self.labels):
            self.labels[idx].size = max(8, int(ratio * dist))
            if hasattr(self, "size_var"):
                self.size_var.set(self.labels[idx].size)
        elif kind == "overlay" and idx < len(self.overlays):
            ov = self.overlays[idx]
            prev_x = ov.scale_x
            ov.scale_x = max(0.05, min(5.0, ratio * dist))
            factor = ov.scale_x / prev_x if prev_x else 1.0
            ov.scale_y = max(0.05, min(5.0, ov.scale_y * factor))
            ov.scale = ov.scale_x
            if hasattr(self, "over_scale_var"):
                self.over_scale_var.set(f"{ov.scale:.2f}")
            if hasattr(self, "over_w_var") and hasattr(self, "over_h_var"):
                self.over_w_var.set(f"{ov.scale_x:.2f}")
                self.over_h_var.set(f"{ov.scale_y:.2f}")

    def _on_release(self, e):
        self.dragging = None
        self.resizing = False
        self.drag_off = (0, 0)
        self.canvas.config(cursor="crosshair")
        self._refresh_canvas()

    def _schedule_refresh(self, delay=16):
        """Debounce preview re-render so dragging stays smooth."""
        if getattr(self, "_refresh_job", None):
            try:
                self.after_cancel(self._refresh_job)
            except Exception:
                pass
        self._refresh_job = self.after(delay, self._refresh_canvas)


    def _arrow_size(self, delta, state=0):
        """Keyboard-arrow resizing of the selected element (Shift = big steps)."""
        if not self.selected:
            return
        kind, i = self.selected
        big = bool(state & 0x0001)
        if kind == "label" and i < len(self.labels):
            cur = self.labels[i].size
            if hasattr(self, "size_var"):
                try:
                    cur = int(self.size_var.get())
                except Exception:
                    pass
            step = 10 if big else 1
            cur = max(8, min(1000, cur + delta * step))
            self.labels[i].size = cur
            if hasattr(self, "size_var"):
                self.size_var.set(cur)
        elif kind == "overlay" and i < len(self.overlays):
            ov = self.overlays[i]
            step = 0.20 if big else 0.05
            nx = max(0.05, min(5.0, ov.scale_x + delta * step))
            ny = max(0.05, min(5.0, ov.scale_y + delta * step))
            ov.scale_x, ov.scale_y = nx, ny
            ov.scale = nx
            if hasattr(self, "over_scale_var"):
                self.over_scale_var.set(f"{nx:.2f}")
            if hasattr(self, "over_w_var") and hasattr(self, "over_h_var"):
                self.over_w_var.set(f"{nx:.2f}")
                self.over_h_var.set(f"{ny:.2f}")
        else:
            return
        self._schedule_refresh()

    def _on_right_click(self, e):
        if self.selected:
            self.apply_label_prop()

    def _sync_editor_from_selection(self):
        if self.selected and self.selected[0] == "label":
            lbl = self.labels[self.selected[1]]
            self.text_entry.delete(0, tk.END)
            self.text_entry.insert(0, lbl.text)
            self.size_var.set(lbl.size)
            self.rot_var.set(lbl.rotation)
            self.font_var.set(lbl.font_name)
            if hasattr(self, "opacity_var"):
                self.opacity_var.set(lbl.opacity)
            if hasattr(self, "arc_var"):
                self.arc_var.set(lbl.arc_angle)
            if hasattr(self, "word_spacing_var"):
                self.word_spacing_var.set(getattr(lbl, "word_spacing", 0))
        elif self.selected and self.selected[0] == "overlay":
            i = self.selected[1]
            if i < len(self.overlays):
                if hasattr(self, "over_scale_var"):
                    self.over_scale_var.set(f"{self.overlays[i].scale:.2f}")
                if hasattr(self, "over_w_var") and hasattr(self, "over_h_var"):
                    self.over_w_var.set(f"{self.overlays[i].scale_x:.2f}")
                    self.over_h_var.set(f"{self.overlays[i].scale_y:.2f}")
                if hasattr(self, "flip_h_var"):
                    self.flip_h_var.set(bool(self.overlays[i].flip_h))
                    self.flip_v_var.set(bool(self.overlays[i].flip_v))
                if hasattr(self, "over_rot_var"):
                    self.over_rot_var.set(self.overlays[i].rotation)
                if hasattr(self, "over_opacity_var"):
                    self.over_opacity_var.set(self.overlays[i].opacity)

    # -------------------------------------------------------------- SAVE
    def _render_full(self):
        """Return high-res composed PIL image (base + overlays + labels)."""
        img = self.base_pil.convert("RGB")
        self._draw_overlays_and_labels(img, 1.0)
        return img

    def save_image(self, fmt):
        if self.base_pil is None:
            return
        driver = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG"}.get(fmt.lower(), fmt.upper())
        path = filedialog.asksaveasfilename(
            title=f"Save {fmt.upper()} image", parent=self,
            defaultextension="." + fmt,
            filetypes=[(fmt.upper(), f"*.{fmt}")])
        if not path:
            return
        try:
            out = self._render_full()
            out.save(path, driver)
            messagebox.showinfo("Saved", f"Image saved:\n{path}", parent=self)
        except Exception as e:
            log_error(f"save_image {fmt}: {e}")
            messagebox.showerror("Error", f"Save failed:\n{e}", parent=self)

    def save_pdf(self):
        if self.base_pil is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save as PDF", parent=self,
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            out = self._render_full()
            save_as_pdf(out, path, fit_a4=True)
            messagebox.showinfo("Saved", f"PDF saved:\n{path}", parent=self)
        except Exception as e:
            log_error(f"save_pdf: {e}")
            messagebox.showerror("Error", f"PDF save failed:\n{e}", parent=self)

    def _save_project(self):
        """Save the entire project state (including background image) to a .qazip file."""
        if self.base_pil is None:
            messagebox.showinfo("Save", "پہلے کوئی ڈیزائن بنائیں", parent=self)
            return

        path = filedialog.asksaveasfilename(
            title="Save Project", parent=self,
            defaultextension=".qazip", filetypes=[("Qazi Project", "*.qazip")])
        if not path:
            return

        try:
            # Convert background (base_pil) to base64
            buffered_base = io.BytesIO()
            # Save as PNG to preserve all details/transparency
            self.base_pil.save(buffered_base, format="PNG")
            base_b64 = base64.b64encode(buffered_base.getvalue()).decode()

            project = {
                "version": "1.2",
                "base_image_b64": base_b64,
                "canvas_color": getattr(self, "canvas_color", (255, 255, 255)),
                "labels": [],
                "overlays": []
            }

            for lbl in self.labels:
                project["labels"].append({
                    "text": lbl.text,
                    "font_name": lbl.font_name,
                    "size": lbl.size,
                    "color": lbl.color,
                    "x": lbl.x,
                    "y": lbl.y,
                    "rotation": lbl.rotation,
                    "opacity": lbl.opacity,
                    "arc_angle": lbl.arc_angle,
                    "word_spacing": getattr(lbl, "word_spacing", 0),
                    "z": lbl.z
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
                    "crop": ov.crop
                }
                # If overlay has modified data (rembg/crop), save it too
                if ov.data:
                    buf = io.BytesIO()
                    ov.data.save(buf, format="PNG")
                    ov_data["data_b64"] = base64.b64encode(buf.getvalue()).decode()
                project["overlays"].append(ov_data)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(project, f)
            messagebox.showinfo("Saved", "پراجیکٹ کامیابی سے محفوظ ہو گیا ہے", parent=self)
        except Exception as e:
            log_error(f"save_project: {e}")
            messagebox.showerror("Error", f"پراجیکٹ محفوظ کرنے میں غلطی آئی:\n{e}", parent=self)

    def _load_project(self):
        """Load a project state from a .qazip file."""
        path = filedialog.askopenfilename(
            title="Open Project", parent=self,
            filetypes=[("Qazi Project", "*.qazip")])
        if not path:
            return

        try:
            data = open(path, "rb").read()
            for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
                try:
                    project = json.loads(data.decode(enc))
                    break
                except Exception:
                    continue
            else:
                raise ValueError("project file format not recognized")

            # Load the background image first
            if "base_image_b64" in project:
                base_data = base64.b64decode(project["base_image_b64"])
                # Use convert("RGB") for background unless we want to support transparent backgrounds
                self.base_pil = Image.open(io.BytesIO(base_data)).convert("RGB")
            else:
                cc = project.get("canvas_color", (255, 255, 255))
                self.base_pil = Image.new("RGB", (1050, 660), tuple(cc))

            # Reset current workspace state
            self.labels = []
            self.overlays = []
            self.selected = None
            self.base_tk = None
            self._z_counter = 1
            used_z = set()

            # Restore labels then overlays (overlays first keeps old stacking)
            for o_data in project.get("overlays", []):
                ov_img = None
                if "data_b64" in o_data:
                    img_data = base64.b64decode(o_data["data_b64"])
                    ov_img = Image.open(io.BytesIO(img_data)).convert("RGBA")

                ov = OverlayImage(
                    path=o_data["path"],
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
                    scale_y=o_data.get("scale_y")
                )
                z = o_data.get("z")
                if z is None or z in used_z:
                    z = self._next_z()
                else:
                    used_z.add(z)
                    self._z_counter = max(self._z_counter, z + 1)
                ov.z = z
                self.overlays.append(ov)

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
                    word_spacing=l_data.get("word_spacing", 0)
                )
                z = l_data.get("z")
                if z is None or z in used_z:
                    z = self._next_z()
                else:
                    used_z.add(z)
                    self._z_counter = max(self._z_counter, z + 1)
                lbl.z = z
                self.labels.append(lbl)

            # Important: Force a redraw
            self._refresh_canvas()
            messagebox.showinfo("Loaded", "پراجیکٹ کامیابی سے لوڈ ہو گیا ہے", parent=self)
        except Exception as e:
            log_error(f"load_project: {e}")
            messagebox.showerror("Error", f"پراجیکٹ لوڈ کرنے میں غلطی آئی:\n{e}", parent=self)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
