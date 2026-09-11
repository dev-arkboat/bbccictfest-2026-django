"""Shared QR-code helper (PNG bytes for a URL)."""

from io import BytesIO

import qrcode


def qr_png_bytes(url: str, box_size: int = 10, border: int = 4) -> bytes:
    img = qrcode.make(url, box_size=box_size, border=border)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
