from __future__ import annotations

from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.infrastructure.subtitles.errors import SubtitleParseError
from listentrace.infrastructure.subtitles.text_normalize import normalize_cue_text
from listentrace.infrastructure.subtitles.timecode import parse_cue_timing_line


def parse_srt(content: str) -> list[SubtitleCue]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[SubtitleCue] = []
    i = 0
    n = len(lines)

    while i < n:
        if lines[i].strip() == "":
            i += 1
            continue

        index_line_number = i + 1
        index_text = lines[i].strip()
        if not index_text.isdigit():
            raise SubtitleParseError(f"expected numeric cue index, got {index_text!r}", index_line_number)
        cue_index = int(index_text)
        i += 1

        if i >= n:
            raise SubtitleParseError("cue is missing a timing line", index_line_number)
        timing_line_number = i + 1
        start_ms, end_ms = parse_cue_timing_line(lines[i].strip(), timing_line_number)
        i += 1

        text_lines: list[str] = []
        while i < n and lines[i].strip() != "":
            text_lines.append(lines[i])
            i += 1

        if not text_lines:
            raise SubtitleParseError("cue has no text", timing_line_number)

        raw_text = "\n".join(text_lines).strip()
        try:
            cue = SubtitleCue(
                cue_index=cue_index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=raw_text,
                normalized_text=normalize_cue_text(raw_text),
            )
        except ValueError as exc:
            raise SubtitleParseError(str(exc), timing_line_number) from exc
        cues.append(cue)

    return cues
