# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
manapak is a desktop application for checking and applying Flatpak updates based on ManaTools AUI python

License: GPLv3

Author:  Angelo Naselli <anaselli@linux.it>

@package manapak
'''
from manapak.helpinfo import ManapakHelpInfo


def test_help_info_has_all_navigation_sections():
    info = ManapakHelpInfo()

    for section in ("home", "checking", "updating", "information", "privileges"):
        assert info.show(section)
    assert "href=\"checking\"" in info.home()


def test_unknown_help_section_is_empty():
    assert ManapakHelpInfo().show("missing") == ""
