from __future__ import annotations

import struct
import wave
from datetime import datetime, timedelta

import pytest

from listentrace.application.services import practice_session_service as svc
from listentrace.application.services.material_import_service import import_material
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.time_display import format_local_timestamp
from listentrace.ui.windows.session_history_dialog import SessionHistoryDialog


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=1, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def test_session_history_shows_local_time_not_raw_utc(qapp, conn, tmp_path):
    """M12 Round 3 Time Contract (m08-02, W7): history rows must display local
    time, not the raw stored UTC string."""
    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")
    result = import_material(conn, media, subtitle, "Lesson")
    session = svc.start_session(conn, result.material_id)

    dialog = SessionHistoryDialog(conn, result.material_id, "Lesson")
    assert dialog._list.count() == 1
    label_text = dialog._list.item(0).text()

    stored_started_at = svc.get_session(conn, session.id).started_at
    assert format_local_timestamp(stored_started_at) in label_text

    local_offset = datetime.now().astimezone().utcoffset()
    if local_offset != timedelta(0):
        raw_utc_minute_precision = stored_started_at[:16]  # "YYYY-MM-DD HH:MM"
        assert raw_utc_minute_precision not in label_text, (
            "the raw UTC clock time must not appear verbatim -- it must be "
            "converted to local time first"
        )
    dialog.close()
