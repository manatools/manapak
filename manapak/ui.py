"""UI layer for manapak Flatpak updater."""

from __future__ import annotations

import gettext
from html import escape
import logging
import queue
import threading
from typing import Iterable, List, Set

import manatools.aui.yui as MUI
from manatools.ui import basedialog
from manatools.ui import common as ui_common
from manatools.ui import helpdialog

from .flatpak_api import FlatpakAPIError, FlatpakAppDetails, FlatpakAppInfo, FlatpakManager
from .helpinfo import ManapakHelpInfo


_ = gettext.gettext
logger = logging.getLogger("manapak.ui")


class ApplicationInformationDialog(basedialog.BaseDialog):
    """Modal, close-safe dialog used for one application's Flatpak metadata."""

    def __init__(self, markup: str) -> None:
        super().__init__(
            title=_("Application information"),
            icon="manapak",
            dialogType=basedialog.DialogType.POPUP,
            minWidth=720,
            minHeight=300,
        )
        self._markup = markup

    def UIlayout(self, layout):
        text = self.factory.createRichText(layout, "", plainTextMode=False)
        text.setValue(self._markup)
        text.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        text.setStretchable(MUI.YUIDimension.YD_VERT, True)

        button_row = self.factory.createHBox(layout)
        self.factory.createHStretch(button_row)
        close_button = self.factory.createIconButton(button_row, "window-close", _("&Close"))
        close_button.setHelpText(_("Close only the information dialog and return to manapak."))
        self.eventManager.addWidgetEvent(close_button, self._close)
        self.eventManager.addCancelEvent(self._close)
        self.dialog.setDefaultButton(close_button)

    def _close(self):
        self.ExitLoop()


class ManapakDialog(basedialog.BaseDialog):
    """Main app dialog."""

    def __init__(self, use_system_installation: bool = True) -> None:
        super().__init__(
            title=_("manapak - Flatpak updates"),
            icon="manapak",
            dialogType=basedialog.DialogType.MAIN,
            minWidth=860,
            minHeight=480,
        )
        self.timeout = 200
        self._manager = FlatpakManager(use_system_installation=use_system_installation)
        self._queue: "queue.Queue[dict]" = queue.Queue()
        self._stop_event = threading.Event()
        self._threads: set[threading.Thread] = set()
        self._pending_tasks = 0
        self._current_rows: List[FlatpakAppInfo] = []
        self._installed_rows: List[FlatpakAppInfo] = []
        self._update_rows: List[FlatpakAppInfo] = []
        self._update_ids: Set[str] = set()
        self._show_updates_only = True

        self._check_button = None
        self._update_button = None
        self._apps_table = None
        self._log_view = None
        self._view_mode_combo = None
        self._context_update_item = None
        self._context_information_item = None
        self._reported_errors: Set[str] = set()

    def UIlayout(self, layout):
        self.factory.createVSpacing(layout, 4)

        main_pane = self.factory.createPaned(layout, MUI.YUIDimension.YD_VERT)
        main_pane.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        main_pane.setStretchable(MUI.YUIDimension.YD_VERT, True)

        sources_box = self.factory.createVBox(main_pane)
        sources_box.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        sources_box.setStretchable(MUI.YUIDimension.YD_VERT, True)
        sources_box.setWeight(MUI.YUIDimension.YD_VERT, 40)

        filter_row = self.factory.createHBox(sources_box)
        self.factory.createLabel(filter_row, _("View"))
        self.factory.createHSpacing(filter_row, 8)
        self._view_mode_combo = self.factory.createComboBox(filter_row, "")
        self._view_mode_combo.setNotify(True)
        self._view_mode_combo.addItems(
            [
                MUI.YItem(_("Only updates"), True),
                MUI.YItem(_("All applications"), False),
            ]
        )
        self._view_mode_combo.setHelpText(_("Choose whether to show only applications with updates or the full installed catalog."))
        self.eventManager.addWidgetEvent(self._view_mode_combo, self._on_view_mode_changed)
        self.factory.createHStretch(filter_row)

        self.factory.createVSpacing(sources_box, 4)
        header = MUI.YTableHeader()
        header.addColumn(_("App ID"))
        header.addColumn(_("Current Version"))
        header.addColumn(_("Branch"))
        header.addColumn(_("Update available"))
        self._apps_table = self.factory.createTable(sources_box, header, multiSelection=False)
        self._apps_table.setNotify(True)
        self._apps_table.setNotifyContextMenu(True)
        self.eventManager.addWidgetEvent(self._apps_table, self._on_table_event)
        self._build_context_menu()

        log_box = self.factory.createVBox(main_pane)
        log_box.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        log_box.setStretchable(MUI.YUIDimension.YD_VERT, True)
        log_box.setWeight(MUI.YUIDimension.YD_VERT, 60)

        self._status_label = self.factory.createLabel(log_box, _("Idle"))
        self._progress_bar = self.factory.createProgressBar(log_box, _("Operation progress"))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)

        self.factory.createVSpacing(log_box, 6)
        self._log_view = self.factory.createLogView(
            log_box,
            _("Operation log"),
            visibleLines=8,
            storedLines=300,
            focus=MUI.YLogViewFocus.TAIL,
        )

        action_row = self.factory.createHBox(layout)
        action_row.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        self.factory.createHStretch(action_row)
        help_button = self.factory.createIconButton(action_row, "help-browser", _("&Help"))
        help_button.setHelpText(_("Open usage, update and privilege documentation."))
        about_button = self.factory.createIconButton(action_row, "help-about", _("&About"))
        about_button.setHelpText(_("Show application version, license and project information."))
        self._check_button = self.factory.createIconButton(action_row, "view-refresh", _("Check &Updates"))
        self._check_button.setHelpText(_("Refresh the update catalog from Flatpak remotes."))
        self._update_button = self.factory.createIconButton(action_row, "system-software-update", _("Update &All"))
        self._update_button.setHelpText(_("Update all applications that are currently marked as updatable."))
        self._update_button.setEnabled(False)
        close_button = self.factory.createIconButton(action_row, "application-exit", _("&Close"))
        close_button.setHelpText(_("Close the application. Background threads are stopped gracefully."))

        self.eventManager.addWidgetEvent(help_button, self._on_help)
        self.eventManager.addWidgetEvent(about_button, self._on_about)
        self.eventManager.addWidgetEvent(self._check_button, self._on_check_updates)
        self.eventManager.addWidgetEvent(self._update_button, self._on_update_selected)
        self.eventManager.addWidgetEvent(close_button, self._on_close)
        self.eventManager.addCancelEvent(self._on_close)
        self.eventManager.addTimeOutEvent(self._on_timeout)

        self._append_log(_("Application started. Loading Flatpak updates..."))
        self._run_background("refresh_catalog", self._worker_refresh_catalog)

    def _on_check_updates(self):
        self._run_background("refresh_catalog", self._worker_refresh_catalog)

    def _on_help(self):
        try:
            dialog = helpdialog.HelpDialog(
                ManapakHelpInfo(),
                minWidth=640,
                minHeight=320,
            )
            dialog.run()
        except Exception:
            logger.exception("Unable to open Help dialog")
            self._show_error(_("Unable to open Help. See the application log for details."))

    def _on_about(self):
        try:
            ui_common.AboutDialog(
                dialog_mode=ui_common.AboutDialogMode.TABBED,
                size={"width": 640, "height": 360},
            )
        except Exception:
            logger.exception("Unable to open About dialog")
            self._show_error(_("Unable to open About. See the application log for details."))

    def _on_update_selected(self):
        app_ids = self._collect_update_targets()
        if not app_ids:
            ui_common.infoMsgBox({"title": _("No updates available"), "text": _("There are no applications with updates available right now.")})
            return
        self._run_background("update_selected", self._worker_update_selected, app_ids)

    def _on_table_event(self, event=None):
        if event is None:
            return
        reason = event.reason() if hasattr(event, "reason") else None
        if reason == MUI.YEventReason.SelectionChanged:
            self._update_button_state()
            return
        if reason != MUI.YEventReason.ContextMenuActivated:
            return
        selected_id = self._selected_app_id()
        can_update = bool(selected_id and selected_id in self._update_ids and self._pending_tasks == 0)
        self._context_update_item.setEnabled(can_update)
        self._context_information_item.setEnabled(bool(selected_id) and self._pending_tasks == 0)
        app = MUI.YUI.app()
        app.openContextMenu(self._context_menu)

    def _on_context_update(self):
        app_id = self._selected_app_id()
        if not app_id or app_id not in self._update_ids:
            ui_common.infoMsgBox({"title": _("No update for selected app"), "text": _("The selected application has no available update.")})
            return
        self._run_background("update_selected", self._worker_update_selected, [app_id])

    def _on_context_information(self):
        app_id = self._selected_app_id()
        if not app_id:
            return
        self._run_background("load_app_details", self._worker_load_app_details, app_id)

    def _on_view_mode_changed(self):
        self._show_updates_only = self._selected_view_mode() == "updates"
        self._apply_current_view()

    def _on_timeout(self, owner=None, event=None):
        self._drain_queue()

    def _on_close(self):
        self._stop_background_threads()
        self.ExitLoop()

    def _run_background(self, task_name: str, handler, *handler_args):
        if self._stop_event.is_set():
            return
        thread = threading.Thread(
            target=self._thread_entry,
            args=(task_name, handler, handler_args),
            name=f"manapak-{task_name}",
            daemon=True,
        )
        self._pending_tasks += 1
        self._set_busy(True)
        self._threads.add(thread)
        thread.start()

    def _thread_entry(self, task_name: str, handler, handler_args):
        try:
            handler(*handler_args)
        except FlatpakAPIError as exc:
            logger.error("%s failed: %s", task_name, exc)
            self._queue.put({"type": "error", "message": str(exc)})
        except Exception as exc:
            logger.exception("Unexpected error in task %s", task_name)
            self._queue.put({"type": "error", "message": str(exc)})
        finally:
            self._queue.put({"type": "done", "task": task_name, "thread_name": threading.current_thread().name})

    def _worker_refresh_catalog(self):
        apps = self._manager.get_installed_apps()
        updates = self._manager.check_updates()
        self._queue.put(
            {
                "type": "catalog_data",
                "installed_apps": apps,
                "update_apps": updates,
                "message": _("Available updates: %(count)d") % {"count": len(updates)},
            }
        )

    def _worker_update_selected(self, app_ids: Iterable[str]):
        for app_id in app_ids:
            if self._stop_event.is_set():
                return
            self._queue.put({"type": "log", "message": _("Updating %(app)s...") % {"app": app_id}})
            self._manager.update_app(
                app_id,
                status_callback=lambda phase, percent, message: self._queue.put(
                    {"type": "progress", "phase": phase, "percent": percent, "message": message}
                ),
            )
            self._queue.put({"type": "log", "message": _("Update completed for %(app)s.") % {"app": app_id}})
        self._queue.put({"type": "log", "message": _("Refreshing updates list...")})
        self._worker_refresh_catalog()

    def _worker_load_app_details(self, app_id: str):
        details = self._manager.get_app_details(app_id)
        self._queue.put({"type": "app_details", "details": details})

    def _drain_queue(self):
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break

            event_type = item.get("type")
            if event_type == "log":
                self._append_log(item["message"])
            elif event_type == "catalog_data":
                self._installed_rows = list(item["installed_apps"])
                self._update_rows = list(item["update_apps"])
                self._update_ids = {app.app_id for app in self._update_rows}
                self._apply_current_view()
                self._append_log(item["message"])
                if not self._update_rows:
                    self._append_log(_("No updates available."))
            elif event_type == "error":
                message = item.get("message", _("Unknown error"))
                self._append_log(_("Error: %(error)s") % {"error": message})
                self._set_progress(0, _("Error"), message)
                self._show_error_once(message, title=_("Flatpak error"))
            elif event_type == "progress":
                phase = item.get("phase", "progress")
                percent = int(item.get("percent", 0))
                message = item.get("message", "")
                self._set_progress(percent, phase, message)
            elif event_type == "app_details":
                self._show_app_information(item["details"])
            elif event_type == "done":
                self._pending_tasks = max(0, self._pending_tasks - 1)
                self._threads = {t for t in self._threads if t.is_alive()}
                if self._pending_tasks == 0:
                    self._set_busy(False)
                    self._set_progress(0, _("Idle"), _("Ready"))

        self._update_button_state()

    def _apply_current_view(self):
        self._current_rows = list(self._update_rows if self._show_updates_only else self._installed_rows)
        self._fill_table(self._current_rows)
        self._update_button_state()

    def _build_context_menu(self):
        self._context_menu = MUI.YMenuItem("context", is_menu=True)
        self._context_update_item = self._context_menu.addItem(_("Update"), icon_name="system-software-update")
        self._context_information_item = self._context_menu.addItem(_("Information"), icon_name="dialog-information")
        self.eventManager.addMenuEvent(self._context_update_item, self._on_context_update)
        self.eventManager.addMenuEvent(self._context_information_item, self._on_context_information)

    def _show_app_information(self, details: FlatpakAppDetails):
        dialog = ApplicationInformationDialog(self._format_app_information(details))
        dialog.run()

    @staticmethod
    def _format_app_information(details: FlatpakAppDetails) -> str:
        fields = [
            (_("Application"), details.app_id),
            (_("Installed version"), details.installed_version),
            (_("Branch"), details.branch),
            (_("Architecture"), details.arch),
            (_("Origin"), details.origin),
            (_("Runtime"), details.runtime),
            (_("SDK"), details.sdk),
            (_("Base app"), details.base),
            (_("Installed commit"), details.installed_commit),
            (_("Available commit"), details.available_commit),
            (_("Update available"), _("Yes") if details.update_available else _("No")),
        ]
        rows = "".join(
            f"<p><b>{escape(label)}:</b> {escape(str(value).strip() or 'n/a')}</p>"
            for label, value in fields
        )
        return f"<div>{rows}</div>"

    def _fill_table(self, rows: List[FlatpakAppInfo]):
        self._apps_table.deleteAllItems()
        for app in rows:
            row = MUI.YTableItem()
            row.addCells(app.app_id, app.current_version, app.branch, self._updatable_text(app.app_id))
            self._apps_table.addItem(row)

    def _selected_app_ids(self) -> List[str]:
        app_id = self._selected_app_id()
        return [app_id] if app_id else []

    def _selected_app_id(self) -> str:
        selected = self._apps_table.selectedItem() if self._apps_table is not None else None
        if selected is None:
            return ""
        app_id = selected.label(0) if hasattr(selected, "label") else ""
        return app_id or ""

    def _selected_updatable_app_ids(self) -> List[str]:
        return [app_id for app_id in self._selected_app_ids() if app_id in self._update_ids]

    def _collect_update_targets(self) -> List[str]:
        return sorted(self._update_ids)

    def _updatable_text(self, app_id: str) -> str:
        return _("Yes") if app_id in self._update_ids else _("No")

    def _selected_view_mode(self) -> str:
        selected = self._view_mode_combo.selectedItem() if self._view_mode_combo is not None else None
        if selected is None:
            return "updates"
        label = ""
        if hasattr(selected, "label"):
            value = selected.label
            label = value() if callable(value) else str(value)
        return "all" if label == _("All applications") else "updates"

    def _update_button_state(self):
        has_selection = bool(self._collect_update_targets())
        has_pending = self._pending_tasks > 0
        self._update_button.setEnabled(has_selection and not has_pending)

    def _set_busy(self, busy: bool):
        self._check_button.setEnabled(not busy)
        self._update_button.setEnabled(not busy and bool(self._collect_update_targets()))

    def _set_progress(self, value: int, phase: str, message: str):
        if self._progress_bar is None:
            return
        progress_value = max(0, min(100, int(value)))
        self._progress_bar.setValue(progress_value)
        self._progress_bar.setVisible(progress_value > 0 or phase not in ("Idle", "done"))
        self._status_label.setValue(f"{phase}: {message}" if message else phase)
        if not message and phase == "Idle":
            self._status_label.setValue(_("Idle"))

    def _append_log(self, line: str):
        self._log_view.appendLines(line)

    def _show_error(self, message: str):
        self._show_error_once(message, title=_("manapak error"))

    def _show_error_once(self, message: str, title=None):
        if message in self._reported_errors:
            return
        self._reported_errors.add(message)
        ui_common.warningMsgBox(
            {
                "title": title or _("manapak error"),
                "text": message,
                "size": {"width": 560, "height": 220},
            }
        )

    def _stop_background_threads(self):
        self._stop_event.set()
        self._manager.cancel_operations()
        for thread in list(self._threads):
            thread.join(timeout=0.25)
            if thread.is_alive():
                logger.warning("Background thread %s did not stop within the close timeout", thread.name)
        self._threads.clear()
