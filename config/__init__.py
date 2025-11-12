"""Config package initializer.

Import `config` from this module in the rest of the project:

    from config import config

"""
from .settings import config, Config  # noqa: F401

__all__ = ['config', 'Config']
