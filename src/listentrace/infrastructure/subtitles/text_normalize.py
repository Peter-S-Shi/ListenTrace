from __future__ import annotations

import re

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_cue_text(raw_text: str) -> str:
    without_tags = _TAG_RE.sub("", raw_text)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()
