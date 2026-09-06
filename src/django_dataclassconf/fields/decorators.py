import typing

from .utils import create_field_type
from .bases import (
    FieldGeneric, 
    FieldValue, 
    Field,
    FV, 
)

__all__ = [
    'field_type',
]

def field_type(
    *, field_name: typing.Optional[str] = None
) -> typing.Callable[[typing.Type[FV]], typing.Type[FV]]:
    """
    Decorate a :class:`FieldValue` subclass to create its corresponding
    configuration field type.

    The decorator automatically generates the runtime
    :class:`FieldGeneric` and :class:`Field` classes required to use the
    decorated :class:`FieldValue` as a parameterised configuration field.
    
    Notes
    ---
    The decorator intentionally returns the generated :class:`Field` type at
    runtime while presenting the original :class:`FieldValue` type to static
    type checkers and to properly support IDE autocompletion.
    """

    def _decorator(field_value_class: typing.Type[FV]) -> typing.Type[FV]:
        return create_field_type(field_value_class, field_name)
    return _decorator