"""Image loader with support for various formats including PSD, RAW, HEIC, etc."""

from pathlib import Path
from io import BytesIO

from PySide6.QtGui import QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt
from PIL import Image


# Standard image formats supported by Qt natively
QT_NATIVE_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".ico"}

# SVG formats (Qt SVG module)
SVG_FORMATS = {".svg", ".svgz"}

# PSD/PSB formats (psd-tools)
PSD_FORMATS = {".psd", ".psb"}

# HEIC/HEIF formats (pillow-heif)
HEIF_FORMATS = {".heic", ".heif"}

# AVIF format (pillow-avif-plugin or Pillow 10+)
AVIF_FORMATS = {".avif"}

# RAW camera formats (rawpy)
RAW_FORMATS = {
    ".raw",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".dng",
    ".orf",
    ".rw2",
    ".pef",
    ".srw",
    ".raf",
    ".mrw",
    ".dcr",
    ".kdc",
    ".erf",
    ".3fr",
    ".mef",
    ".mos",
    ".nrw",
    ".ptx",
    ".r3d",
    ".rwl",
    ".rwz",
    ".sr2",
    ".srf",
    ".x3f",
}

# OpenEXR HDR format (OpenEXR)
EXR_FORMATS = {".exr"}

# Other formats supported by Pillow
PILLOW_FORMATS = {
    ".jfif",
    ".jpe",  # JPEG variants
    ".tga",
    ".icb",
    ".vda",
    ".vst",  # Targa
    ".pcx",  # PCX
    ".dds",  # DirectDraw Surface
    ".hdr",  # Radiance HDR
    ".pbm",
    ".pgm",
    ".ppm",
    ".pnm",  # Netpbm
    ".sgi",
    ".rgb",
    ".rgba",
    ".bw",  # SGI
    ".fits",
    ".fit",
    ".fts",  # FITS
    ".im",  # IM
    ".msp",  # MSP
    ".palm",  # Palm
    ".pdf",  # PDF (first page only)
    ".xbm",  # XBM
    ".xpm",  # XPM
    ".eps",  # EPS (if Ghostscript available)
    ".wmf",
    ".emf",  # Windows Metafile
    ".cur",  # Windows cursor
    ".ani",  # Animated cursor
    ".icns",  # macOS icon
    ".jp2",
    ".j2k",
    ".jpc",
    ".jpf",
    ".jpx",
    ".j2c",  # JPEG 2000
    ".qoi",  # QOI (Quite OK Image)
}

# All supported formats
ALL_IMAGE_FORMATS = (
    QT_NATIVE_FORMATS
    | SVG_FORMATS
    | PSD_FORMATS
    | HEIF_FORMATS
    | AVIF_FORMATS
    | RAW_FORMATS
    | EXR_FORMATS
    | PILLOW_FORMATS
)


def is_supported_image(path: Path) -> bool:
    """Check if path is a supported image file."""
    return path.suffix.lower() in ALL_IMAGE_FORMATS


def load_pixmap(path: Path) -> QPixmap:
    """Load image from path, supporting various formats."""
    suffix = path.suffix.lower()

    if suffix in QT_NATIVE_FORMATS:
        return QPixmap(str(path))
    elif suffix in SVG_FORMATS:
        return _load_svg(path)
    elif suffix in PSD_FORMATS:
        return _load_psd(path)
    elif suffix in HEIF_FORMATS:
        return _load_heif(path)
    elif suffix in AVIF_FORMATS:
        return _load_avif(path)
    elif suffix in RAW_FORMATS:
        return _load_raw(path)
    elif suffix in EXR_FORMATS:
        return _load_exr(path)
    elif suffix in PILLOW_FORMATS:
        return _load_with_pillow(path)
    else:
        # Fallback to Qt
        return QPixmap(str(path))


def _pil_to_pixmap(pil_image: Image.Image) -> QPixmap:
    """Convert PIL Image to QPixmap."""
    if pil_image is None:
        return QPixmap()

    # Convert to RGBA if necessary
    if pil_image.mode not in ("RGBA", "RGB"):
        if pil_image.mode == "P":
            pil_image = pil_image.convert("RGBA")
        elif pil_image.mode in ("L", "LA"):
            pil_image = pil_image.convert("RGBA")
        else:
            try:
                pil_image = pil_image.convert("RGBA")
            except Exception:
                pil_image = pil_image.convert("RGB")

    # Save to bytes buffer as PNG
    buffer = BytesIO()
    pil_image.save(buffer, format="PNG")
    buffer.seek(0)

    # Load into QPixmap
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())
    return pixmap


def _load_svg(path: Path) -> QPixmap:
    """Load SVG file and render to QPixmap."""
    try:
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QPixmap()

        # Render at reasonable size (max 4096px)
        size = renderer.defaultSize()
        if size.width() > 4096 or size.height() > 4096:
            size.scale(4096, 4096, Qt.AspectRatioMode.KeepAspectRatio)

        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        from PySide6.QtGui import QPainter

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        return pixmap
    except Exception as e:
        print(f"Error loading SVG: {e}")
        return QPixmap()


def _load_psd(path: Path) -> QPixmap:
    """Load PSD file and convert to QPixmap."""
    try:
        from psd_tools import PSDImage

        psd = PSDImage.open(path)
        pil_image = psd.composite()
        return _pil_to_pixmap(pil_image)

    except Exception as e:
        print(f"Error loading PSD: {e}")
        return QPixmap()


def _load_heif(path: Path) -> QPixmap:
    """Load HEIC/HEIF file and convert to QPixmap."""
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()

        pil_image = Image.open(path)
        return _pil_to_pixmap(pil_image)

    except ImportError:
        print("pillow-heif not installed, cannot load HEIC/HEIF")
        return QPixmap()
    except Exception as e:
        print(f"Error loading HEIF: {e}")
        return QPixmap()


def _load_avif(path: Path) -> QPixmap:
    """Load AVIF file and convert to QPixmap."""
    try:
        # Try pillow-avif-plugin first, then fall back to native Pillow support
        try:
            import pillow_avif
        except ImportError:
            pass  # Pillow 10+ has native AVIF support

        pil_image = Image.open(path)
        return _pil_to_pixmap(pil_image)

    except Exception as e:
        print(f"Error loading AVIF: {e}")
        return QPixmap()


def _load_raw(path: Path) -> QPixmap:
    """Load RAW camera file and convert to QPixmap."""
    try:
        import rawpy

        with rawpy.imread(str(path)) as raw:
            # Use default postprocessing
            rgb = raw.postprocess(use_camera_wb=True, half_size=False)

        pil_image = Image.fromarray(rgb)
        return _pil_to_pixmap(pil_image)

    except ImportError:
        print("rawpy not installed, cannot load RAW files")
        return QPixmap()
    except Exception as e:
        print(f"Error loading RAW: {e}")
        return QPixmap()


def _load_exr(path: Path) -> QPixmap:
    """Load OpenEXR file and convert to QPixmap."""
    try:
        import OpenEXR
        import Imath
        import numpy as np

        exr_file = OpenEXR.InputFile(str(path))
        header = exr_file.header()
        dw = header["dataWindow"]
        width = dw.max.x - dw.min.x + 1
        height = dw.max.y - dw.min.y + 1

        # Read RGB channels
        pt = Imath.PixelType(Imath.PixelType.FLOAT)
        channels = ["R", "G", "B"]

        rgb_data = []
        for c in channels:
            if c in header["channels"]:
                data = exr_file.channel(c, pt)
                rgb_data.append(np.frombuffer(data, dtype=np.float32).reshape(height, width))
            else:
                rgb_data.append(np.zeros((height, width), dtype=np.float32))

        # Stack and tone map (simple gamma)
        rgb = np.stack(rgb_data, axis=-1)
        rgb = np.clip(rgb, 0, 1)
        rgb = (rgb ** (1 / 2.2) * 255).astype(np.uint8)

        pil_image = Image.fromarray(rgb, "RGB")
        return _pil_to_pixmap(pil_image)

    except ImportError:
        print("OpenEXR not installed, cannot load EXR files")
        return QPixmap()
    except Exception as e:
        print(f"Error loading EXR: {e}")
        return QPixmap()


def _load_with_pillow(path: Path) -> QPixmap:
    """Load image using Pillow."""
    try:
        pil_image = Image.open(path)
        # Handle animated images - get first frame
        if hasattr(pil_image, "n_frames") and pil_image.n_frames > 1:
            pil_image.seek(0)
        return _pil_to_pixmap(pil_image)

    except Exception as e:
        print(f"Error loading with Pillow: {e}")
        return QPixmap()
