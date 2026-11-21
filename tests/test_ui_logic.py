# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
manapak is a desktop application for checking and applying Flatpak updates based on ManaTools AUI python

License: GPLv3

Author:  Angelo Naselli <anaselli@linux.it>

@package manapak
'''
from __future__ import annotations

import manapak.ui as ui_module
from manapak.flatpak_api import FlatpakAppDetails
from manapak.ui import ApplicationInformationDialog, ManapakDialog


class _FakeItem:
    def __init__(self, text: str):
        self._text = text

    def label(self):
        return self._text


class _FakeCombo:
    def __init__(self, text: str):
        self._item = _FakeItem(text)

    def selectedItem(self):
        return self._item


class _FakeRow:
    def __init__(self, app_id: str):
        self._app_id = app_id

    def label(self, index: int):
        return self._app_id if index == 0 else ""


class _FakeTable:
    def __init__(self, app_id: str | None):
        self._row = _FakeRow(app_id) if app_id else None

    def selectedItem(self):
        return self._row


def test_selected_updatable_app_ids_filters_non_updatable():
    dialog = object.__new__(ManapakDialog)
    dialog._update_ids = {"org.example.One", "org.example.Three"}
    dialog._selected_app_ids = lambda: ["org.example.One", "org.example.Two"]

    assert dialog._selected_updatable_app_ids() == ["org.example.One"]


def test_selected_view_mode_reads_combo_label():
    dialog = object.__new__(ManapakDialog)
    dialog._view_mode_combo = _FakeCombo(ui_module._("All applications"))

    assert dialog._selected_view_mode() == "all"


def test_updatable_text_depends_on_update_set():
    dialog = object.__new__(ManapakDialog)
    dialog._update_ids = {"org.example.One"}

    assert dialog._updatable_text("org.example.One") == ui_module._("Yes")
    assert dialog._updatable_text("org.example.Two") == ui_module._("No")


def test_collect_update_targets_sorted():
    dialog = object.__new__(ManapakDialog)
    dialog._update_ids = {"org.example.B", "org.example.A"}

    assert dialog._collect_update_targets() == ["org.example.A", "org.example.B"]


def test_selected_app_id_reads_current_table_row():
    dialog = object.__new__(ManapakDialog)
    dialog._apps_table = _FakeTable("org.example.App")

    assert dialog._selected_app_id() == "org.example.App"


def test_format_app_information_uses_safe_readable_markup():
    details = FlatpakAppDetails(
        app_id="org.example.<App>",
        installed_version="1.0",
        branch="stable",
        arch="x86_64",
        origin="flathub",
        runtime="org.freedesktop.Platform/x86_64/26.08",
        sdk="org.freedesktop.Sdk/x86_64/26.08",
        base="n/a",
        installed_commit="old-commit",
        available_commit="new-commit",
        update_available=True,
    )

    markup = ManapakDialog._format_app_information(details)

    assert "<p><b>" in markup
    assert "org.example.&lt;App&gt;" in markup
    assert "org.freedesktop.Platform/x86_64/26.08" in markup


def test_information_dialog_close_only_exits_popup_loop():
    dialog = object.__new__(ApplicationInformationDialog)
    called = []
    dialog.ExitLoop = lambda: called.append("closed")

    dialog._close()

    assert called == ["closed"]


def test_show_error_once_suppresses_duplicate_popups(monkeypatch):
    dialog = object.__new__(ManapakDialog)
    dialog._reported_errors = set()
    calls = []
    monkeypatch.setattr(ui_module.ui_common, "warningMsgBox", lambda info: calls.append(info))

    dialog._show_error_once("same failure")
    dialog._show_error_once("same failure")

    assert len(calls) == 1
