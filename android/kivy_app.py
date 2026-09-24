"""Qazi Urdu Poster Designer & Writer - Kivy (Android + desktop).

A thin Kivy UI over the GUI-agnostic engine in core.py. Every feature of
the desktop tkinter app is present:
  - background upload / replace / new canvas / card / colour
  - Urdu text labels with font, size, colour, rotation, opacity, arc,
    word spacing, on-screen Urdu keypad, shaped preview
  - overlay images (uniform + separate W/H size, flip, rotation,
    opacity, crop, remove background, replace)
  - layer ordering, tap-select, drag-move, corner-drag resize,
    two-finger pinch-zoom, pan
  - font download / install / uninstall / refresh
  - save PNG / JPG / PDF, save & open project (.qazip), share
"""
import io
import json
import os
import threading
import time

from PIL import Image as PILImage

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image as KwImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

import core
import urdu_text
import a_io
from urdu_keypad import UrduKeypad

GREEN = get_color_from_hex("#0b3d2e")
GREEN_D = get_color_from_hex("#166f52")
BLUE = get_color_from_hex("#2a5a9a")
GOLD = get_color_from_hex("#b8860b")
RED = get_color_from_hex("#b33b3b")
GREY = (0.5, 0.5, 0.5, 1)
WHITE = (1, 1, 1, 1)
PANEL_BG = get_color_from_hex("#f2f4f3")


def pil_to_texture(pil):
    from kivy.graphics.texture import Texture
    colors = pil.mode
    if colors == "RGB":
        colors = "rgb"
    elif colors not in ("rgba", "rgb"):
        pil = pil.convert("RGBA")
        colors = "rgba"
    tex = Texture.create(size=pil.size, colorfmt=colors)
    tex.blit_buffer(pil.tobytes(), colorfmt=colors, bufferfmt="ubyte")
    tex.flip_vertical()
    return tex


def open_pil(data_bytes):
    return PILImage.open(io.BytesIO(data_bytes))


def now_stamp():
    return time.strftime("%Y%m%d_%H%M%S")


# ------------------------------------------------------------------ bits
def hbox(spacing=dp(6)):
    b = BoxLayout(orientation="horizontal", spacing=spacing)
    return b


def vbox(spacing=dp(6)):
    b = BoxLayout(orientation="vertical", spacing=spacing)
    return b


def make_btn(text, cb, bg=GREEN, fg=WHITE, bold=True, height=dp(46)):
    b = Button(text=text, background_normal="", background_color=bg, color=fg,
               font_size=dp(15), size_hint_y=None, height=height)
    if bold:
        b.font_name = "Roboto-Bold"
    b.bind(on_release=lambda *_: cb())
    return b


def make_lbl(text, size=13, bold=False, color=(0.12, 0.24, 0.2, 1), halign="left"):
    l = Label(text=text, font_size=dp(size), color=color, halign=halign,
              valign="middle", size_hint_y=None, height=dp(24))
    if halign in ("left", "right"):
        l.bind(size=lambda s, *_: setattr(s, "text_size", (s.width, None)))
    return l


def make_slider(minv, maxv, default, step=1):
    s = Slider(min=minv, max=maxv, value=default, step=step)
    return s


# ------------------------------------------------------------------ popup


# ------------------------------------------------------------------ popup
class PromptPopup(Popup):
    """A popup with title + message + optional text field."""

    def __init__(self, title, message="", label="Value:", default="", **kw):
        super().__init__(title=title, auto_dismiss=False, **kw)
        self.result = None
        box = vbox()
        box.add_widget(make_lbl(message, size=14))
        row = hbox()
        row.add_widget(make_lbl(label, size=14))
        self.field = TextInput(text=str(default), multiline=False, font_size=dp(16))
        row.add_widget(self.field)
        box.add_widget(row)
        btns = hbox()
        ok = make_btn("OK", self._ok, GREEN)
        cc = make_btn("Cancel", self._cancel, (0.5, 0.5, 0.5, 1), bold=False)
        btns.add_widget(ok)
        btns.add_widget(cc)
        box.add_widget(btns)
        self.content = box

    def _ok(self):
        self.result = self.field.text
        self.dismiss()

    def _cancel(self):
        self.dismiss()


class FilePickerPopup(Popup):
    """Choose an existing file (desktop / test fallback)."""

    def __init__(self, on_done, title="Select file", filters=None, path=None):
        super().__init__(title=title, size_hint=(0.94, 0.9), auto_dismiss=False)
        self.on_done = on_done
        box = vbox()
        if not path:
            path = os.getcwd()
        self.fc = FileChooserListView(path=path, filters=filters or [], dirselect=False)
        self.fc.bind(on_submit=lambda *a: self._pick(self.fc.selection))
        box.add_widget(self.fc)
        btns = hbox()
        btns.add_widget(make_btn("Cancel", self.dismiss, (0.5, 0.5, 0.5, 1), bold=False))
        btns.add_widget(make_btn("Open", self._pick_sel, GREEN))
        box.add_widget(btns)
        self.content = box

    def _pick_sel(self):
        self._pick(self.fc.selection)

    def _pick(self, selection):
        if selection:
            self.on_done(selection[0])
            self.dismiss()


class SavePopup(Popup):
    """Choose a folder + filename (desktop / test fallback)."""

    def __init__(self, on_done, title="Save", default_name="poster.png", path=None):
        super().__init__(title=title, size_hint=(0.94, 0.9), auto_dismiss=False)
        self.on_done = on_done
        box = vbox()
        row = hbox()
        row.add_widget(make_lbl("Name:", size=14))
        self.name = TextInput(text=default_name, multiline=False, font_size=dp(15))
        row.add_widget(self.name)
        box.add_widget(row)
        self.fc = FileChooserListView(path=path or os.getcwd(), dirselect=True)
        box.add_widget(self.fc)
        btns = hbox()
        btns.add_widget(make_btn("Cancel", self.dismiss, (0.5, 0.5, 0.5, 1), bold=False))
        btns.add_widget(make_btn("Save", self._save, GREEN))
        box.add_widget(btns)
        self.content = box

    def _save(self):
        try:
            pre = self.fc.path
            final = os.path.join(pre, self.name.text.strip())
        except Exception:
            final = os.path.join(os.getcwd(), "poster.png")
        self.on_done(final)
        self.dismiss()


class SavedPopup(Popup):
    """Shows export result with share / save-elsewhere actions."""

    def __init__(self, title, message, share_path=None, share_mime=None,
                 on_elsewhere=None):
        super().__init__(title=title, size_hint=(0.9, None), height=dp(260),
                         auto_dismiss=True)
        box = vbox()
        box.add_widget(make_lbl(message, size=14))
        btns = hbox()
        if share_path and a_io.IS_ANDROID:
            b = make_btn("Share", lambda: a_io.share_file(share_path, share_mime or "image/png"), BLUE)
            btns.add_widget(b)
        if on_elsewhere:
            btns.add_widget(make_btn("Save elsewhere...", on_elsewhere, GOLD))
        btns.add_widget(make_btn("Close", self.dismiss, (0.5, 0.5, 0.5, 1), bold=False))
        box.add_widget(btns)
        self.content = box


# ------------------------------------------------------------- crop popup
class CropWidget(Widget):
    def __init__(self, app, ov, **kw):
        super().__init__(**kw)
        self.app = app
        self.ov_img = ov.open()
        self.box = [0, 0, 0, 0]   # l,t,r,b in source px (empty = full)
        self.start = None
        self.rect = (0, 0, 0, 0)
        self.bind(pos=self._redraw, size=self._redraw)
        self._tex = None
        try:
            w0, h0 = self.ov_img.size
            s = min(1.0, 700.0 / w0, 500.0 / h0)
            self._tex = pil_to_texture(self.ov_img.resize(
                (max(1, int(w0 * s)), max(1, int(h0 * s))), PILImage.LANCZOS))
            self._img_size = (int(w0 * s), int(h0 * s))
        except Exception:
            self._img_size = (1, 1)

    def _redraw(self, *a):
        self.canvas.clear()
        with self.canvas:
            Color(0.25, 0.25, 0.25, 1)
            Rectangle(size=self.size)
            if self._tex:
                w, h = self.size
                iw, ih = self._img_size
                s = min(w / iw, h / ih)
                dw, dh = iw * s, ih * s
                x0 = (w - dw) / 2
                y0 = (h - dh) / 2
                self._disp = (x0, y0, dw, dh)
                Color(1, 1, 1, 1)
                Rectangle(texture=self._tex, pos=(x0, y0), size=(dw, dh))
            Color(1, 0.18, 0.33, 1)
            Line(rectangle=self.rect, width=2)
        if getattr(self, "_disp", None) and self.rect[2] > 0:
            self.app._crop_status.text = self._status()

    def _status(self):
        l, t, r, b = self.rect
        return "box %dx%d" % (max(0, int(r - l)), max(0, int(b - t)))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self.start = touch.pos
            return True
        return False

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False
        x0, y0 = self.start
        x1, y1 = touch.pos
        self.rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self._redraw()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self._redraw()
        return True

    def apply(self):
        if not getattr(self, "_disp", None):
            return False, (0, 0, self.ov_img.width, self.ov_img.height)
        x0, y0, dw, dh = self._disp
        l, t, r, b = self.rect
        if r - l < 6 or b - t < 6:
            return False, (0, 0, self.ov_img.width, self.ov_img.height)
        sx = self.ov_img.width / dw
        sy = self.ov_img.height / dh
        return True, (int((l - x0) * sx), int((t - y0) * sy),
                      int((r - x0) * sx), int((b - y0) * sy))


class CropPopup(Popup):
    def __init__(self, app, ov):
        super().__init__(title="Crop - drag to draw a box",
                         size_hint=(0.94, 0.9), auto_dismiss=False)
        self.app = app
        self.ov = ov
        box = vbox()
        self.cw = CropWidget(app, ov)
        box.add_widget(self.cw)
        self._crop_status = make_lbl("", size=13)
        box.add_widget(self._crop_status)
        btns = hbox()
        btns.add_widget(make_btn("Apply crop", self._apply, GREEN))
        btns.add_widget(make_btn("Reset", self._reset, GOLD))
        btns.add_widget(make_btn("Cancel", self.dismiss, (0.5, 0.5, 0.5, 1), bold=False))
        box.add_widget(btns)
        self.content = box

    def _apply(self):
        ok, crop = self.cw.apply()
        if ok:
            self.ov.crop = crop
            self.app.rerender_poster()
            self.dismiss()

    def _reset(self):
        self.ov.crop = None
        self.ov.data = None
        self.app.rerender_poster()
        self.dismiss()


# ------------------------------------------------------------ color picker
class ColorPopup(Popup):
    def __init__(self, current=(0, 0, 0), title="Colour", on_ok=None):
        super().__init__(title=title, size_hint=(0.92, None), height=dp(360),
                         auto_dismiss=False)
        self.on_ok = on_ok
        box = vbox()
        self.rs = make_slider(0, 255, current[0], 1)
        self.gs = make_slider(0, 255, current[1], 1)
        self.bs = make_slider(0, 255, current[2], 1)
        self.preview = Widget(size_hint_y=None, height=dp(44))
        box.add_widget(self.preview)
        for lbl, sl in (("R", self.rs), ("G", self.gs), ("B", self.bs)):
            r = hbox()
            r.add_widget(make_lbl(lbl, size=14, bold=True))
            sl.bind(value=lambda *_: self._refresh())
            r.add_widget(sl)
            box.add_widget(r)
        btns = hbox()
        btns.add_widget(make_btn("Cancel", self.dismiss, (0.5, 0.5, 0.5, 1), bold=False))
        btns.add_widget(make_btn("OK", self._picked, GREEN))
        box.add_widget(btns)
        self.content = box
        self._refresh()

    def value(self):
        return (int(self.rs.value), int(self.gs.value), int(self.bs.value))

    def _refresh(self):
        r, g, b = self.value()
        self.preview.canvas.clear()
        with self.preview.canvas:
            Color(r / 255, g / 255, b / 255, 1)
            Rectangle(size=self.preview.size)

    def _picked(self):
        if self.on_ok:
            self.on_ok(self.value())
        self.dismiss()


# -------------------------------------------------------------- keypad
class KeypadPopup(Popup):
    def __init__(self, app, **kw):
        super().__init__(title="", size_hint=(0.96, 0.9), auto_dismiss=False)
        self.app = app
        self.content = UrduKeypad(app.text_entry,
                                  on_apply=app.apply_urdu_text,
                                  on_change=app.update_urdu_preview)
        self.title = "\u0627\u0631\u062f\u0648 \u06a9\u06cc \u0628\u0648\u0631\u0688"


# ---------------------------------------------------------------- preview
class PreviewPane(Widget):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.touches = {}
        self.mode = None
        self.drag_off = (0, 0)
        self.rect = (0, 0, 0, 0)
        self.px_per_img = 1.0
        self._sched = False
        self._gesture = None
        self.pos_hint_render = True
        self.bind(pos=self._geom, size=self._geom)

    def _geom(self, *a):
        self.schedule_render()

    # ------------------------------------------------------- mapping
    def to_img(self, wx, wy):
        rx, ry, rw, rh = self.rect
        p = self.app.poster
        rw = max(rw, 1)
        rh = max(rh, 1)
        return ((wx - rx) / rw * p.width, (wy - ry) / rh * p.height)

    def schedule_render(self, ts=0.03):
        if self._sched:
            return
        self._sched = True
        Clock.schedule_once(lambda *_: self._render(), ts)

    def rerender(self):
        self._render()

    def _render(self):
        self._sched = False
        p = self.app.poster
        w = self.width
        h = self.height
        if w < 8 or h < 8 or p is None or p.width < 4 or p.height < 4:
            return
        fit = min(w / p.width, h / p.height)
        disp_w = p.width * fit * self.zoom
        disp_h = p.height * fit * self.zoom
        rx = (w - disp_w) / 2 + self.pan[0]
        ry = (h - disp_h) / 2 + self.pan[1]
        self.rect = (rx, ry, disp_w, disp_h)
        self.px_per_img = disp_w / p.width
        dw = int(abs(disp_w))
        dh = int(abs(disp_h))
        m = max(dw, dh, 1)
        if m > 1300:
            s = 1300.0 / m
            dw = int(dw * s)
            dh = int(dh * s)
        try:
            prev = p.render_preview(dw, dh)
        except Exception:
            prev = None
        self.canvas.clear()
        with self.canvas:
            Color(0.3, 0.3, 0.3, 1)
            Rectangle(size=self.size)
            if prev is not None:
                tex = pil_to_texture(prev)
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(rx, ry), size=(disp_w, disp_h))
            self._draw_selection()

    def _draw_selection(self):
        p = self.app.poster
        sel = p.selected
        if not sel:
            return
        box = p.element_box(*sel)
        if not box:
            return
        cx, cy, hw, hh = box
        rx, ry, rw, rh = self.rect
        rw = max(rw, 1)
        rh = max(rh, 1)
        sx = lambda v: rx + (v / p.width) * rw
        sy = lambda v: ry + (v / p.height) * rh
        x0, y0 = sx(cx - hw), sy(cy - hh)
        x1, y1 = sx(cx + hw), sy(cy + hh)
        with self.canvas:
            Color(0.75, 0.85, 0.9, 1)
            Line(rectangle=(x0, y0, x1 - x0, y1 - y0), width=1.5)
            Color(1, 1, 1, 1)
            s = 7
            for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                Rectangle(pos=(px - s, py - s), size=(2 * s, 2 * s))

    # ------------------------------------------------------- gestures
    def on_touch_down(self, touch):
        if not self.collide_point(touch.x, touch.y):
            return False
        touch.grab(self)
        self.touches[touch.id] = touch.pos
        if len(self.touches) == 2:
            self.mode = "zoom"
            self._gesture = self._capture_gesture()
            return True
        self._begin_select(touch)
        return True

    def _capture_gesture(self):
        p = self.app.poster
        pts = list(self.touches.values())
        midx = sum(t[0] for t in pts) / len(pts)
        midy = sum(t[1] for t in pts) / len(pts)
        a, b = pts[0], pts[1]
        dist = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        return {"mid": (midx, midy),
                "img": self.to_img(midx, midy),
                "zoom": self.zoom,
                "dist": max(dist, 1.0)}

    def _begin_select(self, touch):
        p = self.app.poster
        img = self.to_img(touch.x, touch.y)
        thr_img = 26.0 / max(self.px_per_img, 1e-6)
        corner = p.corner_at(img[0], img[1], threshold_px=thr_img)
        if corner:
            p.selected = corner
            self.mode = "resize"
        else:
            hit = p.hit_test(img[0], img[1])
            if hit:
                p.selected = hit
                kind, i = hit
                el = p._get_element(kind, i)
                if el is not None:
                    self.drag_off = (el.x * p.width - img[0],
                                     el.y * p.height - img[1])
                self.mode = "drag"
            else:
                p.selected = None
                self.mode = None
        self.app.sync_editor()
        self.schedule_render(0)

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False
        self.touches[touch.id] = touch.pos
        if self.mode == "zoom" and len(self.touches) >= 2:
            self._zoom_update()
            return True
        if self.mode in ("drag", "resize") and len(self.touches) == 1:
            img = self.to_img(touch.x, touch.y)
            p = self.app.poster
            if self.mode == "resize" and p.selected:
                p.do_resize(p.selected[0], p.selected[1], img[0], img[1])
            else:
                p.move_selected_to(img[0], img[1], offset=self.drag_off)
            self.schedule_render()
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self.touches.pop(touch.id, None)
        if len(self.touches) == 0:
            self.mode = None
            self.app.sync_props()
        elif len(self.touches) == 1:
            self.mode = "drag"
            self._gesture = None
            t = list(self.touches.values())[0]
            self._begin_drag_only(t)
        self.schedule_render(0)
        return True

    def _begin_drag_only(self, pos):
        p = self.app.poster
        img = self.to_img(pos[0], pos[1])
        hit = p.hit_test(img[0], img[1])
        if hit and p.selected:
            kind, i = hit
            if kind == p.selected[0] and i == p.selected[1]:
                el = p._get_element(kind, i)
                if el is not None:
                    self.drag_off = (el.x * p.width - img[0],
                                     el.y * p.height - img[1])
                    self.mode = "drag"

    def _zoom_update(self):
        pts = list(self.touches.values())
        a, b = pts[0], pts[1]
        dist = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        g = self._gesture
        if g is None:
            return
        z = g["zoom"] * (dist / g["dist"])
        self.zoom = min(6.0, max(0.2, z))
        p = self.app.poster
        fit = min(self.width / p.width, self.height / p.height)
        disp_w = p.width * fit * self.zoom
        disp_h = p.height * fit * self.zoom
        ix, iy = g["img"]
        rx = mid[0] - (ix / p.width) * disp_w
        ry = mid[1] - (iy / p.height) * disp_h
        self.pan = [rx - (self.width - disp_w) / 2,
                    ry - (self.height - disp_h) / 2]
        self.schedule_render()


# ------------------------------------------------------------ scroll tab
def scroll_tab():
    sv = ScrollView()
    inner = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(8),
                      spacing=dp(6))
    inner.bind(minimum_height=inner.setter("height"))
    sv.add_widget(inner)
    return sv, inner


def section(inner, text):
    inner.add_widget(make_lbl(text, size=14, bold=True, color=GREEN))


# ================================================================== app
class QaziPosterApp(App):
    title = "Qazi Urdu Poster Designer & Writer"
    icon = "icon.png"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.poster = core.Poster(1600, 2200, fill=(255, 255, 255))
        self.panel_visible = True
        self._winsize = (0, 0)

    def build(self):
        self._label_refs = {}
        root = BoxLayout(orientation="vertical")
        root.add_widget(self._build_header())
        self.main_box = BoxLayout(spacing=dp(2))
        root.add_widget(self.main_box)
        self.hint_lbl = make_lbl(
            "drag = move   |   corner = resize   |   two fingers = zoom/pan",
            size=11, color=(0.4, 0.4, 0.4, 1), halign="center")
        self.hint_lbl.size_hint_y = None
        self.hint_lbl.height = dp(18)
        root.add_widget(self.hint_lbl)
        self.toast_lbl = make_lbl("", size=12, color=GREEN, halign="center")
        self.toast_lbl.size_hint_y = None
        self.toast_lbl.height = dp(20)
        root.add_widget(self.toast_lbl)

        self.preview = PreviewPane(self)
        self.panel = self._build_panel()
        self.main_box.add_widget(self.preview)
        self.main_box.add_widget(self.panel)
        self._relayout(None)
        Window.bind(on_resize=self._relayout)
        self.rerender_poster()
        return root

    # ----------------------------------------------------------- header
    def _build_header(self):
        hd = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52),
                       padding=dp(8), spacing=dp(6))
        hd.canvas.clear()
        from kivy.graphics import Color as _C, Rectangle as _R
        with hd.canvas:
            _C(0.043, 0.24, 0.18, 1)
            _R(size=hd.size)
        hd.bind(pos=lambda s, *_: setattr(s.canvas.children[1], "pos", s.pos))
        hd.bind(size=lambda s, *_: setattr(s.canvas.children[1], "size", s.size))
        t = make_lbl("Qazi Urdu Poster Designer", size=16, bold=True,
                     color=WHITE)
        hd.add_widget(t)
        b = make_btn("Panel", self._toggle_panel, GREEN_D, bold=False,
                     height=dp(40))
        b.size_hint_x = None
        b.width = dp(80)
        hd.add_widget(b)
        zr = make_btn("Zoom-fit", self._zoom_fit, GREEN_D, bold=False,
                      height=dp(40))
        zr.size_hint_x = None
        zr.width = dp(88)
        hd.add_widget(zr)
        return hd

    def _toggle_panel(self):
        self.panel_visible = not self.panel_visible
        self._relayout(None)

    def _zoom_fit(self):
        self.preview.zoom = 1.0
        self.preview.pan = [0.0, 0.0]
        self.preview.rerender()
        try:
            self.zoom_sl.value = 1.0
        except Exception:
            pass

    def _relayout(self, win, w=None, h=None):
        win_w = Window.width
        win_h = Window.height
        if w is not None:
            win_w, win_h = w, h
        self.main_box.clear_widgets()
        if win_w >= win_h * 1.05 and self.panel_visible:
            self.main_box.orientation = "horizontal"
            self.preview.size_hint = (1, 1)
            self.panel.size_hint = (None, 1)
            self.panel.width = min(dp(360), win_w * 0.44)
        else:
            self.main_box.orientation = "vertical"
            if self.panel_visible:
                self.preview.size_hint = (1, 0.55)
                self.panel.size_hint = (1, 0.45)
            else:
                self.preview.size_hint = (1, 1)
        self.main_box.add_widget(self.preview)
        if self.panel_visible:
            self.main_box.add_widget(self.panel)
        self.preview.schedule_render(0)

    # ----------------------------------------------------------- panel
    def _build_panel(self):
        tp = TabbedPanel(do_default_tab=False, tab_width=dp(86), tab_height=dp(42))
        tp.tab_pos = "top_mid"
        self.tabs = {}
        items = [("Text", self._tab_text), ("Overlay", self._tab_overlay),
                 ("Layer", self._tab_layer), ("Canvas", self._tab_canvas),
                 ("Fonts", self._tab_fonts), ("Save", self._tab_save)]
        for label, builder in items:
            item = TabbedPanelItem(text=label)
            sv, inner = scroll_tab()
            builder(inner)
            item.content = sv
            tp.add_widget(item)
            self.tabs[label] = inner
        return tp

    def _row(self, inner, widgets):
        r = hbox()
        for w in widgets:
            r.add_widget(w)
        inner.add_widget(r)
        return r

    def _quick(self, inner, label, cb):
        b = Button(text=label, size_hint=(None, None), width=dp(52), height=dp(34),
                   background_normal="", background_color=BLUE, color=WHITE,
                   font_size=dp(13))
        b.bind(on_release=lambda *_: cb())
        inner.add_widget(b)
        return b

    # ========================================================= TEXT TAB
    def _tab_text(self, inner):
        section(inner, "Text layer")
        r = hbox()
        self.text_entry = TextInput(text="\u0646\u0626\u06cc \u062a\u062d\u0631\u06cc\u0631",
                                    multiline=False, font_size=dp(17),
                                    size_hint_y=None, height=dp(44))
        self.text_entry.bind(text=lambda *_: self.update_urdu_preview())
        r.add_widget(self.text_entry)
        kb = make_btn("\u0627\u0631\u062f\u0648", self._open_keypad, GOLD, height=dp(44))
        kb.size_hint_x = None
        kb.width = dp(66)
        r.add_widget(kb)
        inner.add_widget(r)

        self.text_thumb = KwImage(size_hint_y=None, height=dp(64))
        inner.add_widget(self.text_thumb)

        row = hbox()
        row.add_widget(make_btn("Apply text", self.apply_urdu_text, GREEN))
        row.add_widget(make_btn("+ New text", self.add_text, BLUE))
        row.add_widget(make_btn("Delete", self.delete_selected, RED))
        inner.add_widget(row)

        section(inner, "Font")
        names = sorted(core.URDU_FONTS.keys())
        self.font_spin = Spinner(text=core.DEFAULT_FONT, values=names,
                                 size_hint_y=None, height=dp(40), font_size=dp(14))
        self.font_spin.bind(text=lambda *_: self.label_prop_changed())
        inner.add_widget(self.font_spin)

        section(inner, "Size")
        rr = hbox()
        self.size_sl = make_slider(8, 400, 60, 1)
        self.size_sl.bind(value=lambda *_: self.label_prop_changed())
        rr.add_widget(self.size_sl)
        self.size_val = make_lbl("60", size=13, bold=True)
        self.size_val.size_hint_x = None
        self.size_val.width = dp(40)
        rr.add_widget(self.size_val)
        inner.add_widget(rr)
        q = hbox()
        for v in (30, 60, 120, 200):
            self._quick(q, str(v), lambda v=v: self._set_sl(self.size_sl, v))
        inner.add_widget(q)

        section(inner, "Colour")
        self.color_btn = make_btn("Text colour ...", self._pick_text_color, BLUE,
                                  height=dp(40))
        inner.add_widget(self.color_btn)

        section(inner, "Rotation (deg)")
        rr = hbox()
        self.rot_sl = make_slider(-90, 90, 0, 1)
        self.rot_sl.bind(value=lambda *_: self.label_prop_changed())
        rr.add_widget(self.rot_sl)
        self.rot_val = make_lbl("0", size=13, bold=True)
        self.rot_val.size_hint_x = None
        self.rot_val.width = dp(40)
        rr.add_widget(self.rot_val)
        inner.add_widget(rr)
        q = hbox()
        for v in (0, -90, 90):
            self._quick(q, str(v), lambda v=v: self._set_sl(self.rot_sl, v))
        inner.add_widget(q)

        section(inner, "Opacity %")
        rr = hbox()
        self.op_sl = make_slider(0, 100, 100, 1)
        self.op_sl.bind(value=lambda *_: self.label_prop_changed())
        rr.add_widget(self.op_sl)
        self.op_val = make_lbl("100", size=13, bold=True)
        self.op_val.size_hint_x = None
        self.op_val.width = dp(40)
        rr.add_widget(self.op_val)
        inner.add_widget(rr)

        section(inner, "Arc (curved text)")
        rr = hbox()
        self.arc_sl = make_slider(-180, 180, 0, 5)
        self.arc_sl.bind(value=lambda *_: self.label_prop_changed())
        rr.add_widget(self.arc_sl)
        self.arc_val = make_lbl("0", size=13, bold=True)
        self.arc_val.size_hint_x = None
        self.arc_val.width = dp(40)
        rr.add_widget(self.arc_val)
        inner.add_widget(rr)
        q = hbox()
        for v in (0, -45, 90, 180):
            self._quick(q, str(v), lambda v=v: self._set_sl(self.arc_sl, v))
        inner.add_widget(q)

        section(inner, "Word spacing")
        rr = hbox()
        self.ws_sl = make_slider(-100, 400, 0, 1)
        self.ws_sl.bind(value=lambda *_: self.label_prop_changed())
        rr.add_widget(self.ws_sl)
        self.ws_val = make_lbl("0", size=13, bold=True)
        self.ws_val.size_hint_x = None
        self.ws_val.width = dp(40)
        rr.add_widget(self.ws_val)
        inner.add_widget(rr)
        q = hbox()
        for v in (-10, 0, 10, 20):
            self._quick(q, str(v), lambda v=v: self._set_sl(self.ws_sl, v))
        inner.add_widget(q)

    # ========================================================= OVERLAY
    def _tab_overlay(self, inner):
        section(inner, "Overlay image (logo / photo)")
        inner.add_widget(make_btn("Upload overlay image", self.upload_overlay, GOLD))
        inner.add_widget(make_btn("Replace overlay image", self.replace_overlay, BLUE))
        inner.add_widget(make_btn("Crop ...", self.crop_selected, GREEN_D))
        inner.add_widget(make_btn("Remove background", self.remove_bg, RED))
        inner.add_widget(make_btn("Delete selected", self.delete_selected, RED))

        section(inner, "Image size (uniform)")
        rr = hbox()
        self.ov_scale_sl = make_slider(0.1, 3.0, 1.0, 0.05)
        rr.add_widget(self.ov_scale_sl)
        self.ov_scale_val = make_lbl("1.0", size=13, bold=True)
        self.ov_scale_val.size_hint_x = None
        self.ov_scale_val.width = dp(44)
        rr.add_widget(self.ov_scale_val)
        inner.add_widget(rr)
        inner.add_widget(make_btn("Apply size", self.overlay_scale_changed, GREEN_D,
                                  bold=False, height=dp(38)))

        section(inner, "Separate width / height")
        rr = hbox()
        rr.add_widget(make_lbl("W", size=13, bold=True))
        self.ov_w_sl = make_slider(0.1, 3.0, 1.0, 0.05)
        rr.add_widget(self.ov_w_sl)
        inner.add_widget(rr)
        rr = hbox()
        rr.add_widget(make_lbl("H", size=13, bold=True))
        self.ov_h_sl = make_slider(0.1, 3.0, 1.0, 0.05)
        rr.add_widget(self.ov_h_sl)
        inner.add_widget(rr)
        inner.add_widget(make_btn("Apply W/H", self.overlay_size_changed, GREEN_D,
                                  bold=False, height=dp(38)))

        section(inner, "Flip")
        rr = hbox()
        self.flip_h = CheckBox(active=False, color=GREEN)
        rr.add_widget(make_lbl("Horizontal", size=13))
        rr.add_widget(self.flip_h)
        self.flip_v = CheckBox(active=False, color=GREEN)
        rr.add_widget(make_lbl("Vertical", size=13))
        rr.add_widget(self.flip_v)
        self.flip_h.bind(active=lambda *_: self.overlay_flip_changed())
        self.flip_v.bind(active=lambda *_: self.overlay_flip_changed())
        inner.add_widget(rr)

        section(inner, "Rotation (deg)")
        rr = hbox()
        self.ov_rot_sl = make_slider(-180, 180, 0, 1)
        self.ov_rot_sl.bind(value=lambda *_: self.overlay_rot_changed())
        rr.add_widget(self.ov_rot_sl)
        self.ov_rot_val = make_lbl("0", size=13, bold=True)
        self.ov_rot_val.size_hint_x = None
        self.ov_rot_val.width = dp(40)
        rr.add_widget(self.ov_rot_val)
        inner.add_widget(rr)
        q = hbox()
        for v in (0, -90, 90, 180):
            self._quick(q, str(v), lambda v=v: self._set_sl(self.ov_rot_sl, v))
        inner.add_widget(q)

        section(inner, "Opacity %")
        rr = hbox()
        self.ov_op_sl = make_slider(0, 100, 100, 1)
        self.ov_op_sl.bind(value=lambda *_: self.overlay_opacity_changed())
        rr.add_widget(self.ov_op_sl)
        self.ov_op_val = make_lbl("100", size=13, bold=True)
        self.ov_op_val.size_hint_x = None
        self.ov_op_val.width = dp(40)
        rr.add_widget(self.ov_op_val)
        inner.add_widget(rr)

    # ========================================================== LAYER
    def _tab_layer(self, inner):
        section(inner, "Layer order (selected element)")
        inner.add_widget(make_btn("To front", lambda: self.layer_cmd("front"), GREEN))
        inner.add_widget(make_btn("Forward", lambda: self.layer_cmd("forward"), GREEN_D))
        inner.add_widget(make_btn("Backward", lambda: self.layer_cmd("backward"), GREEN_D))
        inner.add_widget(make_btn("To back", lambda: self.layer_cmd("back"), GREEN))
        inner.add_widget(make_lbl("Text and images stack; the highest layer shows on top.",
                                  size=12, color=(0.4, 0.4, 0.4, 1)))

    # ======================================================== CANVAS
    def _tab_canvas(self, inner):
        section(inner, "Project / background")
        inner.add_widget(make_btn("Upload background (new)", self.upload_background, GREEN))
        inner.add_widget(make_btn("Replace background (keep design)", self.replace_background, GREEN_D))
        inner.add_widget(make_btn("New blank canvas ...", self.new_canvas_prompt, BLUE))
        inner.add_widget(make_btn("New blank card", self.new_blank_card, BLUE))
        inner.add_widget(make_btn("Canvas colour ...", self.pick_canvas_color, GOLD))

    # ========================================================== FONTS
    def _tab_fonts(self, inner):
        section(inner, "Font management")
        self.font_download_btn = make_btn("Download Urdu fonts", self.font_downloader, BLUE)
        inner.add_widget(self.font_download_btn)
        inner.add_widget(make_btn("Install font file from device", self.install_font_from_file, GREEN))
        self.font_uninstall_btn = make_btn("Remove a user font", self.font_uninstaller, RED)
        inner.add_widget(self.font_uninstall_btn)
        inner.add_widget(make_btn("Refresh font list", self.refresh_fonts, GREY, bold=False))
        inner.add_widget(make_lbl("Bundled fonts (Jameel Noori Nastaleeq, Amiri, "
                                  "Noto Naskh, Aligarh ...) are permanent.", size=12,
                                  color=(0.45, 0.45, 0.45, 1)))
        self.font_status = make_lbl("", size=12, color=GREEN)
        inner.add_widget(self.font_status)

    # ============================================================ SAVE
    def _tab_save(self, inner):
        section(inner, "Save your design")
        inner.add_widget(make_btn("Save PNG", lambda: self.save_image("png"), GREEN))
        inner.add_widget(make_btn("Save JPG", lambda: self.save_image("jpg"), GREEN_D))
        inner.add_widget(make_btn("Save PDF", self.save_pdf, RED))
        rr = hbox()
        rr.add_widget(make_btn("Save project", self.save_project, BLUE))
        rr.add_widget(make_btn("Open project", self.open_project, BLUE))
        inner.add_widget(rr)
        inner.add_widget(make_lbl(".qazip project keeps background + layers."
                                 " PDF is fitted to A4 (150 DPI).", size=12,
                                 color=(0.4, 0.4, 0.4, 1)))
        self.save_status = make_lbl("", size=12, color=GREEN)
        inner.add_widget(self.save_status)

    # ------------------------------------------------------------ toast
    def notify(self, msg, color=GREEN):
        self.toast_lbl.text = msg
        self.toast_lbl.color = color
        Clock.schedule_once(lambda *_: self._clear_toast(), 4)

    def _clear_toast(self):
        if self.toast_lbl.text:
            self.toast_lbl.text = ""

    # ---------------------------------------------------- text actions
    def _open_keypad(self):
        KeypadPopup(self).open()

    def selected_label(self):
        p = self.poster
        if p.selected and p.selected[0] == "label":
            i = p.selected[1]
            if 0 <= i < len(p.labels):
                return p.labels[i], i
        return None, -1

    def apply_urdu_text(self):
        p = self.poster
        txt = self.text_entry.text
        lbl, i = self.selected_label()
        if lbl is not None:
            lbl.text = urdu_text.normalize(txt)
            lbl.font_name = self.font_spin.text if self.font_spin.text in core.URDU_FONTS \
                else lbl.font_name
            lbl.size = int(self.size_sl.value)
            lbl.word_spacing = int(self.ws_sl.value)
        elif txt is not None and not p.selected:
            self.add_text()
        self.rerender_poster()
        self.update_urdu_preview()

    def add_text(self):
        p = self.poster
        txt = self.text_entry.text or "\u0646\u0626\u06cc \u062a\u062d\u0631\u06cc\u0631"
        p.add_label(text=txt,
                    size=int(self.size_sl.value),
                    font_name=self.font_spin.text if self.font_spin.text in core.URDU_FONTS else None,
                    opacity=int(self.op_sl.value),
                    arc_angle=int(self.arc_sl.value),
                    word_spacing=int(self.ws_sl.value))
        self.sync_editor()
        self.rerender_poster()
        self.update_urdu_preview()

    def label_prop_changed(self):
        p = self.poster
        lbl, i = self.selected_label()
        if lbl is None:
            return
        lbl.size = int(self.size_sl.value)
        lbl.rotation = int(self.rot_sl.value)
        lbl.opacity = int(self.op_sl.value)
        lbl.arc_angle = int(self.arc_sl.value)
        lbl.word_spacing = int(self.ws_sl.value)
        fn = self.font_spin.text
        if fn in core.URDU_FONTS:
            lbl.font_name = fn
        self.size_val.text = str(lbl.size)
        self.rot_val.text = str(lbl.rotation)
        self.op_val.text = str(lbl.opacity)
        self.arc_val.text = str(lbl.arc_angle)
        self.ws_val.text = str(lbl.word_spacing)
        self.color_btn.text = "Text colour ..."
        self.rerender_poster()
        self.update_urdu_preview()

    def _set_sl(self, sl, v):
        sl.value = v

    def _pick_text_color(self):
        lbl, i = self.selected_label()
        cur = lbl.color if lbl is not None else (0, 0, 0)
        def ok(c):
            if lbl is not None:
                lbl.color = c
                self.rerender_poster()
            else:
                self.notify("Select a text label first")
        ColorPopup(current=cur, on_ok=ok).open()

    def update_urdu_preview(self):
        try:
            txt = self.text_entry.text
            if not txt:
                return
            font_name = self.font_spin.text if hasattr(self, "font_spin") and \
                self.font_spin.text in core.URDU_FONTS else core.DEFAULT_FONT
            size = int(self.size_sl.value) if hasattr(self, "size_sl") else 40
            tmp = core.Poster(400, 80, fill=(255, 255, 255))
            tmp.add_label(text=txt, x=0.5, y=0.5, size=max(int(size * 0.6), 20),
                          font_name=font_name)
            img = tmp.render_preview(380, 64)
            self.text_thumb.texture = pil_to_texture(img)
            self.text_thumb.size_hint_y = None
            self.text_thumb.height = dp(64)
        except Exception:
            pass

    # --------------------------------------------------- overlay actions
    def selected_overlay(self):
        p = self.poster
        ov, i = p._selected_overlay()
        return ov, i

    def upload_overlay(self):
        self._pick_image(self._overlay_picked)

    def _overlay_picked(self, pil_img, _name):
        p = self.poster
        p.add_overlay(base_image=pil_img.convert("RGBA"))
        self.sync_editor()
        self.rerender_poster()
        self.notify("Overlay added")

    def replace_overlay(self):
        ov, i = self.selected_overlay()
        if ov is None:
            self.notify("Select an overlay image first", RED)
            return
        self._pick_image(self._overlay_replaced)

    def _overlay_replaced(self, pil_img, _name):
        p = self.poster
        if p.replace_selected_overlay_image(base_image=pil_img.convert("RGBA")):
            self.rerender_poster()
            self.notify("Overlay replaced")

    def crop_selected(self):
        ov, i = self.selected_overlay()
        if ov is None:
            self.notify("Select an overlay image first", RED)
            return
        CropPopup(self, ov).open()

    def remove_bg(self):
        ov, i = self.selected_overlay()
        if ov is None:
            self.notify("Select an overlay image first", RED)
            return
        try:
            import rembg
        except Exception:
            rembg = None
        self.notify("Removing background ...")
        def worker():
            try:
                src = ov.open()
                if rembg is not None:
                    if not getattr(self, "_rembg_session", None):
                        self._rembg_session = rembg.new_session("u2netp")
                    res = rembg.remove(src, session=self._rembg_session)
                else:
                    res = core.strip_background_edges(src)
                ov.data = res.convert("RGBA")
                ov.crop = None
                Clock.schedule_once(lambda *_: (self.rerender_poster(),
                                                self.notify("Background removed")))
            except Exception as e:
                core.log_error(f"remove_bg: {e}")
                Clock.schedule_once(lambda *_: self.notify(
                    "Background removal failed", RED))
        threading.Thread(target=worker, daemon=True).start()

    def overlay_scale_changed(self, *a):
        ov, i = self.selected_overlay()
        if ov is None:
            return
        v = float(self.ov_scale_sl.value)
        ov.scale = v
        ov.scale_x = v
        ov.scale_y = v
        try:
            self.ov_w_sl.value = v
            self.ov_h_sl.value = v
        except Exception:
            pass
        self.ov_scale_val.text = "%.2f" % v
        self.rerender_poster()

    def overlay_size_changed(self):
        ov, i = self.selected_overlay()
        if ov is None:
            return
        ov.scale_x = float(self.ov_w_sl.value)
        ov.scale_y = float(self.ov_h_sl.value)
        self.rerender_poster()

    def overlay_flip_changed(self):
        ov, i = self.selected_overlay()
        if ov is None:
            return
        ov.flip_h = bool(self.flip_h.active)
        ov.flip_v = bool(self.flip_v.active)
        self.rerender_poster()

    def overlay_rot_changed(self):
        ov, i = self.selected_overlay()
        if ov is None:
            return
        ov.rotation = int(self.ov_rot_sl.value)
        self.ov_rot_val.text = str(ov.rotation)
        self.rerender_poster()

    def overlay_opacity_changed(self):
        ov, i = self.selected_overlay()
        if ov is None:
            return
        ov.opacity = int(self.ov_op_sl.value)
        self.ov_op_val.text = str(ov.opacity)
        self.rerender_poster()

    # ----------------------------------------------------------- layer
    def layer_cmd(self, mode):
        self.poster.layer_move(mode)
        self.rerender_poster()

    # ---------------------------------------------------------- canvas
    def upload_background(self):
        self._pick_image(self._bg_picked)

    def _bg_picked(self, pil_img, _name):
        p = self.poster
        p.set_background_pil(pil_img)
        self.sync_editor()
        self.rerender_poster()
        self.notify("Background set (new project)")

    def replace_background(self):
        self._pick_image(self._bg_replaced)

    def _bg_replaced(self, pil_img, _name):
        self.poster.replace_background_pil(pil_img)
        self.rerender_poster()
        self.notify("Background replaced - design kept")

    def new_canvas_prompt(self):
        ppp = PromptPopup("New canvas", "Enter pixel size for the blank canvas.",
                          default="1600 x 2200")
        ppp.size_hint = (0.9, None)
        ppp.height = dp(220)
        ppp.open()
        def check():
            if ppp.result:
                try:
                    parts = ppp.result.lower().replace(",", " ").split()
                    wh = [x for x in parts if x.strip()]
                    w = int(wh[0])
                    h = int(wh[1]) if len(wh) > 1 else int(float(wh[0]) * 1.375)
                    self.poster.new_canvas(w, h)
                    self.sync_editor()
                    self.rerender_poster()
                except Exception:
                    self.notify("Format: width x height e.g. 1600 x 2200", RED)
            else:
                Clock.schedule_once(lambda *_: check(), 0.3)
        Clock.schedule_once(lambda *_: check(), 0.4)

    def new_blank_card(self):
        self.poster.new_canvas(1050, 660, fill=(235, 240, 244))
        self.sync_editor()
        self.rerender_poster()

    def pick_canvas_color(self):
        def ok(c):
            if self.poster.base_pil is None:
                self.notify("No canvas yet", RED)
                return
            self.poster.recolor_background(c)
            self.poster.canvas_color = tuple(c)
            self.rerender_poster()
        ColorPopup(current=(255, 255, 255), title="Canvas colour", on_ok=ok).open()

    # ------------------------------------------------------------ fonts
    def refresh_fonts(self):
        core.refresh_font_list()
        names = sorted(core.URDU_FONTS.keys())
        if hasattr(self, "font_spin"):
            self.font_spin.values = names
        self.notify("Font list refreshed (%d)" % len(names))

    def font_downloader(self):
        pop = Popup(title="Download Urdu fonts", size_hint=(0.94, 0.85),
                    auto_dismiss=False)
        box = vbox()
        box.add_widget(make_lbl("Select one or more free Urdu/Arabic fonts:",
                                size=14, bold=True))
        names = [f["name"] for f in core.ONLINE_FONTS]
        sel = [False] * len(names)
        items = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(4))
        items.bind(minimum_height=items.setter("height"))
        for idx, name in enumerate(names):
            def mk(idx, name):
                cb = CheckBox(active=False, color=GREEN)
                cb.size_hint_x = None
                cb.width = dp(40)
                cb.bind(active=lambda ch, i=idx: sel.__setitem__(i, ch.active))
                row = hbox(spacing=dp(2))
                row.add_widget(cb)
                row.add_widget(make_lbl(name, size=14))
                row.size_hint_y = None
                row.height = dp(42)
                return row
            items.add_widget(mk(idx, name))
        sv = ScrollView()
        sv.add_widget(items)
        box.add_widget(sv)
        status = make_lbl("", size=12, color=GREEN)
        box.add_widget(status)

        def start_dl():
            chosen = [names[i] for i in range(len(names)) if sel[i]]
            if not chosen:
                status.text = "Select at least one font"
                return
            status.text = "Downloading ..."
            def worker():
                ok_list, bad_list = self._download_worker(chosen)
                def done(_):
                    status.text = "Installed: %s" % (", ".join(ok_list) if ok_list else "nothing")
                    if bad_list:
                        status.text += "\nRejected: %s" % ", ".join(bad_list[:3])
                    self.refresh_fonts()
                Clock.schedule_once(done, 0.1)
            threading.Thread(target=worker, daemon=True).start()

        btns = hbox()
        btns.add_widget(make_btn("Download & install", start_dl, GREEN))
        btns.add_widget(make_btn("Close", pop.dismiss, (0.5, 0.5, 0.5, 1), bold=False))
        box.add_widget(btns)
        pop.content = box
        pop.open()

    @staticmethod
    def _download_worker(names):
        import urllib.request
        ok_list = []
        bad_list = []
        for name in names:
            entry = next((e for e in core.ONLINE_FONTS if e["name"] == name), None)
            if not entry:
                continue
            for fname, url in entry["files"]:
                dest = os.path.join(core.user_font_dir(), fname)
                tmp = dest + ".part"
                try:
                    with urllib.request.urlopen(url, timeout=45) as r:
                        data = r.read()
                    with open(tmp, "wb") as fh:
                        fh.write(data)
                    good, reason = core.Poster().validate_font(tmp)
                    if good:
                        if os.path.exists(dest):
                            os.remove(dest)
                        os.replace(tmp, dest)
                        ok_list.append(fname)
                    else:
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
                        bad_list.append("%s (%s)" % (name, reason))
                except Exception as e:
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                    bad_list.append("%s (%s)" % (name, e))
        return ok_list, bad_list

    def install_font_from_file(self):
        def got(res):
            if res is None:
                return
            _name, b = res
            try:
                tmp = os.path.join(core.user_font_dir(), "_import_tmp.font")
                with open(tmp, "wb") as fh:
                    fh.write(b)
                good, reason = core.Poster().validate_font(tmp)
                if not good:
                    os.remove(tmp)
                    self.notify("Invalid font: %s" % reason, RED)
                    return
                dest = os.path.join(core.user_font_dir(), _name)
                if os.path.exists(dest):
                    os.remove(dest)
                os.replace(tmp, dest)
                self.refresh_fonts()
                self.notify("Font installed: %s" % _name)
            except Exception as e:
                core.log_error(f"install_font_from_file: {e}")
                self.notify("Install failed", RED)
        launched = a_io.pick_file(got, "font/ttf,font/otf,*/*")
        if not launched:
            self._open_file_chooser(got)

    def font_uninstaller(self):
        user_dir = core.user_font_dir()
        names = [n for n, p in core.URDU_FONTS.items()
                 if p and os.path.normpath(os.path.dirname(p)).lower()
                 == os.path.normpath(user_dir).lower()]
        if not names:
            self.notify("No user-installed fonts", GREY)
            return
        pop = Popup(title="Remove a user font", size_hint=(0.9, 0.6),
                    auto_dismiss=False)
        box = vbox()
        items = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(4))
        items.bind(minimum_height=items.setter("height"))
        for nm in sorted(names):
            b = make_btn(nm, lambda n=nm: self._do_uninstall(n, pop), RED,
                         bold=False, height=dp(42))
            items.add_widget(b)
        sv = ScrollView()
        sv.add_widget(items)
        box.add_widget(sv)
        box.add_widget(make_btn("Close", pop.dismiss, (0.5, 0.5, 0.5, 1), bold=False))
        pop.content = box
        pop.open()

    def _do_uninstall(self, name, pop=None):
        p = core.URDU_FONTS.get(name)
        if p:
            core.clear_render_caches()
            core.remove_font_file(p)
            self.refresh_fonts()
            self.notify("Removed %s" % name)
        if pop:
            pop.dismiss()

    # ------------------------------------------------- image picking
    def _pick_image(self, cb):
        def got(res):
            if res is None:
                return
            _name, b = res
            try:
                pil = open_pil(b)
                cb(pil, _name)
            except Exception as e:
                self.notify("Cannot open image: %s" % e, RED)
        launched = a_io.pick_file(got, "image/*")
        if not launched:
            self._open_file_chooser(cb)

    def _open_file_chooser(self, cb):
        def on_path(path):
            try:
                pil = open_pil(open(path, "rb").read())
                cb(pil, os.path.basename(path))
            except Exception as e:
                self.notify("Cannot open file: %s" % e, RED)
        fp = FilePickerPopup(on_path, title="Choose an image",
                             filters=["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"])
        fp.open()

    # ---------------------------------------------------------- saving
    def _export(self, mime, prefix, name, data, note):
        out_dir = core.output_dir()
        path = os.path.join(out_dir, name)
        try:
            with open(path, "wb") as fh:
                fh.write(data)
        except Exception as e:
            core.log_error(f"export write {name}: {e}")
            self.notify("Save failed: %s" % e, RED)
            return
        self.save_status.text = "%s: %s" % (note, path)

        def elsewhere():
            def writer(fd):
                if fd is None:
                    return
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(data)
                    self.notify("Saved elsewhere")
                except Exception as e:
                    self.notify("Save elsewhere failed", RED)
            launched = a_io.create_document(name, mime, writer)
            if not launched:
                self._open_save_chooser(name, data)

        SavedPopup("Saved", "Saved to app storage:\n%s" % path,
                   share_path=path if mime.startswith("image") else None,
                   share_mime=mime, on_elsewhere=elsewhere).open()

    def save_image(self, fmt):
        if self.poster.base_pil is None:
            return
        try:
            data = self.poster.save_image(fmt)
        except Exception as e:
            self.notify("Save failed: %s" % e, RED)
            return
        mime = "image/png" if fmt == "png" else "image/jpeg"
        self._export(mime, fmt, "poster_%s.%s" % (now_stamp(), fmt), data,
                     "Image saved")

    def save_pdf(self):
        if self.poster.base_pil is None:
            return
        try:
            data = self.poster.pdf_bytes()
        except Exception as e:
            self.notify("PDF failed: %s" % e, RED)
            return
        self._export("application/pdf", "pdf", "poster_%s.pdf" % now_stamp(),
                     data, "PDF saved")

    def save_project(self):
        try:
            js = self.poster.project_json()
            data = json_dumps(js).encode("utf-8")
        except Exception as e:
            self.notify("Project save failed: %s" % e, RED)
            return
        self._export("application/json", "qazip", "design_%s.qazip" % now_stamp(),
                     data, "Project saved")

    def open_project(self):
        def got(res):
            if res is None:
                return
            _name, b = res
            try:
                self.poster = core.Poster.from_project_bytes(b)
                self.sync_editor()
                self.rerender_poster()
                self.notify("Project loaded")
            except Exception as e:
                core.log_error(f"open_project: {e}")
                self.notify("Cannot open project", RED)
        launched = a_io.pick_file(got, "application/json,*/*")
        if not launched:
            self._open_project_chooser(got)

    def _open_project_chooser(self, cb):
        def on_path(path):
            try:
                with open(path, "rb") as fh:
                    b = fh.read()
                cb((os.path.basename(path), b))
            except Exception as e:
                self.notify("Cannot read project", RED)
        fp = FilePickerPopup(on_path, title="Open .qazip project",
                             filters=["*.qazip", "*.json"])
        fp.open()

    def _open_save_chooser(self, name, data):
        def on_path(final):
            try:
                with open(final, "wb") as fh:
                    fh.write(data)
                self.notify("Saved: %s" % final)
            except Exception as e:
                self.notify("Save failed: %s" % e, RED)
        sp = SavePopup(on_path, title="Save file", default_name=name,
                       path=core.output_dir())
        sp.open()

    # ----------------------------------------------------------- sync
    def sync_editor(self):
        p = self.poster
        lbl, li = self.selected_label()
        ov, oi = p._selected_overlay()
        if lbl is not None:
            try:
                self.text_entry.text = lbl.text
                self.font_spin.text = lbl.font_name if lbl.font_name in core.URDU_FONTS \
                    else self.font_spin.text
                self.size_sl.value = min(400, lbl.size)
                self.size_val.text = str(lbl.size)
                self.rot_sl.value = lbl.rotation
                self.rot_val.text = str(lbl.rotation)
                self.op_sl.value = lbl.opacity
                self.op_val.text = str(lbl.opacity)
                self.arc_sl.value = min(180, max(-180, lbl.arc_angle))
                self.arc_val.text = str(lbl.arc_angle)
                self.ws_sl.value = min(400, max(-100, lbl.word_spacing))
                self.ws_val.text = str(lbl.word_spacing)
                self.update_urdu_preview()
            except Exception:
                pass
        if ov is not None:
            try:
                self.ov_scale_sl.value = min(3.0, max(0.1, ov.scale))
                self.ov_scale_val.text = "%.2f" % ov.scale
                self.ov_w_sl.value = min(3.0, max(0.1, ov.scale_x))
                self.ov_h_sl.value = min(3.0, max(0.1, ov.scale_y))
                self.flip_h.active = bool(ov.flip_h)
                self.flip_v.active = bool(ov.flip_v)
                self.ov_rot_sl.value = ov.rotation
                self.ov_rot_val.text = str(ov.rotation)
                self.ov_op_sl.value = ov.opacity
                self.ov_op_val.text = str(ov.opacity)
            except Exception:
                pass

    def sync_props(self):
        """Refresh sliders after a drag/resize on the canvas."""
        p = self.poster
        lbl, li = self.selected_label()
        ov, oi = p._selected_overlay()
        if lbl is not None:
            try:
                self.size_sl.value = min(400, lbl.size)
                self.size_val.text = str(lbl.size)
            except Exception:
                pass
        if ov is not None:
            try:
                self.ov_scale_sl.value = min(3.0, max(0.1, ov.scale))
                self.ov_scale_val.text = "%.2f" % ov.scale
                self.ov_w_sl.value = min(3.0, max(0.1, ov.scale_x))
                self.ov_h_sl.value = min(3.0, max(0.1, ov.scale_y))
            except Exception:
                pass

    def delete_selected(self):
        self.poster.delete_selected()
        self.sync_editor()
        self.rerender_poster()

    def rerender_poster(self):
        self.preview.rerender()

    # ----------------------------------------------------------- misc
    def on_stop(self):
        pass


def json_dumps(obj):
    import json as _j
    return _j.dumps(obj, ensure_ascii=False)


def _set_window_icon(self):
    try:
        self.icon = "icon.png"
    except Exception:
        pass


if __name__ == "__main__":
    QaziPosterApp().run()