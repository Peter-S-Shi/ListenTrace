from __future__ import annotations

import sys
import types

from listentrace.infrastructure import windows_identity


def test_app_user_model_id_is_stable_product_only_identifier():
    assert windows_identity.APP_USER_MODEL_ID == "ListenTrace.Desktop"
    assert not any(ch.isdigit() for ch in windows_identity.APP_USER_MODEL_ID)


def test_set_windows_app_user_model_id_is_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    result = windows_identity.set_windows_app_user_model_id()
    assert result is False


def test_set_windows_app_user_model_id_requests_the_expected_value_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    calls = []
    fake_shell32 = types.SimpleNamespace(
        SetCurrentProcessExplicitAppUserModelID=lambda app_id: calls.append(app_id)
    )
    fake_windll = types.SimpleNamespace(shell32=fake_shell32)
    monkeypatch.setattr(windows_identity.ctypes, "windll", fake_windll, raising=False)

    result = windows_identity.set_windows_app_user_model_id()

    assert result is True
    assert calls == ["ListenTrace.Desktop"]


def test_set_windows_app_user_model_id_accepts_a_custom_id_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    calls = []
    fake_shell32 = types.SimpleNamespace(
        SetCurrentProcessExplicitAppUserModelID=lambda app_id: calls.append(app_id)
    )
    fake_windll = types.SimpleNamespace(shell32=fake_shell32)
    monkeypatch.setattr(windows_identity.ctypes, "windll", fake_windll, raising=False)

    windows_identity.set_windows_app_user_model_id("Custom.Id")

    assert calls == ["Custom.Id"]


def test_set_windows_app_user_model_id_swallows_shell_failure_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    def _raise(app_id):
        raise OSError("shell not available")

    fake_shell32 = types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=_raise)
    fake_windll = types.SimpleNamespace(shell32=fake_shell32)
    monkeypatch.setattr(windows_identity.ctypes, "windll", fake_windll, raising=False)

    result = windows_identity.set_windows_app_user_model_id()

    assert result is False
