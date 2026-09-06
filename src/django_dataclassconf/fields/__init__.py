"""
Field system for typed, validated configuration values.

Base classes for custom fields
---
:class:`FieldValue`, :class:`FieldGeneric`, and :class:`Field` form the
extension API. Library users subclass these to create their own validated
or transformed configuration field types.

Simplified field customization
---
A subclass of :class:`FieldValue` can automatically have its corresponding
subclasses of :class:`FieldGeneric` and :class:`Field` by two ways:
- Using the :func:`field_type` decorator
- Using the :func:`create_field_type` function

Built-in field types
---
- :class:`Importable`
- :class:`Path`

Field-annotated dataclass attributes are automatically converted from
their raw settings values into :class:`FieldValue` instances by
:func:`resolve_config_fields`, which is called during
:meth:`~django_dataclassconf.conf.BaseConfig.update`.
"""
from .bases import *
from .decorators import *
from .types import *
from .utils import *