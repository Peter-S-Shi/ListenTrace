from __future__ import annotations

from pathlib import Path

import pytest

from listentrace.infrastructure.subtitles.errors import SubtitleParseError
from listentrace.infrastructure.subtitles.loader import parse_subtitle_file
from listentrace.infrastructure.subtitles.srt_parser import parse_srt
from listentrace.infrastructure.subtitles.vtt_parser import parse_vtt

FIXTURES = Path(__file__).parent.parent / "fixtures" / "subtitles"


def test_parse_srt_produces_normalized_cues():
    cues = parse_srt((FIXTURES / "sample.srt").read_text(encoding="utf-8"))

    assert len(cues) == 2
    assert cues[0].cue_index == 1
    assert cues[0].start_ms == 0
    assert cues[0].end_ms == 2500
    assert cues[0].text == "Bonjour tout le monde"

    assert cues[1].start_ms == 2500
    assert cues[1].end_ms == 5000
    assert cues[1].text == "Comment <i>ça va</i> ?"
    assert cues[1].normalized_text == "Comment ça va ?"


def test_parse_vtt_produces_normalized_cues():
    cues = parse_vtt((FIXTURES / "sample.vtt").read_text(encoding="utf-8"))

    assert len(cues) == 2
    assert cues[0].start_ms == 0
    assert cues[0].end_ms == 2500
    assert cues[0].text == "Bonjour tout le monde"
    assert cues[1].start_ms == 2500
    assert cues[1].end_ms == 5000


def test_parse_srt_rejects_timing_going_backwards():
    with pytest.raises(SubtitleParseError):
        parse_srt((FIXTURES / "malformed_timing.srt").read_text(encoding="utf-8"))


def test_parse_srt_rejects_non_numeric_index():
    with pytest.raises(SubtitleParseError):
        parse_srt((FIXTURES / "malformed_index.srt").read_text(encoding="utf-8"))


def test_parse_vtt_rejects_missing_header():
    with pytest.raises(SubtitleParseError):
        parse_vtt((FIXTURES / "malformed_missing_header.vtt").read_text(encoding="utf-8"))


def test_loader_dispatches_by_extension():
    srt_cues = parse_subtitle_file(FIXTURES / "sample.srt")
    vtt_cues = parse_subtitle_file(FIXTURES / "sample.vtt")
    assert len(srt_cues) == 2
    assert len(vtt_cues) == 2


def test_loader_rejects_unsupported_extension(tmp_path):
    unsupported = tmp_path / "sample.txt"
    unsupported.write_text("plain transcript", encoding="utf-8")
    with pytest.raises(SubtitleParseError):
        parse_subtitle_file(unsupported)
