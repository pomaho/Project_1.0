from __future__ import annotations

import re


_whitespace_re = re.compile(r"\s+")


def normalize_keyword(value: str) -> str:
    trimmed = value.strip().lower()
    if not trimmed:
        return ""
    trimmed = trimmed.replace("ё", "е")
    trimmed = _whitespace_re.sub(" ", trimmed)
    return trimmed
