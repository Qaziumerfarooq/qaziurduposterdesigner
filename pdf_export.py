"""Render a PIL image as a PDF page using reportlab."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image


def image_to_pdf(image: Image.Image, pdf_path: str, page_size=None):
    """Save a PIL RGB image to a single-page PDF.

    Places the image centered on the given page (default A4 portrait).
    """
    img = image.convert("RGB")
    w_px, h_px = img.size

    if page_size is None:
        # Use the image aspect for a custom page so nothing is cropped.
        # Cap at A4-like maximums.
        page_w = w_px
        page_h = h_px
    else:
        page_w, page_h = page_size

    c = canvas.Canvas(pdf_path, pagesize=(page_w, page_h))
    c.drawInlineImage(img, 0, 0, width=page_w, height=page_h)
    # tag metadata
    c.setTitle("Qazi Urdu Poster Designer & Writer")
    c.setAuthor("Qazi Muhammad Umer Farooq Hajveri")
    c.showPage()
    c.save()
    return pdf_path


def save_as_pdf(image: Image.Image, pdf_path: str, fit_a4=True):
    """Save an image as a PDF, optionally fitting onto an A4 page.

    If fit_a4 is True, the image is embedded at its true pixel print size
    centered on an A4 page (150 DPI reference) without distortion.
    """
    img = image.convert("RGB")
    if fit_a4:
        target_w, target_h = (1240, 1754)  # A4 at ~150 DPI
        w, h = img.size
        ratio = min(target_w / w, target_h / h)
        draw_w = int(w * ratio)
        draw_h = int(h * ratio)

        c = canvas.Canvas(pdf_path, pagesize=(target_w, target_h))
        x = (target_w - draw_w) // 2
        y = (target_h - draw_h) // 2
        c.drawInlineImage(img, x, y, width=draw_w, height=draw_h)
        c.setTitle("Qazi Urdu Poster Designer & Writer")
        c.setAuthor("Qazi Muhammad Umer Farooq Hajveri")
        c.showPage()
        c.save()
    else:
        image_to_pdf(img, pdf_path)
    return pdf_path
