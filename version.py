# -*- coding: utf-8 -*-
"""
Version management for Voirie Communale plugin
"""


__version__ = "0.20.4"
__version_info__ = (0, 20, 4)


def get_version():
    """Retourne la version actuelle du plugin"""
    return __version__


def get_version_info():
    """Retourne les informations de version sous forme de tuple"""
    return __version_info__
