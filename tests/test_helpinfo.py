from manapak.helpinfo import ManapakHelpInfo


def test_help_info_has_all_navigation_sections():
    info = ManapakHelpInfo()

    for section in ("home", "checking", "updating", "information", "privileges"):
        assert info.show(section)
    assert "href=\"checking\"" in info.home()


def test_unknown_help_section_is_empty():
    assert ManapakHelpInfo().show("missing") == ""
