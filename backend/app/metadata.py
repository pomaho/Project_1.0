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
    for fmt in (
        "%Y:%m:%d %H:%M:%S%z",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _split_keywords(value: str) -> list[str]:
    if not value:
        return []
    separators = [";", ","]
    for sep in separators:
        if sep in value:
            parts = [item.strip() for item in value.split(sep)]
            return [item for item in parts if item]
    return [value.strip()]


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        for item in value:
            coerced = _coerce_text(item)
            if coerced:
                return coerced
        return None
    if isinstance(value, dict):
        for item in value.values():
            coerced = _coerce_text(item)
            if coerced:
                return coerced
        return None
    return None


def _extract_keywords(record: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in (
        "Subject",
        "HierarchicalSubject",
        "TagsList",
        "XPKeywords",
        "XMP:Subject",
        "XMP-dc:Subject",
        "XMP:HierarchicalSubject",
        "XMP-lr:HierarchicalSubject",
        "XMP:TagsList",
        "XMP:Keywords",
        "MWG:Keywords",
        "IPTC:Keywords",
        "IPTC:Subject",
        "EXIF:XPKeywords",
        "Keywords",
    ):
        value = record.get(key)
        if isinstance(value, list):
            candidates.extend([str(item) for item in value])
        elif isinstance(value, str):
            candidates.extend(_split_keywords(value))
    return candidates


EXIFTOOL_TIMEOUT_SECONDS = 10


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
            timeout=EXIFTOOL_TIMEOUT_SECONDS,
        )
        payload = json.loads(result.stdout)
        record = payload[0] if payload else {}
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        record = {}

    mime, _ = mimetypes.guess_type(file_path.name)

    title = (
        record.get("XMP:Title")
        or record.get("XMP-dc:Title")
        or record.get("IPTC:Headline")
        or record.get("XMP:Headline")
        or record.get("EXIF:ImageDescription")
        or record.get("Title")
    )
    description = (
        record.get("XMP:Description")
        or record.get("XMP-dc:Description")
        or record.get("IPTC:Caption-Abstract")
        or record.get("EXIF:ImageDescription")
        or record.get("Description")
    )

    shot_at = _parse_exif_datetime(
        record.get("DateTimeOriginal")
        or record.get("EXIF:CreateDate")
        or record.get("CreateDate")
        or record.get("XMP:CreateDate")
        or record.get("ModifyDate")
        or record.get("XMP:ModifyDate")
        or record.get("FileModifyDate")
        or ""
    )

    return {
        "keywords": _extract_keywords(record),
        "shot_at": shot_at,
        "width": record.get("ImageWidth"),
        "height": record.get("ImageHeight"),
        "mime": record.get("MIMEType") or mime or "application/octet-stream",
        "title": _coerce_text(title),
        "description": _coerce_text(description),
    }


def extract_shot_at_only(path: str) -> datetime | None:
    file_path = Path(path)
    if not file_path.exists():
        return None

    try:
        result = subprocess.run(
            [
                "exiftool",
                "-json",
                "-n",
                "-charset",
                "utf8",
                "-DateTimeOriginal",
                "-CreateDate",
                "-XMP:CreateDate",
                "-ModifyDate",
                "-XMP:ModifyDate",
                "-FileModifyDate",
                str(file_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=EXIFTOOL_TIMEOUT_SECONDS,
        )
        payload = json.loads(result.stdout)
        record = payload[0] if payload else {}
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None

    return _parse_exif_datetime(
        record.get("DateTimeOriginal")
        or record.get("EXIF:CreateDate")
        or record.get("CreateDate")
        or record.get("XMP:CreateDate")
        or record.get("ModifyDate")
        or record.get("XMP:ModifyDate")
        or record.get("FileModifyDate")
        or ""
    )
