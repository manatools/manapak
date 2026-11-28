# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
manapak is a desktop application for checking and applying Flatpak updates based on ManaTools AUI python

License: GPLv3

Author:  Angelo Naselli <anaselli@linux.it>

@package manapak
'''

from __future__ import annotations

import configparser
from dataclasses import dataclass
import logging
import threading
import time
from typing import List

try:
    import gi

    gi.require_version("Flatpak", "1.0")
    from gi.repository import Flatpak, Gio, GLib
except (ImportError, ValueError) as exc:
    gi = None
    Flatpak = None
    GLib = None
    Gio = None
    _FLATPAK_IMPORT_ERROR = exc
else:
    _FLATPAK_IMPORT_ERROR = None

logger = logging.getLogger("manapak.flatpak_api")


class FlatpakAPIError(RuntimeError):
    """Raised for functional Flatpak API failures."""


@dataclass(frozen=True)
class FlatpakAppInfo:
    app_id: str
    current_version: str
    branch: str
    arch: str
    origin: str


@dataclass(frozen=True)
class FlatpakAppDetails:
    app_id: str
    installed_version: str
    branch: str
    arch: str
    origin: str
    runtime: str
    sdk: str
    base: str
    installed_commit: str
    available_commit: str
    update_available: bool


class FlatpakManager:
    """Business logic wrapper around gi.repository.Flatpak."""

    def __init__(self, use_system_installation: bool = True) -> None:
        self.use_system_installation = use_system_installation
        self._installation = None
        self._installations = None
        self._cancellables = set()
        self._cancellables_lock = threading.Lock()
        self._last_remote_refresh_at = 0.0
        self._remote_refresh_interval = 300.0
        self._remote_refresh_lock = threading.Lock()

    @staticmethod
    def ensure_available() -> None:
        if Flatpak is None:
            raise FlatpakAPIError(
                "Flatpak Python bindings are not available. Install gir1.2-flatpak-1.0 (or distro equivalent)."
            ) from _FLATPAK_IMPORT_ERROR

    def get_installation(self):
        """Return the chosen Flatpak installation object.

        The app never shells out to ``pkexec``, ``sudo`` or ``flatpak`` commands.
        Instead it relies on the OS/Flatpak daemon to authorize access for the
        active user when a system installation requires elevated rights.
        """
        self.ensure_available()
        if self._installation is not None:
            return self._installation

        try:
            if self.use_system_installation:
                self._installation = Flatpak.Installation.new_system(None)
            else:
                self._installation = Flatpak.Installation.new_user(None)
        except TypeError:
            if self.use_system_installation:
                self._installation = Flatpak.Installation.new_system()
            else:
                self._installation = Flatpak.Installation.new_user()
        except GLib.Error as exc:
            scope = "system" if self.use_system_installation else "user"
            if self._is_privilege_error(exc):
                raise FlatpakAPIError(self._describe_privilege_error(scope)) from exc
            raise FlatpakAPIError(f"Cannot open Flatpak {scope} installation: {exc.message}") from exc
        return self._installation

    @staticmethod
    def _describe_privilege_error(scope: str) -> str:
        return (
            f"Flatpak {scope} installation requires Polkit authorization. "
            "Authenticate when prompted, or switch to a user installation. "
            "No shell-based escalation is used."
        )

    @staticmethod
    def _is_privilege_error(exc) -> bool:
        text = str(exc).lower()
        markers = (
            "not authorized",
            "permission denied",
            "access denied",
            "not permitted",
            "polkit",
            "org.freedesktop.policykit",
        )
        return any(marker in text for marker in markers)

    def get_installations(self):
        """Return all available installations for this system, in a deterministic order."""
        if self._installations is not None:
            return list(self._installations)

        installations = []
        factory_pairs = [
            ("system", self._safe_new_installation, "new_system"),
            ("user", self._safe_new_installation, "new_user"),
        ]
        for _, factory, method_name in factory_pairs:
            try:
                installation = factory(method_name)
            except Exception:
                logger.debug("Unable to create Flatpak installation %s", method_name, exc_info=True)
                continue
            if installation is not None:
                installations.append(installation)
        if not installations:
            installations.append(self.get_installation())
        self._installations = tuple(installations)
        return list(installations)

    def _safe_new_installation(self, method_name: str):
        factory = getattr(Flatpak.Installation, method_name, None)
        if factory is None:
            return None
        try:
            return factory(None)
        except TypeError:
            return factory()
        except GLib.Error:
            return None

    def get_remotes(self):
        """Return remote names visible from all active installations."""
        remotes = []
        for installation in self.get_installations():
            try:
                available = installation.list_remotes()
            except AttributeError:
                logger.debug("Flatpak installation lacks list_remotes()")
                continue
            except GLib.Error as exc:
                logger.warning("Unable to list Flatpak remotes: %s", exc.message)
                continue
            for remote in available or []:
                name = getattr(remote, "get_name", lambda: None)()
                if name:
                    remotes.append(name)
        return sorted(set(remotes))

    def get_installed_apps(self) -> List[FlatpakAppInfo]:
        refs = []
        for installation in self.get_installations():
            try:
                refs.extend(installation.list_installed_refs(None))
            except TypeError:
                refs.extend(installation.list_installed_refs())
            except GLib.Error as exc:
                raise FlatpakAPIError(f"Unable to list installed refs: {exc.message}") from exc
        return self._to_app_list(refs)

    def check_updates(self) -> List[FlatpakAppInfo]:
        self.refresh_remote_metadata_if_stale()
        refs = []
        for installation in self.get_installations():
            try:
                refs.extend(installation.list_installed_refs_for_update(None))
            except TypeError:
                refs.extend(installation.list_installed_refs_for_update())
            except GLib.Error as exc:
                raise FlatpakAPIError(f"Unable to check updates: {exc.message}") from exc
        return self._to_app_list(refs, include_runtimes=True)

    def refresh_remote_metadata_if_stale(self, force: bool = False) -> bool:
        now = time.monotonic()
        with self._remote_refresh_lock:
            if not force and (now - self._last_remote_refresh_at) < self._remote_refresh_interval:
                return False
            self._last_remote_refresh_at = now

        refreshed = False
        for installation in self.get_installations():
            remotes = self._list_installation_remotes(installation)
            if not remotes:
                continue
            updater = getattr(installation, "update_remote_sync", None)
            if not callable(updater):
                continue
            for remote_name in remotes:
                if not remote_name:
                    continue
                try:
                    updater(remote_name, None)
                except TypeError:
                    try:
                        updater(remote_name)
                    except (GLib.Error, TypeError) as exc:
                        logger.warning("Unable to refresh Flatpak remote metadata for %s: %s", remote_name, exc)
                        continue
                except GLib.Error as exc:
                    logger.warning("Unable to refresh Flatpak remote metadata for %s: %s", remote_name, exc.message)
                    continue
                refreshed = True
        return refreshed

    @staticmethod
    def _list_installation_remotes(installation) -> List[str]:
        try:
            remotes = installation.list_remotes()
        except AttributeError:
            logger.debug("Flatpak installation lacks list_remotes()")
            return []
        except GLib.Error as exc:
            logger.warning("Unable to list Flatpak remotes: %s", exc.message)
            return []
        names = []
        for remote in remotes or []:
            name = getattr(remote, "get_name", lambda: None)()
            if name:
                names.append(name)
        return names

    def get_app_details(self, app_id: str) -> FlatpakAppDetails:
        """Return installed and update metadata for one application."""
        update_ids = {app.app_id for app in self.check_updates()}
        requested = self._normalize_app_id(app_id)

        for installation in self.get_installations():
            try:
                refs = installation.list_installed_refs(None)
            except TypeError:
                refs = installation.list_installed_refs()
            except GLib.Error as exc:
                logger.warning("Unable to inspect installed refs for %s: %s", app_id, exc.message)
                continue

            for ref in refs:
                if not self._ref_kind_is_supported(ref) or self._normalize_app_id(self._ref_name(ref)) != requested:
                    continue

                metadata = self._load_ref_metadata(ref)
                available_commit = self._available_commit(installation, ref)
                return FlatpakAppDetails(
                    app_id=self._ref_name(ref),
                    installed_version=self._version(ref),
                    branch=self._safe_call(ref, "get_branch", ""),
                    arch=self._safe_call(ref, "get_arch", ""),
                    origin=self._safe_call(ref, "get_origin", ""),
                    runtime=metadata.get("runtime", metadata.get("name", "n/a")),
                    sdk=metadata.get("sdk", "n/a"),
                    base=metadata.get("base", "n/a"),
                    installed_commit=self._safe_call(ref, "get_commit", "n/a"),
                    available_commit=available_commit,
                    update_available=app_id in update_ids,
                )

        raise FlatpakAPIError(f"Installed Flatpak application not found: {app_id}.")

    def update_app(self, app_id: str, status_callback=None) -> None:
        """Apply an update for a single app while optionally reporting progress.

        The callback receives a ``(phase, percent, message)`` tuple, where phase
        is a short status label and percent is in the 0-100 range.
        """
        def emit(phase: str, percent: int, message: str) -> None:
            if status_callback is not None:
                status_callback(phase, percent, message)

        emit("resolve", 5, f"Resolving Flatpak installation for {app_id}...")
        installation = self.get_installation()
        update_ref = self._find_update_ref(installation, app_id)
        if update_ref is None:
            for candidate in self.get_installations():
                update_ref = self._find_update_ref(candidate, app_id)
                if update_ref is not None:
                    installation = candidate
                    break
        if update_ref is None:
            emit("not-found", 0, f"No update candidate found for {app_id}.")
            raise FlatpakAPIError(f"No update candidate found for {app_id}.")

        ref_string = self._ref_string(update_ref)
        emit("queue", 35, f"Queuing update for {ref_string}...")
        transaction = self._new_transaction(installation)
        if not self._queue_update_operation(transaction, ref_string):
            emit("error", 0, f"Unable to queue update for {ref_string}.")
            raise FlatpakAPIError(f"Unable to queue update for {ref_string}.")

        cancellable = self._create_cancellable()
        try:
            emit("run", 70, f"Applying update for {app_id}...")
            if cancellable is None:
                try:
                    transaction.run(None)
                except TypeError:
                    transaction.run()
            else:
                try:
                    transaction.run(cancellable)
                except TypeError:
                    transaction.run()
        except GLib.Error as exc:
            emit("error", 0, f"Failed to update {app_id}: {exc.message}")
            raise FlatpakAPIError(f"Failed to update {app_id}: {exc.message}") from exc
        finally:
            self._release_cancellable(cancellable)

        emit("done", 100, f"Update completed for {app_id}.")

    def cancel_operations(self) -> None:
        """Request cancellation of active Flatpak transaction operations."""
        with self._cancellables_lock:
            cancellables = list(self._cancellables)
        for cancellable in cancellables:
            try:
                cancellable.cancel()
            except Exception:
                logger.warning("Unable to cancel a Flatpak transaction", exc_info=True)

    def _create_cancellable(self):
        if Gio is None:
            return None
        cancellable = Gio.Cancellable()
        with self._cancellables_lock:
            self._cancellables.add(cancellable)
        return cancellable

    def _release_cancellable(self, cancellable) -> None:
        if cancellable is None:
            return
        with self._cancellables_lock:
            self._cancellables.discard(cancellable)

    def _find_update_ref(self, installation, app_id: str):
        requested = self._normalize_app_id(app_id)
        try:
            refs = installation.list_installed_refs_for_update(None)
        except TypeError:
            refs = installation.list_installed_refs_for_update()
        except GLib.Error as exc:
            raise FlatpakAPIError(f"Unable to query updates for {app_id}: {exc.message}") from exc

        for ref in refs:
            if not self._ref_kind_is_supported(ref):
                continue
            current = self._normalize_app_id(self._ref_name(ref))
            if current == requested:
                return ref
        return None

    @staticmethod
    def _new_transaction(installation):
        if hasattr(Flatpak.Transaction, "new_for_installation"):
            try:
                return Flatpak.Transaction.new_for_installation(installation, None)
            except TypeError:
                return Flatpak.Transaction.new_for_installation(installation)
        if hasattr(Flatpak.Transaction, "new"):
            try:
                return Flatpak.Transaction.new(installation, None)
            except TypeError:
                return Flatpak.Transaction.new(installation)
        raise FlatpakAPIError("Flatpak.Transaction constructor is unavailable.")

    def _queue_update_operation(self, transaction, ref_string: str) -> bool:
        try:
            result = transaction.add_update(ref_string, None, None)
            return bool(result)
        except TypeError:
            try:
                return bool(transaction.add_update(ref_string))
            except TypeError as exc:
                raise FlatpakAPIError(f"Unsupported update signature for {ref_string}: {exc}") from exc
        except GLib.Error as exc:
            raise FlatpakAPIError(f"Unable to queue update for {ref_string}: {exc.message}") from exc

    def _to_app_list(self, refs, include_runtimes: bool = False) -> List[FlatpakAppInfo]:
        apps: List[FlatpakAppInfo] = []
        seen = set()
        for ref in refs:
            if include_runtimes:
                if not self._ref_kind_is_supported(ref):
                    continue
            elif not self._ref_kind_is_app(ref):
                continue
            app_id = self._ref_name(ref)
            key = self._ref_key(ref, app_id)
            if key in seen:
                continue
            seen.add(key)
            apps.append(
                FlatpakAppInfo(
                    app_id=app_id,
                    current_version=self._version(ref),
                    branch=self._safe_call(ref, "get_branch", ""),
                    arch=self._safe_call(ref, "get_arch", ""),
                    origin=self._safe_call(ref, "get_origin", ""),
                )
            )
        return sorted(apps, key=lambda item: item.app_id.lower())

    @staticmethod
    def _ref_key(ref, app_id: str) -> str:
        return (
            f"{FlatpakManager._ref_kind(ref)}|{app_id}|"
            f"{FlatpakManager._safe_call(ref, 'get_branch', '')}|"
            f"{FlatpakManager._safe_call(ref, 'get_arch', '')}"
        )

    @staticmethod
    def _ref_kind(ref):
        if hasattr(ref, "get_kind"):
            return ref.get_kind()
        if hasattr(ref, "kind"):
            return ref.kind
        return None

    @staticmethod
    def _ref_kind_is_app(ref) -> bool:
        return FlatpakManager._ref_kind(ref) == Flatpak.RefKind.APP

    @staticmethod
    def _ref_kind_is_runtime(ref) -> bool:
        runtime_kind = getattr(Flatpak.RefKind, "RUNTIME", None)
        return runtime_kind is not None and FlatpakManager._ref_kind(ref) == runtime_kind

    @staticmethod
    def _ref_kind_is_supported(ref) -> bool:
        return FlatpakManager._ref_kind_is_app(ref) or FlatpakManager._ref_kind_is_runtime(ref)

    @staticmethod
    def _ref_name(ref) -> str:
        if hasattr(ref, "get_name"):
            return ref.get_name()
        if hasattr(ref, "name"):
            return ref.name
        return ""

    @staticmethod
    def _normalize_app_id(value: str) -> str:
        normalized = (value or "").strip().lower()
        return normalized.removeprefix("app/").removeprefix("runtime/")

    def _version(self, ref) -> str:
        for getter in ("get_appdata_version", "get_latest_commit", "get_commit"):
            value = self._safe_call(ref, getter, "")
            if value:
                return str(value)
        return "n/a"

    @staticmethod
    def _load_ref_metadata(ref) -> dict[str, str]:
        loader = getattr(ref, "load_metadata", None)
        if not callable(loader):
            return {}
        try:
            data = loader(None)
        except TypeError:
            try:
                data = loader()
            except (GLib.Error, TypeError):
                logger.debug("Unable to load Flatpak metadata", exc_info=True)
                return {}
        except GLib.Error:
            logger.debug("Unable to load Flatpak metadata", exc_info=True)
            return {}

        raw = data.get_data() if hasattr(data, "get_data") else bytes(data)
        if not isinstance(raw, bytes):
            raw = bytes(raw)
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(raw.decode("utf-8"))
        except (UnicodeDecodeError, configparser.Error):
            logger.warning("Ignoring malformed Flatpak metadata")
            return {}
        section = "Application" if parser.has_section("Application") else "Runtime" if parser.has_section("Runtime") else None
        if section is None:
            return {}
        return {key.lower(): value for key, value in parser.items(section)}

    @staticmethod
    def _available_commit(installation, ref) -> str:
        fetcher = getattr(installation, "fetch_remote_ref_sync", None)
        origin = FlatpakManager._safe_call(ref, "get_origin", "")
        if not callable(fetcher) or not origin:
            return "n/a"
        try:
            remote_ref = fetcher(
                origin,
                ref.get_kind(),
                FlatpakManager._ref_name(ref),
                FlatpakManager._safe_call(ref, "get_arch", ""),
                FlatpakManager._safe_call(ref, "get_branch", ""),
                None,
            )
        except TypeError:
            try:
                remote_ref = fetcher(
                    origin,
                    ref.get_kind(),
                    FlatpakManager._ref_name(ref),
                    FlatpakManager._safe_call(ref, "get_arch", ""),
                    FlatpakManager._safe_call(ref, "get_branch", ""),
                )
            except (GLib.Error, TypeError):
                logger.warning("Unable to fetch remote Flatpak ref %s", FlatpakManager._ref_string(ref), exc_info=True)
                return "n/a"
        except GLib.Error:
            logger.warning("Unable to fetch remote Flatpak ref %s", FlatpakManager._ref_string(ref), exc_info=True)
            return "n/a"
        return FlatpakManager._safe_call(remote_ref, "get_commit", "n/a")

    @staticmethod
    def _ref_string(ref) -> str:
        if hasattr(ref, "format_ref"):
            result = ref.format_ref()
            if result:
                return str(result)
        name = FlatpakManager._ref_name(ref)
        arch = FlatpakManager._safe_call(ref, "get_arch", "")
        branch = FlatpakManager._safe_call(ref, "get_branch", "")
        if name and arch and branch:
            prefix = "runtime" if FlatpakManager._ref_kind_is_runtime(ref) else "app"
            return f"{prefix}/{name}/{arch}/{branch}"
        return str(name or ref)

    @staticmethod
    def _safe_call(obj, method_name: str, default: str) -> str:
        method = getattr(obj, method_name, None)
        if callable(method):
            try:
                return method() or default
            except TypeError:
                return default
        return default
