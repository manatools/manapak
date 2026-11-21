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

import manatools.basehelpinfo as helpdata


_ = gettext.gettext


class ManapakHelpInfo(helpdata.HelpInfoBase):
    """Describe the Flatpak catalog, updates and privilege model."""

    def __init__(self) -> None:
        super().__init__()
        home_link = self._link(_("Go to index"), "home")
        index = "<ul>%s</ul>" % "".join(
            f"<li>{self._link(title, target)}</li>"
            for title, target in (
                (_("Checking for updates"), "checking"),
                (_("Updating applications"), "updating"),
                (_("Application information"), "information"),
                (_("Privileges and installation scopes"), "privileges"),
            )
        )
        self.text = {
            "home": (
                "<h1>manapak</h1>"
                + _(
                    "manapak inspects and updates Flatpak applications through "
                    "gi.repository.Flatpak. It does not execute Flatpak CLI commands."
                )
                + index
            ),
            "checking": (
                f"<h1>{_('Checking for updates')}</h1>"
                + _(
                    "At startup manapak loads installed applications and asks Flatpak "
                    "for available updates. Use Check Updates to refresh the catalog. "
                    "The View selector switches between updates and all installed apps."
                )
                + f"<p>{home_link}</p>"
            ),
            "updating": (
                f"<h1>{_('Updating applications')}</h1>"
                + _(
                    "Update All applies every available application update. A single "
                    "application can be updated from the table context menu. Progress "
                    "and status messages are handled in the background without "
                    "blocking the main interface."
                )
                + f"<p>{home_link}</p>"
            ),
            "information": (
                f"<h1>{_('Application information')}</h1>"
                + _(
                    "Open an application's context menu and choose Information to "
                    "inspect its origin, architecture, branch, runtime, SDK, base "
                    "application, installed commit and available commit."
                )
                + f"<p>{home_link}</p>"
            ),
            "privileges": (
                f"<h1>{_('Privileges and installation scopes')}</h1>"
                + _(
                    "User and system Flatpak installations are inspected. System "
                    "changes are authorized by the operating system's Flatpak and "
                    "Polkit integration. manapak never invokes sudo or pkexec."
                )
                + f"<p>{home_link}</p>"
            ),
        }

    @staticmethod
    def _link(description: str, target: str) -> str:
        return f'<a href="{target}">{description}</a>'

    def show(self, info_to_show: str) -> str:
        return self.text.get(info_to_show, "")

    def home(self) -> str:
        return self.text["home"]
