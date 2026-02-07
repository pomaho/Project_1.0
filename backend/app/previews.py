from __future__ import annotations

import io
from pathlib import Path
from typing import Literal

from PIL import Image

try:
    import pyvips
except Exception:  # pragma: no cover - fallback if vips missing
    pyvips = None


PreviewSize = Literal["thumb", "medium"]

# Use a single 800px preview for all sizes to speed up generation.
SIZE_MAP: dict[PreviewSize, int] = {
    "thumb": 800,
    "medium": 800,
}


class PreviewError(RuntimeError):
    pass


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _vips_resize(image_path: str, max_size: int) -> bytes:
    if pyvips is None:
        raise PreviewError("pyvips not available")
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    scale = min(max_size / image.width, max_size / image.height, 1.0)
    if scale != 1.0:
        image = image.resize(scale)
    return image.write_to_buffer(".webp[Q=80]")


def _pillow_resize(image_path: str, max_size: int) -> bytes:
    with Image.open(image_path) as img:
        img.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=80)
        return buffer.getvalue()


def generate_preview(image_path: str, size: PreviewSize) -> bytes:
    max_size = SIZE_MAP[size]
    try:
        return _vips_resize(image_path, max_size)
    except Exception:
        return _pillow_resize(image_path, max_size)


def preview_path(root: str, file_id: str, size: PreviewSize) -> Path:
    # All sizes resolve to the same file.
    return Path(root) / file_id / "preview.webp"


def write_preview(root: str, file_id: str, size: PreviewSize, data: bytes) -> str:
    target = preview_path(root, file_id, size)
    _ensure_dir(target.parent)
    target.write_bytes(data)
    return str(target)
