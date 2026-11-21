"""manapak package."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def N_(message):
    return message


PACKAGE_NAME = "manapak"

try:
    __version__ = version(PACKAGE_NAME)
except PackageNotFoundError:
    __version__ = "1.0.0-loc"

APP_NAME = PACKAGE_NAME
APP_ICON_NAME = APP_NAME
APP_ICON_PATH = str(Path(__file__).resolve().parent / "resources" / "manapak.svg")
APP_DISPLAY_NAME = N_("manapak - Flatpak updates")
APP_LICENSE = "GPL-3.0-or-later"
APP_DESCRIPTION = N_("Desktop tool to check and apply Flatpak updates via the Flatpak Python API.")
APP_CLI_DESCRIPTION = N_("Manage Flatpak updates through the Flatpak Python API.")
APP_PROJECT_URL = "https://github.com/manatools/manapak"
APP_MANATOOLS_URL = "https://github.com/manatools/python-manatools"

from .app import main

__all__ = [
    "APP_NAME",
    "APP_ICON_NAME",
    "APP_ICON_PATH",
    "APP_DISPLAY_NAME",
    "APP_LICENSE",
    "APP_DESCRIPTION",
    "APP_CLI_DESCRIPTION",
    "APP_PROJECT_URL",
    "APP_MANATOOLS_URL",
    "__version__",
    "main",
]
