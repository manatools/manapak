# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
Unit tests for dnfdragora integration of manapak.

Tests cover:
- The adapter module (dnfdragora_plugin.py) correctly re-exports ManapakDialog
- The updater module (dnfdragora_plugin_updater.py) exposes get_update_count() correctly
- Error handling and thread-safety
- Mocking to avoid launching the real GUI or requiring Flatpak

License: GPLv3
Author:  Angelo Naselli <anaselli@linux.it>

@package manapak.tests.test_dnfdragora_integration
'''

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

import manapak.dnfdragora_plugin
import manapak.dnfdragora_plugin_updater
from manapak.ui import ManapakDialog
from manapak.flatpak_api import FlatpakAPIError, FlatpakAppInfo


class TestDnfdragoraPluginAdapter(unittest.TestCase):
    """Test that the plugin adapter correctly re-exports ManapakDialog."""

    def test_manapak_dialog_is_re_exported(self):
        """
        Test that ManapakDialog in dnfdragora_plugin is the same as the original.

        This confirms the adapter is a true re-export and not a duplicate class.
        """
        adapter_dialog = manapak.dnfdragora_plugin.ManapakDialog
        original_dialog = ManapakDialog

        self.assertIs(
            adapter_dialog,
            original_dialog,
            "ManapakDialog should be the same object in both modules"
        )

    def test_plugin_adapter_has_all_export(self):
        """Test that the plugin module has __all__ defined."""
        self.assertTrue(
            hasattr(manapak.dnfdragora_plugin, '__all__'),
            "Plugin adapter should define __all__ for proper introspection"
        )
        self.assertIn(
            'ManapakDialog',
            manapak.dnfdragora_plugin.__all__,
            "__all__ should include ManapakDialog"
        )

    def test_plugin_adapter_module_docstring(self):
        """Test that the plugin adapter has a docstring explaining its role."""
        self.assertIsNotNone(
            manapak.dnfdragora_plugin.__doc__,
            "Plugin adapter module should have a docstring"
        )
        doc = manapak.dnfdragora_plugin.__doc__.lower()
        self.assertIn(
            "re-export",
            doc,
            "Module docstring should mention re-export"
        )


class TestDnfdragoraUpdater(unittest.TestCase):
    """Test the updater module's get_update_count() function."""

    def test_get_update_count_success_with_updates(self):
        """Test get_update_count() returns the correct count when updates are available."""
        mock_apps = [
            MagicMock(spec=FlatpakAppInfo, app_id="app1"),
            MagicMock(spec=FlatpakAppInfo, app_id="app2"),
            MagicMock(spec=FlatpakAppInfo, app_id="app3"),
            MagicMock(spec=FlatpakAppInfo, app_id="org.gnome.Platform", ref_type="runtime"),
            MagicMock(spec=FlatpakAppInfo, app_id="org.gnome.Platform.Locale", ref_type="runtime"),
        ]

        with patch('manapak.dnfdragora_plugin_updater.FlatpakManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.check_updates.return_value = mock_apps

            result = manapak.dnfdragora_plugin_updater.get_update_count()

            self.assertEqual(result, 5)
            mock_manager_class.assert_called_once_with(use_system_installation=True)
            mock_manager.check_updates.assert_called_once()

    def test_get_update_count_success_no_updates(self):
        """Test get_update_count() returns 0 when no updates are available."""
        with patch('manapak.dnfdragora_plugin_updater.FlatpakManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.check_updates.return_value = []

            result = manapak.dnfdragora_plugin_updater.get_update_count()

            self.assertEqual(result, 0)

    def test_get_update_count_handles_flatpak_api_error(self):
        """Test get_update_count() returns 0 when FlatpakAPIError is raised."""
        with patch('manapak.dnfdragora_plugin_updater.FlatpakManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.check_updates.side_effect = FlatpakAPIError(
                "Flatpak bindings not available"
            )

            result = manapak.dnfdragora_plugin_updater.get_update_count()

            self.assertEqual(result, 0)

    def test_get_update_count_handles_generic_exception(self):
        """Test get_update_count() returns 0 when an unexpected exception is raised."""
        with patch('manapak.dnfdragora_plugin_updater.FlatpakManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.check_updates.side_effect = RuntimeError(
                "Unexpected Flatpak error"
            )

            result = manapak.dnfdragora_plugin_updater.get_update_count()

            self.assertEqual(result, 0)

    def test_get_update_count_uses_system_installation(self):
        """Test that get_update_count() specifically uses system installation."""
        with patch('manapak.dnfdragora_plugin_updater.FlatpakManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.check_updates.return_value = []

            manapak.dnfdragora_plugin_updater.get_update_count()

            mock_manager_class.assert_called_once_with(use_system_installation=True)

    def test_get_update_count_function_exists(self):
        """Test that get_update_count() is defined and callable."""
        self.assertTrue(
            hasattr(manapak.dnfdragora_plugin_updater, 'get_update_count'),
            "dnfdragora_plugin_updater module should define get_update_count()"
        )
        self.assertTrue(
            callable(manapak.dnfdragora_plugin_updater.get_update_count),
            "get_update_count should be callable"
        )

    def test_get_update_count_has_docstring(self):
        """Test that get_update_count() has a proper docstring."""
        docstring = manapak.dnfdragora_plugin_updater.get_update_count.__doc__
        self.assertIsNotNone(docstring, "get_update_count should have a docstring")
        self.assertIn(
            "worker thread",
            docstring.lower(),
            "Docstring should mention threading/worker context"
        )
        self.assertIn(
            "returns",
            docstring.lower(),
            "Docstring should describe return value"
        )


class TestDnfdragoraIntegrationSmoke(unittest.TestCase):
    """Integration-level smoke tests."""

    def test_adapter_dialog_can_be_imported_by_module_path(self):
        """Test that dnfdragora can discover and import the dialog."""
        import importlib

        try:
            module = importlib.import_module('manapak.dnfdragora_plugin')
            self.assertTrue(
                hasattr(module, 'ManapakDialog'),
                "Module should have ManapakDialog attribute"
            )
        except ImportError as e:
            self.fail(f"Failed to import dnfdragora_plugin: {e}")

    def test_updater_module_can_be_imported_by_module_path(self):
        """Test that dnfdragora-updater can discover and import the updater module."""
        import importlib

        try:
            module = importlib.import_module('manapak.dnfdragora_plugin_updater')
            self.assertTrue(
                hasattr(module, 'get_update_count'),
                "Module should have get_update_count function"
            )
        except ImportError as e:
            self.fail(f"Failed to import dnfdragora_plugin_updater: {e}")


if __name__ == '__main__':
    unittest.main()
