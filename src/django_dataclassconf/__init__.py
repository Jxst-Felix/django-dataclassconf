"""
Typed, dataclass-based configuration management for Django.
"""

__version__ = '0.2.0'

from .conf import BaseConfig, config_loader
from .fields import Importable, ImportableValue

__all__ = [
    "BaseConfig", 
    "config_loader", 
    "Importable", 
    "ImportableValue", 
    "__version__",
]