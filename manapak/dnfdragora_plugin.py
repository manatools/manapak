# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
dnfdragora plugin adapter for manapak.

This module provides a stable import path for dnfdragora's plugin loader.
It re-exports the existing ManapakDialog class without modification,
allowing dnfdragora to load manapak as a plugin while maintaining
separation of concerns: ManapakDialog remains the UI implementation,
and this module serves only as an interface for plugin discovery.

License: GPLv3
Author:  Angelo Naselli <anaselli@linux.it>

@package manapak.dnfdragora_plugin
'''

from __future__ import annotations

from .ui import ManapakDialog

__all__ = ["ManapakDialog"]
