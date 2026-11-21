# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
manapak is a desktop application for checking and applying Flatpak updates based on ManaTools AUI python

License: GPLv3

Author:  Angelo Naselli <anaselli@linux.it>

@package manapak
'''

from __future__ import annotations

import gettext
from importlib import metadata
import logging
import os
import sys

import manatools.aui.yui as MUI
from manatools.args import AppArgs
from manatools.ui import common as ui_common

from .ui import ManapakDialog
from . import (
    APP_CLI_DESCRIPTION,
    APP_DESCRIPTION,
    APP_DISPLAY_NAME,
    APP_ICON_NAME,
    APP_ICON_PATH,
    APP_LICENSE,
    APP_MANATOOLS_URL,
    APP_NAME,
    APP_PROJECT_URL,
    __version__,
)


DEFAULT_LOCALE_DIR = "/usr/share/locale"
_ = gettext.gettext
logger = logging.getLogger("manapak.app")


def _configure_i18n(locales_dir: str = DEFAULT_LOCALE_DIR):
    if hasattr(gettext, "bindtextdomain"):
        gettext.bindtextdomain(APP_NAME, locales_dir)
    if hasattr(gettext, "textdomain"):
        gettext.textdomain(APP_NAME)
    gettext.install(APP_NAME, localedir=locales_dir, names=("ngettext",))


def _extract_locales_dir(argv):
    for index, arg in enumerate(argv):
        if arg.startswith("--locales-dir="):
            return arg.split("=", 1)[1]
        if arg == "--locales-dir" and index + 1 < len(argv):
            return argv[index + 1]
    return None


def _create_parser(locales_dir):
    try:
        return AppArgs(APP_NAME, localedir=locales_dir).parser
    except TypeError:
        return AppArgs(APP_NAME).parser


def _configure_logging(args):
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    if getattr(args, "log_file", None):
        handler = logging.FileHandler(args.log_file, encoding="utf-8")
        level = logging.DEBUG if args.debug else logging.INFO
    elif args.logging or args.debug:
        handler = logging.StreamHandler()
        level = logging.DEBUG if args.debug else logging.INFO
    else:
        return

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
    logger.info("Starting manapak (log level: %s)", logging.getLevelName(level))


def _python_manatools_version() -> str:
    try:
        return metadata.version("python-manatools")
    except metadata.PackageNotFoundError:
        return "source checkout"


def _configure_application_metadata() -> None:
    app = MUI.YUI.app()
    author_email = "anaselli@linux.it"
    app.application_name = _(APP_DISPLAY_NAME)
    app.version = __version__
    app.license = APP_LICENSE
    app.description = _(APP_DESCRIPTION)
    app.authors = (
        f"<h3>{_('Developers')}</h3>"
        "<ul>"
        f"<li>Angelo Naselli ({author_email})</li>"
        "</ul>"
    )
    app.information = (
        f"<h3>{_('Project Links')}</h3>"
        "<ul>"
        f"<li><b>manapak:</b> <a href='{APP_PROJECT_URL}'>{APP_PROJECT_URL}</a></li>"
        f"<li><b>python-manatools:</b> <a href='{APP_MANATOOLS_URL}'>{APP_MANATOOLS_URL}</a></li>"
        "</ul>"
        f"<h3>{_('Runtime')}</h3>"
        "<ul>"
        f"<li><b>python-manatools:</b> {_python_manatools_version()}</li>"
        "</ul>"
    )
    app.logo = APP_ICON_PATH
    try:
        app.setApplicationIcon(APP_ICON_NAME)
    except Exception:
        logger.exception("Unable to set application icon by name %s", APP_ICON_NAME)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    early_locales_dir = _extract_locales_dir(argv)
    _configure_i18n(early_locales_dir or DEFAULT_LOCALE_DIR)

    parser = _create_parser(early_locales_dir or DEFAULT_LOCALE_DIR)
    parser.description = _(APP_CLI_DESCRIPTION)
    parser.add_argument("--logging", action="store_true", help=_("Enable console logging."))
    parser.add_argument("--log-file", metavar="PATHNAME", help=_("Write log entries to PATHNAME instead of the console."))
    parser.add_argument("--debug", action="store_true", help=_("Enable debug logging."))
    parser.add_argument("--user-installation", action="store_true", help=_("Use Flatpak user installation instead of system installation."))
    args = parser.parse_args(argv)

    if args.gtk:
        os.environ["MUI_BACKEND"] = "gtk"
    elif args.ncurses:
        os.environ["MUI_BACKEND"] = "ncurses"
    elif args.qt:
        os.environ["MUI_BACKEND"] = "qt"

    if args.locales_dir:
        _configure_i18n(args.locales_dir)

    _configure_logging(args)

    try:
        _configure_application_metadata()
        dialog = ManapakDialog(use_system_installation=not args.user_installation)
        dialog.run()
        return 0
    except Exception as exc:
        logger.exception("Failed to start manapak")
        try:
            ui_common.warningMsgBox(
                {
                    "title": _("Unable to start manapak"),
                    "text": _(
                        "The application could not be started safely.\n"
                        "Details: %s"
                    ) % str(exc),
                    "size": {"width": 560, "height": 220},
                }
            )
        except Exception:
            logger.exception("Unable to display the startup error dialog")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
