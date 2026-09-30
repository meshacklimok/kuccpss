"""Upload validators: allow-list by extension, size, and real file content.

Extension and client-supplied content-type are never trusted; the bytes are
inspected. SVG/HTML/JS and anything else not on the allow-list is rejected.
"""
import os

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

IMAGE_FORMATS = {  # extension -> Pillow format
    '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP',
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
_PDF_DANGEROUS = (b'/JavaScript', b'/JS', b'/Launch', b'/EmbeddedFile', b'/RichMedia')


def _ext(f):
    return os.path.splitext(getattr(f, 'name', '') or '')[1].lower()


def _read_all(f):
    f.seek(0)
    data = f.read()
    f.seek(0)
    return data


def _already_stored(f):
    # Existing files (FieldFile already saved) are not re-validated on edit.
    return getattr(f, '_committed', False)


def _check_image(f):
    from PIL import Image
    ext = _ext(f)
    if ext not in IMAGE_FORMATS:
        raise ValidationError('Only JPG, PNG or WEBP images are allowed.', code='bad_image_type')
    if f.size > MAX_IMAGE_BYTES:
        raise ValidationError('Image must be 5 MB or smaller.', code='too_large')
    try:
        f.seek(0)
        img = Image.open(f)
        fmt = img.format
        if img.width * img.height > MAX_IMAGE_PIXELS:
            raise ValidationError('Image dimensions are too large.', code='too_large')
        img.verify()
    except ValidationError:
        raise
    except Exception:
        raise ValidationError('This file is not a valid image.', code='bad_image')
    finally:
        f.seek(0)
    if fmt != IMAGE_FORMATS[ext]:
        raise ValidationError('File content does not match its extension.', code='mismatch')


def _check_pdf(f):
    if f.size > MAX_PDF_BYTES:
        raise ValidationError('PDF must be 10 MB or smaller.', code='too_large')
    data = _read_all(f)
    if not data.lstrip()[:5] == b'%PDF-':
        raise ValidationError('This file is not a valid PDF.', code='bad_pdf')
    if any(tok in data for tok in _PDF_DANGEROUS):
        raise ValidationError('PDFs containing scripts or embedded files are not allowed.', code='unsafe_pdf')


@deconstructible
class SafeImageValidator:
    def __call__(self, f):
        if _already_stored(f):
            return
        _check_image(f)

    def __eq__(self, other):
        return isinstance(other, SafeImageValidator)


@deconstructible
class SafeDocumentValidator:
    """Image (jpg/png/webp) or PDF."""
    def __call__(self, f):
        if _already_stored(f):
            return
        if _ext(f) == '.pdf':
            _check_pdf(f)
        else:
            _check_image(f)

    def __eq__(self, other):
        return isinstance(other, SafeDocumentValidator)


@deconstructible
class SafePDFValidator:
    def __call__(self, f):
        if _already_stored(f):
            return
        if _ext(f) != '.pdf':
            raise ValidationError('Only PDF files are allowed.', code='bad_pdf')
        _check_pdf(f)

    def __eq__(self, other):
        return isinstance(other, SafePDFValidator)
