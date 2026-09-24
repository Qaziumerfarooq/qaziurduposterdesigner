# Qazi Urdu Poster Designer & Writer — Android build

Mobile (Kivy) build of the poster designer. The exact same rendering engine
(`core.py`) powers the desktop app, so **no desktop feature is dropped**. The
APK is built from this `android/` folder.

## Contents

| File | Purpose |
| --- | --- |
| `main.py` | APK entry point (launched by python-for-android) |
| `kivy_app.py` | Full Kivy UI: canvas, gestures, editor panels, file/share dialogs |
| `core.py` | Platform-independent PIL engine (labels, overlays, layers, crop, bg-removal, project save/load, PDF) |
| `urdu_keypad.py` | On-screen Urdu keypad (letters, digits, punctuation) |
| `a_io.py` | Android SAF file pick/save/share (jnius) |
| `urdu_text.py`, `urdu_render.py`, `pdf_export.py`, `fonts_res.py` | Shared desktop modules (HarfBuzz optional, falls back safely) |
| `fonts/` | 15 bundled Urdu fonts (~28 MB, shipped inside the APK) |
| `buildozer.spec` | Buildozer configuration |
| `../.github/workflows/build-apk.yml` | Cloud APK build (recommended, no Linux needed) |
| `_test_core.py`, `_test_ui.py` | Smoke tests (run on a desktop Python) |

## Build the APK

### Option A — GitHub Actions (recommended, zero local setup)

1. Push this repository to GitHub.
2. GitHub Actions → “Build Android APK” → **Run workflow** (or any push to
   `main`/`master` touching `android/`).
3. Download the APK from the run's **Artifacts** tab (`qaziurduposter-preview`).

### Option B — Local Linux / WSL

```bash
cd android
sudo apt update && sudo apt install -y zip unzip openjdk-17-jdk autoconf automake libtool pkg-config cmake ninja-build git ccache libgl1 libgl1-mesa-dev libgles2-mesa libgles2-mesa-dev libegl1 libegl1-mesa libdrm2 libxkbcommon0 libglib2.0-0
python3 -m pip install --upgrade pip buildozer cython
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
buildozer android debug
```

Output: `bin/qaziurduposter-1.0.0-*.apk`. First build downloads the Android SDK/
NDK and can take a long time.

### Test on desktop first (optional, no Android needed)

```bash
python -m pip install kivy pillow arabic_reshaper python-bidi reportlab fonttools plyer
python _test_ui.py     # opens a small window briefly, runs 14 feature checks
python -m py_compile core.py kivy_app.py main.py a_io.py urdu_keypad.py
python main.py         # run the actual app on a PC
```

## Feature checklist

Text & typography
- Add multiple Urdu text boxes (keypad with letters, digits, punctuation; insert at cursor)
- Move, resize (corner drag), rotate, delete, duplicate
- Font family (15 bundled Urdu fonts incl. Aligarh Nastaleeq), font *name* selection
- Font size, color (picker), opacity, rotation, arc (curved text), word-spacing
- Bring to front / forward / backward / to back (layer order)

Overlays / photos
- Add pictures (gallery / document picker), replace picture
- Move, proportional resize, independent width/height scale, rotate, flip H/V, opacity
- **Crop** (draw a crop box), **background eraser** (AI `rembg` when installed; built-in offline border eraser always available), **picture adjuster** sliders
- Duplicate, delete, layer ordering

Canvas / background
- New blank card (width/height/color), transparent option
- Set / replace background image (keeps your design), recolor background
- Fit view, zoom (pinch), pan

Project & export
- **Save project** / **Open project** (`.qazip` JSON bundle, full round-trip)
- Export PNG or JPG (quality), save to device (SAF) / share
- Export PDF (A4 @ ~150 DPI)

Platform notes
- Urdu shaping: HarfBuzz when available; automatic arabic_reshaper + bidi
  fallback everywhere else (no dependency on the removed uharfbuzz p4a recipe).
- The `rembg`/`onnxruntime` AI eraser is desktop-only (huge model); the app
  handles the missing module gracefully and still offers the instant offline
  background eraser on Android.