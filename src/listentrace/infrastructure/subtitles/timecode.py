from __future__ import annotations

import re

from listentrace.infrastructure.subtitles.errors import SubtitleParseError

# Accepts "HH:MM:SS,mmm" (SRT) and "HH:MM:SS.mmm" / "MM:SS.mmm" (WebVTT)
_TIMECODE_RE = re.compile(
    r"^(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})[.,](?P<millis>\d{1,3})$"
)


def parse_timecode(raw: str, line_number: int | None = None) -> int:
    match = _TIMECODE_RE.match(raw.strip())
    if not match:
        raise SubtitleParseError(f"invalid timecode {raw!r}", line_number)

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis = int(match.group("millis").ljust(3, "0"))

    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def parse_cue_timing_line(line: str, line_number: int | None = None) -> tuple[int, int]:
    if "-->" not in line:
        raise SubtitleParseError(f"expected a cue timing line, got {line!r}", line_number)

    start_raw, _, remainder = line.partition("-->")
    end_raw = remainder.strip().split(" ")[0]  # WebVTT allows trailing cue settings

    start_ms = parse_timecode(start_raw, line_number)
    end_ms = parse_timecode(end_raw, line_number)
    return start_ms, end_ms
