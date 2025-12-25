"""Image loader with support for various formats including PSD."""

from pathlib import Path
from io import BytesIO

from PySide6.QtGui import QPixmap, QImage


# Standard image formats supported by Qt
STANDARD_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico"}

# Special formats that need custom loading
PSD_FORMATS = {".psd", ".psb"}

# All supported formats
ALL_IMAGE_FORMATS = STANDARD_FORMATS | PSD_FORMATS


def is_supported_image(path: Path) -> bool:
    """Check if path is a supported image file."""
    return path.suffix.lower() in ALL_IMAGE_FORMATS


def load_pixmap(path: Path) -> QPixmap:
    """Load image from path, supporting PSD and standard formats."""
    suffix = path.suffix.lower()

    if suffix in PSD_FORMATS:
        return _load_psd(path)
    else:
        return QPixmap(str(path))


def _load_psd(path: Path) -> QPixmap:
    """Load PSD file and convert to QPixmap."""
    try:
        from psd_tools import PSDImage

        psd = PSDImage.open(path)
        # Composite all layers to single image
        pil_image = psd.composite()

        if pil_image is None:
            return QPixmap()

        # Convert PIL image to QPixmap
        # Convert to RGBA if necessary
        if pil_image.mode != "RGBA":
            pil_image = pil_image.convert("RGBA")

        # Save to bytes buffer
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)

        # Load into QPixmap
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    except Exception as e:
        print(f"Error loading PSD: {e}")
        return QPixmap()
