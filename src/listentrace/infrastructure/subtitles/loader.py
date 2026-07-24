from __future__ import annotations

from pathlib import Path

from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.infrastructure.subtitles.errors import SubtitleParseError
from listentrace.infrastructure.subtitles.srt_parser import parse_srt
from listentrace.infrastructure.subtitles.vtt_parser import parse_vtt

_PARSERS_BY_SUFFIX = {
    ".srt": parse_srt,
    ".vtt": parse_vtt,
}


def parse_subtitle_file(path: Path | str) -> list[SubtitleCue]:
    file_path = Path(path)
    parser = _PARSERS_BY_SUFFIX.get(file_path.suffix.lower())
    if parser is None:
        raise SubtitleParseError(f"unsupported subtitle format: {file_path.suffix!r}")
    return parser(file_path.read_text(encoding="utf-8"))
