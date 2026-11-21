from __future__ import annotations

import logging
from argparse import Namespace

import manapak.app as app_module
from manapak.app import _configure_logging


def _reset_root_logger():
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)


def test_configure_logging_to_file(tmp_path):
    _reset_root_logger()
    logfile = tmp_path / "manapak.log"
    args = Namespace(logging=False, debug=False, log_file=str(logfile))

    _configure_logging(args)
    logging.getLogger("manapak.test").info("test log line")

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert logfile.exists()
    assert "test log line" in logfile.read_text(encoding="utf-8")
    _reset_root_logger()


def test_configure_logging_debug_level_stream():
    _reset_root_logger()
    args = Namespace(logging=True, debug=True, log_file=None)

    _configure_logging(args)

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert root.handlers
    _reset_root_logger()


def test_main_reports_startup_failure(monkeypatch):
    class BrokenDialog:
        def __init__(self, **kwargs):
            raise RuntimeError("backend unavailable")

    reported = []
    monkeypatch.setattr(app_module, "ManapakDialog", BrokenDialog)
    monkeypatch.setattr(app_module, "_configure_application_metadata", lambda: None)
    monkeypatch.setattr(app_module.ui_common, "warningMsgBox", lambda info: reported.append(info))

    assert app_module.main(["--gtk"]) == 1
    assert reported
    assert "backend unavailable" in reported[0]["text"]
