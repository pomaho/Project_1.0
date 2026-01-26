from __future__ import annotations

import json
import mimetypes
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_exif_datetime(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_keywords(record: dict[str, Any]) -> list[str]:
    candidates = []
    for key in (
        "XMP:Subject",
        "IPTC:Keywords",
        "Keywords",
        "XMP:TagsList",
    ):
        value = record.get(key)
        if isinstance(value, list):
            candidates.extend([str(item) for item in value])
        elif isinstance(value, str):
            candidates.append(value)
    return candidates


def extract_metadata(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}

    try:
        result = subprocess.run(
            [
                "exiftool",
                "-json",
                "-n",
                "-charset",
                "utf8",
                str(file_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        record = payload[0] if payload else {}
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        record = {}

    mime, _ = mimetypes.guess_type(file_path.name)

    return {
        "keywords": _extract_keywords(record),
        "shot_at": _parse_exif_datetime(
            record.get("DateTimeOriginal")
            or record.get("CreateDate")
            or record.get("XMP:CreateDate")
            or ""
        ),
        "width": record.get("ImageWidth"),
        "height": record.get("ImageHeight"),
        "mime": record.get("MIMEType") or mime or "application/octet-stream",
    }
