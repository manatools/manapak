# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
manapak is a desktop application for checking and applying Flatpak updates based on ManaTools AUI python

License: GPLv3

Author:  Angelo Naselli <anaselli@linux.it>

@package manapak
'''
from __future__ import annotations

from types import SimpleNamespace

import pytest

from manapak.flatpak_api import FlatpakAPIError, FlatpakManager


class FakeRef:
    def __init__(self, app_id: str):
        self._app_id = app_id

    def get_name(self):
        return self._app_id

    def get_kind(self):
        return 0

    def get_branch(self):
        return "stable"

    def get_arch(self):
        return "x86_64"

    def get_origin(self):
        return "flathub"

    def get_appdata_version(self):
        return "1.2.3"

    def get_commit(self):
        return "installed-commit"

    def load_metadata(self, cancellable=None):
        return SimpleNamespace(
            get_data=lambda: (
                f"[Application]\n"
                f"name={self._app_id}\n"
                "runtime=org.freedesktop.Platform/x86_64/25.08\n"
                "sdk=org.freedesktop.Sdk/x86_64/25.08\n"
                "base=app/org.example.BaseApp/x86_64/25.08\n"
            ).encode("utf-8")
        )

    def format_ref(self):
        return f"app/{self._app_id}/x86_64/stable"


class FakeTransaction:
    def __init__(self):
        self.calls = []

    def add_update(self, ref, subpaths=None, commit=None):
        self.calls.append((ref, subpaths, commit))
        return True

    def run(self, cancellable=None):
        return True


class FakeInstallation:
    def __init__(self, refs):
        self.refs = refs

    def list_installed_refs_for_update(self, cancellable=None):
        return self.refs

    def list_installed_refs(self, cancellable=None):
        return self.refs

    def fetch_remote_ref_sync(self, origin, kind, name, arch, branch, cancellable=None):
        return SimpleNamespace(get_commit=lambda: "available-commit")


def test_update_app_uses_formatted_ref(monkeypatch):
    fake_ref = FakeRef("com.example.App")
    fake_tx = FakeTransaction()

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0)

        class Installation:
            @staticmethod
            def new_user(cancellable=None):
                return FakeInstallation([fake_ref])

            @staticmethod
            def new_system(cancellable=None):
                return FakeInstallation([fake_ref])

        class Transaction:
            @staticmethod
            def new_for_installation(installation, cancellable=None):
                return fake_tx

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=False)
    manager.update_app("com.example.App")

    assert fake_tx.calls == [("app/com.example.App/x86_64/stable", None, None)]


def test_get_installed_apps_filters_non_apps(monkeypatch):
    app_ref = FakeRef("org.example.App")
    class FakeRuntimeRef:
        def get_name(self):
            return "org.example.Platform"

        def get_kind(self):
            return 1

        def get_branch(self):
            return "stable"

        def get_arch(self):
            return "x86_64"

        def get_origin(self):
            return "flathub"

        def get_appdata_version(self):
            return "1.2.3"

    runtime_ref = FakeRuntimeRef()

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0)

        class Installation:
            @staticmethod
            def new_user(cancellable=None):
                return FakeInstallation([app_ref, runtime_ref])

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=False)
    apps = manager.get_installed_apps()

    assert [app.app_id for app in apps] == ["org.example.App"]


def test_update_app_reports_progress_callback(monkeypatch):
    fake_ref = FakeRef("com.example.App")
    fake_tx = FakeTransaction()

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0)

        class Installation:
            @staticmethod
            def new_user(cancellable=None):
                return FakeInstallation([fake_ref])

            @staticmethod
            def new_system(cancellable=None):
                return FakeInstallation([fake_ref])

        class Transaction:
            @staticmethod
            def new_for_installation(installation, cancellable=None):
                return fake_tx

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    events = []
    manager = FlatpakManager(use_system_installation=False)
    manager.update_app("com.example.App", status_callback=lambda phase, percent, message: events.append((phase, percent, message)))

    assert ("done", 100, "Update completed for com.example.App.") in events


def test_get_installation_rewraps_polkit_permission_error(monkeypatch):
    class FakeGLibError(RuntimeError):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

    class FakeFlatpak:
        class Installation:
            @staticmethod
            def new_system(cancellable=None):
                raise FakeGLibError("Not authorized")

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=FakeGLibError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=True)
    with pytest.raises(FlatpakAPIError, match="Polkit|authorized"):
        manager.get_installation()


def test_get_app_details_includes_runtime_and_available_commit(monkeypatch):
    fake_ref = FakeRef("com.example.App")
    installation = FakeInstallation([fake_ref])

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0)

        class Installation:
            pass

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=False)
    monkeypatch.setattr(manager, "get_installations", lambda: [installation])

    details = manager.get_app_details("com.example.App")

    assert details.runtime == "org.freedesktop.Platform/x86_64/25.08"
    assert details.sdk == "org.freedesktop.Sdk/x86_64/25.08"
    assert details.base == "app/org.example.BaseApp/x86_64/25.08"
    assert details.available_commit == "available-commit"
    assert details.update_available is True


def test_get_installations_caches_discovery(monkeypatch):
    calls = {"system": 0, "user": 0}
    installation = FakeInstallation([])

    class FakeFlatpak:
        class Installation:
            @staticmethod
            def new_system(cancellable=None):
                calls["system"] += 1
                return installation

            @staticmethod
            def new_user(cancellable=None):
                calls["user"] += 1
                return installation

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager()
    assert manager.get_installations() == [installation, installation]
    assert manager.get_installations() == [installation, installation]
    assert calls == {"system": 1, "user": 1}


def test_cancel_operations_cancels_active_cancellables():
    manager = FlatpakManager()
    cancelled = []
    class FakeCancellable:
        def cancel(self):
            cancelled.append(True)

    cancellable = FakeCancellable()
    manager._cancellables.add(cancellable)

    manager.cancel_operations()

    assert cancelled == [True]
