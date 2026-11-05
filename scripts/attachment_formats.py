"""Container/header identification only; never semantic document/image validation."""
MAX_ATTACHMENT_SOURCE_BYTES = 16 * 1024 * 1024


def signature(raw):
 if raw.startswith(b'%PDF'):return 'pdf_header'
 if raw.startswith(b'PK\x03\x04'):return 'zip_container_header'
 if raw.startswith(b'\xd0\xcf\x11\xe0'):return 'ole_container_header'
 if raw.startswith(b'\xff\xd8\xff'):return 'jpeg_header'
 if raw.startswith(b'\x89PNG\r\n\x1a\n'):return 'png_header'
 return None
