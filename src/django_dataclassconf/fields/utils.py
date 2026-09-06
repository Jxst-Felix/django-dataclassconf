from dataclasses import fields
import typing

from .bases import (
    FieldGeneric, 
    FieldValue, 
    Field,
    FV, 
)

__all__ = [
    'resolve_config_fields',
    'create_field_type',
    'is_config_field',
]

def create_field_type(
    field_value_class: typing.Type[FV], 
    field_name: typing.Optional[str] = None
) -> typing.Type[FV]:
    """
    Dynamically constructs a :class:`FieldGeneric` subclass and its corresponding
    :class:`Field` subclass for the provided :class:`FieldValue` subclass.

    Notes
    ---
    The decorator intentionally returns the generated :class:`Field` type at
    runtime while presenting the original :class:`FieldValue` type to static
    type checkers and to properly support IDE autocompletion.
    """
    name = field_name or field_value_class.__name__.removesuffix('Value')
    if not name:
        raise ValueError(
            f'Cannot derive field name from {field_value_class.__name__!r}'
        )

    generic_class: typing.Type[FieldGeneric] = type(
        f'_{name}Generic', 
        (FieldGeneric, ), 
        {'_value_class': field_value_class}
    )

    field_class: typing.Type[Field] = type(
        f'_{name}Field', 
        (Field, ), 
        {'_generic_class': generic_class}
    )

    return typing.cast(typing.Type[FV], field_class)


def is_config_field(field_type: typing.Any) -> bool:
    """
    Return ``True`` if ``field_type`` is a parameterised :class:`Field` annotation.
     
    A parameterised :class:`Field` annotation is an instance of
    :class:`FieldGeneric`.
    """
    return isinstance(field_type, FieldGeneric)


def resolve_config_fields(
    data: typing.Dict[str, typing.Any],
    config_class: typing.Type,
) -> typing.Dict[str, typing.Any]:
    """
    Wrap raw configuration values in their :class:`FieldValue` instances.
 
    Iterates over the dataclass fields of ``config_class``. For every
    field whose type annotation is a :class:`FieldGeneric` instance
    (i.e. a parameterised :class:`Field` subclass), the corresponding
    raw value in ``data`` is passed to
    :meth:`FieldGeneric.instantiate` and replaced with the resulting
    :class:`FieldValue`.
 
    Fields not annotated with a ``Field`` subclass are left unchanged.
    If a ``Field``-annotated key is absent from ``data``, the dataclass
    field default is used.
 
    Called internally by
    :meth:`~django_dataclassconf.conf.BaseConfig.update` before
    ``dacite`` validates the full configuration dictionary.
 
    Parameters
    ----------
    data:
        Raw configuration key-value pairs, typically extracted from
        Django settings.
    config_class:
        The dataclass type whose field annotations are inspected.
 
    Returns
    -------
    dict
        A copy of ``data`` with ``Field``-annotated values replaced by
        :class:`FieldValue` instances.
    """
    result = dict(data)
    for field in fields(config_class):
        f_type = field.type
        if not is_config_field(f_type):
            continue
    
        if field.name not in result:
            result[field.name] = field.default
    
        value = result[field.name]
        result[field.name] = f_type.instantiate(value)
    return result