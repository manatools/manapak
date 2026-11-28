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
    def __init__(self, app_id: str, kind: int = 0, partial: bool = False):
        self._app_id = app_id
        self._kind = kind
        self._partial = partial

    def get_name(self):
        return self._app_id

    def get_kind(self):
        return self._kind

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

    def get_is_partial(self):
        return self._partial

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
    def __init__(self, refs, remotes=None):
        self.refs = refs
        self.remotes = remotes or []
        self.refreshed = []

    def list_installed_refs_for_update(self, cancellable=None):
        return self.refs

    def list_installed_refs(self, cancellable=None):
        return self.refs

    def fetch_remote_ref_sync(self, origin, kind, name, arch, branch, cancellable=None):
        return SimpleNamespace(get_commit=lambda: "available-commit")

    def list_remotes(self):
        return [SimpleNamespace(get_name=lambda remote=remote: remote) for remote in self.remotes]

    def update_remote_sync(self, remote_name, cancellable=None):
        self.refreshed.append(remote_name)
        return True


def test_update_app_uses_formatted_ref(monkeypatch):
    fake_ref = FakeRef("com.example.App")
    fake_tx = FakeTransaction()

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

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


def test_get_installed_apps_includes_apps_and_runtimes(monkeypatch):
    app_ref = FakeRef("org.example.App")
    runtime_ref = FakeRef("org.example.Platform", kind=1)

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

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

    assert [app.app_id for app in apps] == ["org.example.App", "org.example.Platform"]


def test_update_app_reports_progress_callback(monkeypatch):
    fake_ref = FakeRef("com.example.App")
    fake_tx = FakeTransaction()

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

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
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

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
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

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


def test_check_updates_includes_runtime_refs(monkeypatch):
    app_ref = FakeRef("org.example.App", kind=0)
    runtime_ref = FakeRef("org.gnome.Platform.Locale", kind=1)
    installation = FakeInstallation([app_ref, runtime_ref], remotes=["flathub"])

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

        class Installation:
            @staticmethod
            def new_user(cancellable=None):
                return installation

            @staticmethod
            def new_system(cancellable=None):
                return installation

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=False)
    updates = manager.check_updates()

    assert [item.app_id for item in updates] == ["org.example.App", "org.gnome.Platform.Locale"]


def test_check_updates_reads_system_installation_updates(monkeypatch):
    user_installation = FakeInstallation([])
    system_installation = FakeInstallation([FakeRef("org.freedesktop.Platform", kind=1)], remotes=["flathub"])

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

        class Installation:
            @staticmethod
            def new_user(cancellable=None):
                return user_installation

            @staticmethod
            def new_system(cancellable=None):
                return system_installation

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=False)
    updates = manager.check_updates()

    assert [item.app_id for item in updates] == ["org.freedesktop.Platform"]


def test_check_updates_refreshes_remote_metadata_when_cache_is_stale(monkeypatch):
    installation = FakeInstallation([FakeRef("org.example.App")], remotes=["flathub"])

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

        class Installation:
            @staticmethod
            def new_user(cancellable=None):
                return installation

            @staticmethod
            def new_system(cancellable=None):
                return installation

    import manapak.flatpak_api as flatpak_api

    times = iter([100.0, 101.0, 200.0])
    monkeypatch.setattr(flatpak_api, "time", SimpleNamespace(monotonic=lambda: next(times)))
    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=False)
    manager._remote_refresh_interval = 30.0
    manager.check_updates()
    manager.check_updates()
    manager.check_updates()

    assert installation.refreshed == ["flathub", "flathub", "flathub", "flathub"]


def test_check_updates_exposes_runtime_partial_and_scope(monkeypatch):
    locale_ref = FakeRef("org.gnome.Platform.Locale", kind=1, partial=True)
    gl_ref = FakeRef("org.freedesktop.Platform.GL.default", kind=1)
    installation = FakeInstallation([locale_ref, gl_ref], remotes=["flathub"])

    class FakeFlatpak:
        RefKind = SimpleNamespace(APP=0, RUNTIME=1)

        class Installation:
            @staticmethod
            def new_system(cancellable=None):
                return installation

            @staticmethod
            def new_user(cancellable=None):
                return FakeInstallation([])

    import manapak.flatpak_api as flatpak_api

    monkeypatch.setattr(flatpak_api, "Flatpak", FakeFlatpak)
    monkeypatch.setattr(flatpak_api, "GLib", SimpleNamespace(Error=RuntimeError))
    monkeypatch.setattr(flatpak_api, "_FLATPAK_IMPORT_ERROR", None)

    manager = FlatpakManager(use_system_installation=True)
    updates = manager.check_updates()

    locale = next(item for item in updates if item.app_id == "org.gnome.Platform.Locale")
    gl = next(item for item in updates if item.app_id == "org.freedesktop.Platform.GL.default")
    assert locale.ref_type == "runtime"
    assert locale.partial is True
    assert locale.scope == "system"
    assert gl.ref_type == "runtime"
    assert gl.partial is False
