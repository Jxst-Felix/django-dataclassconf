"""
Support for lazily imported configuration fields.

Provides the `Importable` type annotation and its runtime
representation, `ImportableValue`. These allow configuration values to be
stored as dotted import paths and resolved only when needed.

Supported import formats:

- Python import paths:
  `"package.module.ClassName"`
- Django model references:
  `"app_label.ModelName"`

Importable fields are automatically converted from strings into
`ImportableValue` instances by :func:`resolve_importables`.
"""
from django.utils.module_loading import import_string
from django.apps import apps

from dataclasses import fields

from collections import abc
import typing

__all__ = [
    'Importable', 
    'ImportableValue', 
    'resolve_importables', 
    'is_importable',
]

T = typing.TypeVar('T')

class ImportableValue(typing.Generic[T]):
    """
    Lazily resolves a dotted import path to a Python object.

    Instances are typically created automatically by
    :func:`resolve_importables` when a configuration field is annotated
    with `Importable[T]`.

    The imported object is resolved only when :meth:`resolve` is called
    and is cached for subsequent lookups.

    Examples
    --------
    Import a class::

        value = ImportableValue(
            "myapp.renderers.CustomRenderer",
            type[Renderer],
        )

        renderer_cls = value.resolve()

    Import a Django model::

        value = ImportableValue(
            "auth.User",
            type[User],
        )

        user_model = value.resolve()
    """
    def __init__(self, import_str: str, inner_type: typing.Any):
        self.import_str = import_str
        self.inner_type = inner_type
        self._imported_obj = None

    def _validate_type(self, imported_obj: typing.Any) -> typing.Any:
        """
        Validates if the imported object matches the expected type.

        Validation rules depend on the type parameter supplied to
        `Importable[T]`:

        - `Importable[type[BaseClass]]` requires the imported object to be
        a subclass of `BaseClass`.
        - `Importable[Callable]` requires the imported object to be callable.
        - Other types are validated using `isinstance()` where possible.

        Raises
        ------
        TypeError
            If the imported object does not satisfy the expected type.
        """
        origin = typing.get_origin(self.inner_type)
        args = typing.get_args(self.inner_type)

        if origin is type:
            expected_base = args[0] if args else object
            nested_origin = typing.get_origin(expected_base)
            if nested_origin is not None:
                expected_base = nested_origin

            if not (
                isinstance(imported_obj, type) and 
                issubclass(imported_obj, expected_base)
            ):
                raise TypeError(
                    f'Resolving {self.import_str}: '
                    f'expected a subclass of {expected_base} but got {imported_obj}'
                )
            
            return imported_obj
        
        if any([
            self.inner_type is typing.Callable, 
            self.inner_type is abc.Callable,
            origin is abc.Callable, 
        ]):
            if not callable(imported_obj):
                raise TypeError(
                    f'Resolving {self.import_str}: '
                    f'expected a callable, but got {type(imported_obj)}'
                )
            return imported_obj
        
        try:
            valid = isinstance(imported_obj, self.inner_type)

        except TypeError:
            valid = True

        if not valid:
            raise TypeError(
                f'Resolving {self.import_str}: '
                f'expected a subclass of {self.inner_type} but got {type(imported_obj)}'
            )
        return imported_obj

    def resolve(self) -> T:
        """
        Resolve and return the imported object.

        Django model references are resolved using `apps.get_model()`.
        All other import paths are resolved using Django's
        `import_string()`.

        Resolved objects are cached so subsequent calls do not repeat the
        import operation.

        Raises
        ------
        ImportError
            If the import path cannot be resolved.
        TypeError
            If the imported object does not match the expected type.
        Exception
            Any exception raised while importing the target module is
            propagated unchanged.
        """
        if not self._imported_obj:
            try:
                imported_obj = apps.get_model(self.import_str)
            except (LookupError, ValueError):
                imported_obj = import_string(self.import_str)

            self._imported_obj = self._validate_type(imported_obj)
        return self._imported_obj

    def __str__(self):
        return self.import_str
    
    def __repr__(self):
        return f'Importable({self.import_str}, expected={self.inner_type})'
    
    def __eq__(self, value) -> bool:
        if isinstance(value, ImportableValue):
            return (
                self.import_str == value.import_str
                and self.inner_type == value.inner_type
            )
        return NotImplemented
    
    def __hash__(self):
        return hash((self.import_str, repr(self.inner_type)))


class _ImportableGeneric:
    """
    Runtime representation of `Importable[T]`.

    This internal helper stores the type parameter supplied to
    `Importable` so it can later be inspected when processing
    dataclass fields.

    Users should not instantiate this class directly.
    """
    def __init__(self, inner_type: typing.Any) -> None:
        self.__inner_type__: typing.Any = inner_type
        self.__origin__: typing.Any = None
    
    def __repr__(self) -> str:
        return f'Importable[{self.__inner_type__}]'
    
    def __instancecheck__(self, instance):
        return True


if typing.TYPE_CHECKING:
    Importable = ImportableValue

else:
    class Importable:
        """
        Type annotation for lazily imported configuration values.

        `Importable[T]` declares that a configuration field should contain
        a dotted import path which resolves to an object compatible with
        `T`.

        Examples
        --------
        Import a class::

            CONFIG_CLASS: Importable[type[BaseConfig]]

        Import an instance::

            DEFAULT_RENDERER: Importable[Renderer]

        Import a callable::

            SERIALIZER: Importable[typing.Callable]
        """
        def __class_getitem__(cls, item: typing.Any) -> _ImportableGeneric:
            alias = _ImportableGeneric(item)
            alias.__origin__ = cls
            return alias


def is_importable(field_type: typing.Any) -> bool:
    """Determine whether a type annotation is `Importable[T]`."""
    return isinstance(field_type, _ImportableGeneric)


def resolve_importables(
    data: typing.Dict[str, typing.Any],
    config_class: typing.Type,
) -> typing.Dict[str, typing.Any]:
    """
    Convert import strings into `ImportableValue` instances.

    For every dataclass field annotated as `Importable[T]`:

    - Missing values are populated from the field default.
    - String values are wrapped in `ImportableValue`.
    - Existing `ImportableValue` instances are left unchanged.
    """
    result = dict(data)
    for field in fields(config_class):
        f_type = field.type
        if not is_importable(f_type):
            continue

        if field.name not in result:
            result[field.name] = field.default

        value = result[field.name]
        if isinstance(value, str):
            result[field.name] = ImportableValue(value, f_type.__inner_type__)
    return result
