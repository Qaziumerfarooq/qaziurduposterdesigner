"""Runtime smoke test for the Kivy UI (opens a small window briefly).

Runs the full app build + exercises every major feature programmatically,
then quits. Requires kivy installed on the host + a display.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

os.environ.setdefault("KIVY_NO_ARGS", "1")
import kivy  # noqa: F401

from kivy.core.window import Window
from kivy.clock import Clock

import kivy_app
from kivy_app import QaziPosterApp, pil_to_texture
from PIL import Image as PILImage

Window.size = (760, 560)

RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append(("PASS", name))
        print("PASS:", name)
    except Exception as e:
        import traceback
        traceback.print_exc()
        RESULTS.append(("FAIL", name))
        print("FAIL:", name, "->", e)


# silence popups during the automated run
class _FakePopup(object):
    def __init__(self, *a, **kw):
        pass

    def open(self):
        pass

    def dismiss(self):
        pass


kivy_app.SavedPopup = _FakePopup
kivy_app.ColorPopup = _FakePopup
kivy_app.CropPopup = _FakePopup
kivy_app.KeypadPopup = _FakePopup
kivy_app.FilePickerPopup = _FakePopup
kivy_app.SavePopup = _FakePopup
kivy_app.PromptPopup = _FakePopup


app = QaziPosterApp()


def _after_build(*_a):
    try:
        check("poster created + first render", lambda: app.poster.width == 1600)

        def test_add_text():
            app.add_text()
            assert app.poster.selected[0] == "label"
            app.apply_urdu_text()
            app.sync_editor()
            app.label_prop_changed()
            app._set_sl(app.arc_sl, 45)
            app.label_prop_changed()
            app._set_sl(app.ws_sl, 10)
            app.label_prop_changed()
        check("text add / apply / props", test_add_text)

        def test_bg():
            img = PILImage.new("RGB", (500, 700), (200, 60, 60))
            app._bg_picked(img, "test.png")
            assert app.poster.width == 500
            img2 = PILImage.new("RGB", (800, 600), (30, 200, 90))
            app._bg_replaced(img2, "t2.png")
            assert app.poster.width == 800
        check("background set + replace keeps design", test_bg)

        def test_overlay():
            ov = PILImage.new("RGBA", (120, 80), (0, 0, 0, 0))
            d = __import__("PIL.ImageDraw", fromlist=["Draw"]).Draw(ov)
            d.rectangle((10, 10, 110, 70), fill=(255, 0, 0, 255))
            app._overlay_picked(ov, "logo.png")
            assert app.poster.selected[0] == "overlay"
            app.ov_scale_sl.value = 1.5
            app.overlay_scale_changed()
            app.ov_w_sl.value = 0.6
            app.ov_h_sl.value = 2.0
            app.overlay_size_changed()
            app.flip_h.active = True
            app.overlay_flip_changed()
            app.ov_rot_sl.value = 90
            app.overlay_rot_changed()
            app.ov_op_sl.value = 50
            app.overlay_opacity_changed()
            assert app.poster.overlays[0].scale_x == 0.6
            assert app.poster.overlays[0].opacity == 50
        check("overlay add + adjust (size / w/h / flip / rotate / opacity)",
              test_overlay)

        def test_replace_overlay():
            app.select_and_test = 1
            ov = PILImage.new("RGBA", (40, 40), (0, 0, 255, 255))
            app._overlay_replaced(ov, "r.png")
            assert app.poster.overlays[0].base_image.size == (40, 40)
        check("replace overlay image", test_replace_overlay)

        def test_layers():
            for mode in ("front", "forward", "backward", "back"):
                app.layer_cmd(mode)
        check("layer ordering", test_layers)

        def test_canvas_ops():
            app.new_blank_card()
            assert app.poster.width == 1050
            app.poster.recolor_background((255, 255, 255))
        check("new card + canvas colour", test_canvas_ops)

        def test_render_engine():
            app.poster.new_canvas(1200, 1600, (20, 40, 60))
            app.poster.add_label("\u0627\u0631\u062f\u0648 \u0679\u06cc\u0633\u0679", size=80)
            app.poster.labels[-1].color = (255, 200, 0)
            full = app.poster.render_full()
            prev = app.poster.render_preview(300, 400)
            assert full.size == (1200, 1600)
            assert prev.size == (300, 400)
            tex = pil_to_texture(prev)
            assert tuple(tex.size) == (300, 400)
            hit = app.poster.hit_test(600, 800)
            assert hit == ("label", 0)
        check("render engine inside UI", test_render_engine)

        def test_select_and_resize():
            app.poster.selected = ("label", 0)
            box = app.poster.element_box("label", 0)
            assert box is not None
            app.poster.do_resize("label", 0, box[0] + 200, box[1])
            app.poster.move_selected_to(500, 400, offset=(0, 0))
            assert app.poster.labels[0].x == 500 / 1200
        check("corner resize + move API", test_select_and_resize)

        def test_save_png():
            data = app.poster.save_image("png")
            assert data[:8] == b"\x89PNG\r\n\x1a\n"
        check("save PNG bytes", test_save_png)

        def test_save_pdf():
            data = app.poster.pdf_bytes()
            assert data[:5] == b"%PDF-"
        check("save PDF bytes", test_save_pdf)

        def test_project_roundtrip():
            js = app.poster.project_json()
            raw = __import__("json").dumps(js).encode("utf-8")
            import core
            p2 = core.Poster.from_project_bytes(raw)
            assert p2.render_full().size == (1200, 1600)
        check("project save/open", test_project_roundtrip)

        def test_panel_toggle():
            app._toggle_panel()
            app._toggle_panel()
            app._zoom_fit()
        check("panel toggle + zoom fit", test_panel_toggle)

        def test_keypad():
            from urdu_keypad import UrduKeypad, _backspace
            kb = UrduKeypad(app.text_entry)
            app.text_entry.text = "\u0627\u0644\u0633\u0644\u0627\u0645"
            app.text_entry.cursor = (10, 0)
            kb._append("\u0639\u0644\u06cc\u06a9\u0645")
            _backspace(app.text_entry)
            kb.dismiss()
        check("urdu keypad insert/backspace", test_keypad)

    finally:
        app.stop()


Clock.schedule_once(_after_build, 0.4)
try:
    app.run()
except SystemExit:
    pass

failed = [r for r in RESULTS if r[0] == "FAIL"]
print("=" * 50)
print("UI SMOKE:", "PASSED %d / %d" % (len(RESULTS) - len(failed), len(RESULTS)))
sys.exit(1 if failed else 0)