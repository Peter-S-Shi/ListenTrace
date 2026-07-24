from __future__ import annotations

from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.infrastructure.subtitles.errors import SubtitleParseError
from listentrace.infrastructure.subtitles.text_normalize import normalize_cue_text
from listentrace.infrastructure.subtitles.timecode import parse_cue_timing_line

_SKIPPED_BLOCK_PREFIXES = ("NOTE", "STYLE", "REGION")


def parse_vtt(content: str) -> list[SubtitleCue]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or not lines[0].strip().startswith("WEBVTT"):
        raise SubtitleParseError("file does not start with a WEBVTT header", 1)

    cues: list[SubtitleCue] = []
    i = 1
    n = len(lines)
    auto_index = 0

    while i < n:
        stripped = lines[i].strip()

        if stripped == "":
            i += 1
            continue

        if stripped.startswith(_SKIPPED_BLOCK_PREFIXES):
            while i < n and lines[i].strip() != "":
                i += 1
            continue

        if "-->" in stripped:
            timing_line = stripped
            timing_line_number = i + 1
        else:
            identifier_line_number = i + 1
            i += 1
            if i >= n:
                raise SubtitleParseError("cue is missing a timing line", identifier_line_number)
            timing_line = lines[i].strip()
            timing_line_number = i + 1

        start_ms, end_ms = parse_cue_timing_line(timing_line, timing_line_number)
        i += 1

        text_lines: list[str] = []
        while i < n and lines[i].strip() != "":
            text_lines.append(lines[i])
            i += 1

        if not text_lines:
            raise SubtitleParseError("cue has no text", timing_line_number)

        auto_index += 1
        raw_text = "\n".join(text_lines).strip()
        try:
            cue = SubtitleCue(
                cue_index=auto_index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=raw_text,
                normalized_text=normalize_cue_text(raw_text),
            )
        except ValueError as exc:
            raise SubtitleParseError(str(exc), timing_line_number) from exc
        cues.append(cue)

    return cues
