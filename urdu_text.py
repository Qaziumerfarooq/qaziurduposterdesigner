import arabic_reshaper
from bidi.algorithm import get_display

def normalize(text: str) -> str:
    if not text: return ""
    # Standardize Urdu characters:
    # 064A (Arabic Ya) -> 06CC (Urdu Ya)
    # 0649 (Alef Maksura) -> 06CC (Urdu Ya)
    # Keep 0626 (Ya with Hamza) as it is essential for Urdu.
    table = {"\u064a": "\u06cc", "\u0649": "\u06cc"}
    return "".join(table.get(ch, ch) for ch in text)

def plain(text: str) -> str:
    """Return readable normalized text (logical order) for on-screen widgets."""
    return normalize(text)

def shape(text: str) -> str:
    if not text: return ""
    # Configuration to EXPLICITLY prevent vertical lines/artifacts
    conf = {
        'delete_harakat': True,
        'support_zwj': False, # ZWJ is often the cause of the vertical bar artifact
        'use_unshaped_instead_of_isolated': True
    }
    reshaper = arabic_reshaper.ArabicReshaper(configuration=conf)
    reshaped = reshaper.reshape(normalize(text))
    return get_display(reshaped)
