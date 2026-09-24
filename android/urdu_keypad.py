"""Urdu on-screen keypad for Kivy (Android + desktop).

Inserts Unicode Urdu letters / digits / punctuation into a Kivy TextInput
at the cursor position, independent of the hardware keyboard. Mirrors the
desktop app's urdu_kb.py layout and behaviour.
"""
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.utils import get_color_from_hex
from kivy.metrics import dp

URDU_LETTERS = [
    ["\u0622", "\u0627", "\u0628", "\u067e", "\u062a", "\u0679", "\u062b", "\u062c", "\u0686"],
    ["\u062d", "\u062e", "\u062f", "\u0688", "\u0630", "\u0631", "\u0691", "\u0632", "\u0698"],
    ["\u0633", "\u0634", "\u0635", "\u0636", "\u0637", "\u0638", "\u0639", "\u063a", "\u0641"],
    ["\u0642", "\u06a9", "\u06af", "\u0644", "\u0645", "\u0646", "\u06ba", "\u0648"],
    ["\u06be", "\u06c1", "\u0621", "\u06cc", "\u06d2", "\u0626", "\u0624", "\u06c3"],
]
URDU_DIGITS = list("\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9")
URDU_PUNCT = ["\u06d4", "\u060c", "\u061f", "\u061b", "\u066a", "\u066c"]

GREEN = get_color_from_hex("#0b3d2e")
GOLD = get_color_from_hex("#b8860b")
RED = get_color_from_hex("#b33b3b")
WHITE = (1, 1, 1, 1)


def _insert_at_cursor(ti, ch):
    """Insert ch at the TextInput cursor position and move the cursor."""
    try:
        idx = ti.cursor[0]
        text = str(ti.text)
        ti.text = text[:idx] + ch + text[idx:]
        ti.cursor = (idx + len(ch), 0)
        return True
    except Exception:
        return False


def _backspace(ti):
    try:
        idx = ti.cursor[0]
        text = str(ti.text)
        if idx <= 0:
            return
        ti.text = text[:idx - 1] + text[idx:]
        ti.cursor = (idx - 1, 0)
    except Exception:
        pass


def _make_key(parent, text, cb, width=42, bg=(1, 1, 1, 1), fg=(0, 0, 0, 1), bold=False):
    b = Button(text=text, size_hint=(None, None), width=dp(width), height=dp(42),
               background_normal="", background_color=bg, color=fg,
               font_size=dp(bold and 16 or 15))
    b.bind(on_release=lambda *_: cb(text))
    parent.add_widget(b)
    return b


class UrduKeypad(Popup):
    """Modal keypad popup bound to a Kivy TextInput."""

    def __init__(self, text_input, on_apply=None, on_change=None, **kwargs):
        kwargs.setdefault("title", "\u0627\u0631\u062f\u0648 \u06a9\u06cc \u0628\u0648\u0631\u0688")
        kwargs.setdefault("size_hint", (0.96, 0.92))
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)
        self.text_input = text_input
        self._on_apply = on_apply
        self._on_change = on_change

        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        grid = GridLayout(cols=9, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for row in URDU_LETTERS:
            for ch in row:
                _make_key(grid, ch, self._append)
        root.add_widget(grid)

        dg = GridLayout(cols=len(URDU_DIGITS) + 1, spacing=dp(4), size_hint_y=None, height=dp(44))
        for d in URDU_DIGITS:
            _make_key(dg, d, self._append)
        _make_key(dg, "Space", lambda *_: self._append(" "), width=88, bg=GREEN, fg=WHITE)
        root.add_widget(dg)

        pg = GridLayout(cols=len(URDU_PUNCT) + 2, spacing=dp(4), size_hint_y=None, height=dp(42))
        for p in URDU_PUNCT:
            _make_key(pg, p, self._append)
        _make_key(pg, "\u2318", lambda *_: _backspace(self.text_input), width=80, bg=GOLD, fg=WHITE)
        _make_key(pg, "Clear", self._clear, width=80, bg=RED, fg=WHITE)
        root.add_widget(pg)

        bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        bt = Button(text="\u21b5 Apply", background_normal="", background_color=GREEN,
                    color=WHITE, font_size=dp(16))
        bt.bind(on_release=lambda *_: self._apply())
        bc = Button(text="Close", background_normal="", background_color=(0.4, 0.4, 0.4, 1),
                    color=WHITE)
        bc.bind(on_release=lambda *_: self.dismiss())
        bar.add_widget(bt)
        bar.add_widget(bc)
        root.add_widget(bar)

        self.content = root

    def _append(self, ch):
        if _insert_at_cursor(self.text_input, ch) and self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def _clear(self):
        self.text_input.text = ""
        self.text_input.cursor = (0, 0)
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def _apply(self):
        if self._on_apply:
            try:
                self._on_apply()
            except Exception:
                pass
        self.dismiss()


def open_keypad(text_input, on_apply=None, on_change=None):
    """Convenience: open a keypad bound to a TextInput."""
    kb = UrduKeypad(text_input, on_apply, on_change)
    kb.open()
    return kb