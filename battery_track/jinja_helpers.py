"""Helpers that print formats (Jinja) can call. Registered in hooks.py -> jinja = {"methods": [...]}."""

import pyqrcode  # already installed with Frappe (used for 2FA QR codes)


def qr_code_data_uri(text, scale=5):
	"""QR code for `text` as an inline PNG: <img src="{{ qr_code_data_uri(doc.name) }}">

	Inline (data URI) means no image file is saved anywhere, and the PDF renderer
	doesn't need to download anything.
	"""
	if not text:
		return ""
	qr = pyqrcode.create(str(text), error="M")  # M = can still be read if ~15% of the label is damaged
	return "data:image/png;base64," + qr.png_as_base64_str(scale=scale)
