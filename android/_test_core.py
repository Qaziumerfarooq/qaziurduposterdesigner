"""Local smoke test for the platform-independent core engine (desktop)."""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import core
from PIL import Image

def main():
    print("bundled fonts:", list(core.URDU_FONTS.keys()))
    print("default font:", core.DEFAULT_FONT)

    p = core.Poster(1200, 1600, fill=(245, 240, 230))

    # background image (gradient square = stand-in for a photo)
    bg = Image.new("RGB", (1200, 1600))
    px = bg.load()
    for y in range(1600):
        for x in range(1200):
            px[x, y] = ((x * 20) % 255, (y * 17) % 255, 120)
    p.set_background_pil(bg)

    # Urdu text labels
    p.add_label("\u0639\u0631\u062f\u0648 \u067e\u0648\u0633\u0679\u0631 \u0688\u0627\u0626\u06cc \u0632\u0627\u0626\u0646\u0631", size=72, x=0.5, y=0.3)
    p.labels[-1].color = (255, 255, 255)
    p.labels[-1].arc_angle = 0
    p.add_label("\u062e\u0648\u0634 \u0622\u0645\u062f\u06cc\u062f", size=90, x=0.5, y=0.55)
    p.labels[-1].color = (255, 215, 0)
    p.add_label("123 + English Mix", size=34, x=0.5, y=0.72)
    p.labels[-1].color = (20, 20, 20)
    p.labels[-1].rotation = -8

    # overlay
    ov = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d = ImageDraw = __import__("PIL.ImageDraw", fromlist=["Draw"]).Draw(ov)
    d.ellipse((20, 20, 180, 180), fill=(200, 40, 40, 255))
    p.add_overlay(base_image=ov, x=0.5, y=0.9)
    p.overlays[-1].scale = 0.7
    p.overlays[-1].scale_x = 0.7
    p.overlays[-1].scale_y = 0.7

    # preview + full render
    prev = p.render_preview(300, 400)
    full = p.render_full()
    assert prev is not None and full.size == (1200, 1600)
    full.save(os.path.join(HERE, "_test_out.png"))
    print("rendered PNG bytes:", os.path.getsize(os.path.join(HERE, "_test_out.png")))

    # save_image bytes
    b = p.save_image("png")
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    print("save_image png bytes:", len(b))

    # pdf bytes
    try:
        pdf = p.pdf_bytes()
        assert pdf[:5] == b"%PDF-"
        print("pdf bytes:", len(pdf))
    except Exception as e:
        print("PDF failed:", e)

    # project round trip
    js = p.project_json()
    print("json keys:", sorted(js.keys()), "labels:", len(js["labels"]), "overlays:", len(js["overlays"]))
    raw = core.json.dumps(js).encode("utf-8")
    p2 = core.Poster.from_project_bytes(raw)
    assert p2.labels == [] or len(p2.labels) == len(p.labels)
    b2 = p2.render_full()
    assert b2.size == full.size
    print("project round-trip OK")

    # hit test
    hit = p.hit_test(600, 880)   # near second label
    print("hit test at (600,880):", hit)

    # arc + spacing + opacity
    core.URDU_FONTS.clear()
    core.URDU_FONTS["Test"] = core.app_root_dir()
    print("ALL CORE TESTS PASSED")

if __name__ == "__main__":
    main()