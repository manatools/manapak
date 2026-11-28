# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
dnfdragora updater module for manapak.

This module exposes the get_update_count() function required by dnfdragora-updater.
It wraps existing manapak Flatpak update-check logic without duplication.

The function is designed to be called from a background worker thread and performs
a single update check query. It returns 0 on any error (Flatpak unavailable, GLib errors, etc.)
to allow dnfdragora-updater to gracefully handle failures.

License: GPLv3
Author:  Angelo Naselli <anaselli@linux.it>

@package manapak.dnfdragora_plugin_updater
'''

from __future__ import annotations

import logging
from .flatpak_api import FlatpakManager, FlatpakAPIError

logger = logging.getLogger(__name__)


def get_update_count() -> int:
    """
    Get the number of Flatpak updates available.

    This function is called by dnfdragora-updater from a worker thread to determine
    if there are pending Flatpak updates. It queries the system Flatpak installation
    and returns the count of application and runtime refs with available updates.

    Thread-safe: This function performs no UI access and no polling loops. It may
    perform I/O (querying Flatpak) and is safe to call from background threads.

    Returns:
        int: Number of Flatpak application and runtime updates available (0 or more).
             Returns 0 on any error (Flatpak not available, GLib errors, permission issues, etc.)
    """
    try:
        manager = FlatpakManager(use_system_installation=True)
        updates = manager.check_updates()
        return len(updates)
    except FlatpakAPIError as exc:
        logger.warning("Failed to check Flatpak updates: %s", str(exc))
        return 0
    except Exception as exc:
        logger.warning("Unexpected error checking Flatpak updates: %s", str(exc), exc_info=True)
        return 0
