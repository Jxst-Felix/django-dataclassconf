"""
Typed, dataclass-based configuration management for Django.
"""

__version__ = '0.3.0'

from .conf import BaseConfig, config_loader
from .fields import (
    FieldValue,
    FieldGeneric,
    Field,
    is_config_field,
    resolve_config_fields,
    ImportableValue,
    Importable,
    PathValue,
    Path,
)

__all__ = [
    "BaseConfig",
    "config_loader",

    "FieldValue",
    "FieldGeneric",
    "Field",

    "is_config_field",
    "resolve_config_fields",

    "Importable",
    "ImportableValue",

    "Path",
    "PathValue",

    "__version__",
]