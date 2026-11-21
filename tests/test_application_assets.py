from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from manapak import (
    APP_DESCRIPTION,
    APP_DISPLAY_NAME,
    APP_ICON_NAME,
    APP_ICON_PATH,
    APP_LICENSE,
)


def test_application_metadata_is_ready_for_about_dialog():
    assert APP_ICON_NAME == "manapak"
    assert APP_DISPLAY_NAME
    assert APP_DESCRIPTION
    assert APP_LICENSE == "GPL-3.0-or-later"


def test_application_svg_icon_exists_and_is_svg():
    icon_path = Path(APP_ICON_PATH)

    assert icon_path.is_file()
    assert icon_path.suffix == ".svg"
    root = ET.parse(icon_path).getroot()
    assert root.tag.endswith("svg")


def test_desktop_entry_points_to_packaged_application():
    desktop = Path("share/applications/org.mageia.manapak.desktop").read_text(encoding="utf-8")

    assert "Exec=manapak" in desktop
    assert "Icon=manapak" in desktop
    assert "Type=Application" in desktop


def test_hicolor_icons_have_expected_dimensions():
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon = Path(f"share/icons/hicolor/{size}x{size}/apps/manapak.png").read_bytes()
        assert icon[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", icon[16:24])
        assert (width, height) == (size, size)


def test_hicolor_scalable_icon_matches_packaged_icon():
    installed = Path("share/icons/hicolor/scalable/apps/manapak.svg")
    packaged = Path(APP_ICON_PATH)

    assert installed.is_file()
    assert installed.read_bytes() == packaged.read_bytes()


def test_icon_is_original_cc0_artwork():
    icon = Path(APP_ICON_PATH).read_text(encoding="utf-8")
    notice = Path("NOTICE").read_text(encoding="utf-8")

    assert "SPDX-License-Identifier: CC0-1.0" in icon
    assert "not the Flatpak project logo" in notice
    assert "CC0-1.0" in notice
