"""Qazi Urdu Poster Designer & Writer - Android / desktop entry point.

python-for-android launches 'main.py' inside the APK. This tiny file just
delegates to the full Kivy application.
"""
import os

# Keep Kivy quiet about its bundled examples/docutils while on mobile.
os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.config import Config  # noqa: E402

Config.set("graphics", "resizable", True)

from kivy_app import QaziPosterApp, _register_kivy_fonts  # noqa: E402


def main():
    _register_kivy_fonts()
    QaziPosterApp().run()


if __name__ == "__main__":
    main()