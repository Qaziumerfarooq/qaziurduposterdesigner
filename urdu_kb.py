"""Urdu on-screen keypad (Toplevel window).

Lets users type Urdu by clicking buttons, independent of the Windows
keyboard layout or Tkinter RTL typing quirks. Inserts proper Unicode
letters directly into a target text widget.
"""
import tkinter as tk
from tkinter import ttk

URDU_LETTERS = [
    ["آ", "ا", "ب", "پ", "ت", "ٹ", "ث", "ج", "چ"],
    ["ح", "خ", "د", "ڈ", "ذ", "ر", "ڑ", "ز", "ژ"],
    ["س", "ش", "ص", "ض", "ط", "ظ", "ع", "غ", "ف"],
    ["ق", "ک", "گ", "ل", "م", "ن", "ں", "و"],
    ["ھ", "ہ", "ء", "ی", "ے", "ئ", "ؤ", "ۃ"],
]
URDU_DIGITS = list("۰۱۲۳۴۵۶۷۸۹")
URDU_PUNCT = ["۔", "،", "؟", "؛", "٪", "٬"]


class UrduKeypad(tk.Toplevel):
    """A movable keypad that inserts Urdu into a target widget."""

    def __init__(self, master, target, title="اردو کی بورڈ"):
        super().__init__(master)
        self.title(title)
        self.target = target
        self._on_change = None
        self._on_enter = None
        self.attributes("-topmost", True)
        self.configure(bg="#eef3f0")
        self.resizable(False, False)

        top = tk.Frame(self, bg="#0b3d2e")
        top.pack(fill="x")
        self.title_lbl = tk.Label(top, text="اردو کی بورڈ  —  اردو ٹائپنگ",
                                  bg="#0b3d2e", fg="white",
                                  font=("Segoe UI", 10, "bold"))
        self.title_lbl.pack(side="left", padx=8, pady=4)
        tk.Button(top, text="✕", command=self.destroy, width=3,
                  bg="#b33b3b", fg="white").pack(side="right", padx=6, pady=4)

        # letters grid
        grid = tk.Frame(self, bg="#eef3f0")
        grid.pack(padx=8, pady=6)
        for row in URDU_LETTERS:
            r = tk.Frame(grid, bg="#eef3f0")
            r.pack()
            for ch in row:
                tk.Button(r, text=ch, width=3, command=lambda c=ch: self._append(c),
                          font=("Segoe UI", 13), bg="#ffffff",
                          activebackground="#cfe9df").pack(side="left", padx=1, pady=1)

        # digits
        dr = tk.Frame(grid, bg="#eef3f0")
        dr.pack()
        for d in URDU_DIGITS:
            tk.Button(dr, text=d, width=3, command=lambda c=d: self._append(c),
                      font=("Segoe UI", 12), bg="#ffffff",
                      activebackground="#cfe9df").pack(side="left", padx=1, pady=1)

        # punctuation
        pr = tk.Frame(grid, bg="#eef3f0")
        pr.pack()
        for p in URDU_PUNCT:
            tk.Button(pr, text=p, width=3, command=lambda c=p: self._append(c),
                      font=("Segoe UI", 12), bg="#ffffff",
                      activebackground="#cfe9df").pack(side="left", padx=1, pady=1)
        tk.Button(pr, text="Space", width=6, command=self._append_space,
                  font=("Segoe UI", 10), bg="#ffffff",
                  activebackground="#cfe9df").pack(side="left", padx=1, pady=1)

        # control row
        cr = tk.Frame(self, bg="#eef3f0")
        cr.pack(padx=8, pady=6, fill="x")
        tk.Button(cr, text="⌫ Backspace", command=self._backspace,
                  bg="#b8860b", fg="white", font=("Segoe UI", 10)).pack(side="left", padx=2)
        tk.Button(cr, text="Clear Text", command=self._clear,
                  bg="#b33b3b", fg="white", font=("Segoe UI", 10)).pack(side="left", padx=2)
        tk.Button(cr, text="Space", command=self._append_space,
                  bg="#166f52", fg="white", font=("Segoe UI", 10)).pack(side="left", padx=2)
        tk.Button(cr, text="Enter/Apply", command=self._enter,
                  bg="#166f52", fg="white", font=("Segoe UI", 10)).pack(side="left", padx=2)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._on_enter = None

    def set_apply_callback(self, func):
        """func() is called when Enter/Apply is pressed."""
        self._on_enter = func

    def set_on_change(self, func):
        """func(*) is called whenever the target text changes."""
        self._on_change = func

    def _fire_change(self):
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def _focus_target(self):
        try:
            self.target.focus_set()
        except Exception:
            pass

    def _append(self, ch):
        self._focus_target()
        try:
            self.target.insert(tk.INSERT, ch)
        except Exception:
            pass
        self._fire_change()

    def _append_space(self):
        self._append(" ")

    def _backspace(self):
        self._focus_target()
        try:
            if isinstance(self.target, tk.Text):
                pos = self.target.index(tk.INSERT)
                if pos != "1.0":
                    before = self.target.get(pos + "-1c")
                    if before:
                        self.target.delete(pos + "-1c")
            else:
                idx = self.target.index(tk.INSERT)
                if idx > 0:
                    self.target.delete(idx - 1)
        except Exception:
            pass
        self._fire_change()

    def _clear(self):
        try:
            if isinstance(self.target, tk.Text):
                self.target.delete("1.0", tk.END)
            else:
                self.target.delete(0, tk.END)
        except Exception:
            pass
        self._fire_change()

    def _enter(self):
        if self._on_enter:
            try:
                self._on_enter()
            except Exception:
                pass
