"""
Field system for typed, validated configuration values.
 
This module provides two layers of functionality:
 
**Base classes for custom fields**
 
:class:`FieldValue`, :class:`FieldGeneric`, and :class:`Field` form the
extension API. Library users subclass these to create their own validated
or transformed configuration field types.
 
**Built-in importable fields**
 
:class:`ImportableValue` and :data:`Importable` are the concrete
implementation of lazily resolved dotted import paths, built on top of
the base classes.
 
Supported import formats for ``Importable`` fields:
 
- Python import paths:
  ``"package.module.ClassName"``
- Django model references:
  ``"app_label.ModelName"``
 
Field-annotated dataclass attributes are automatically converted from
their raw settings values into :class:`FieldValue` instances by
:func:`resolve_config_fields`, which is called during
:meth:`~django_dataclassconf.conf.BaseConfig.update`.
"""
from django.utils.module_loading import import_string
from django.apps import apps

from dataclasses import fields

from abc import ABC, abstractmethod
from collections import abc
import pathlib
import typing
import os

__all__ = [
    'FieldValue',
    'FieldGeneric',
    'Field',

    'is_config_field',
    'resolve_config_fields',

    'ImportableValue',
    'Importable',

    'PathValue',
    'Path',
]


T = typing.TypeVar('T')

class FieldValue(typing.Generic[T], ABC):
    """
    Base class for validated, typed configuration field values.
 
    ``FieldValue[T]`` is the runtime wrapper that holds a raw
    configuration value, validates it, and resolves it to a final
    Python object of type ``T``.
 
    Subclass ``FieldValue`` to implement custom field behaviour. 
    Instances are created automatically by the paired
    :class:`FieldGeneric` subclass during
    :func:`resolve_config_fields`.
 
    Subclasses must implement:
 
    - :meth:`validate` — raise on invalid input.
    - :meth:`resolve` — return the final value of type ``T``.
    - :meth:`__repr__`
    - :meth:`__eq__`
    - :meth:`__hash__`
 
    The concrete :attr:`is_valid` property is provided for free and
    should not normally be overridden.
    """
    @abstractmethod
    def validate(self):
        """
        Validate the wrapped value.
 
        Should raise an appropriate exception (e.g. ``ValueError``,
        ``TypeError``) if the value is invalid. Must not return a
        meaningful value — callers that need a boolean result should use
        :attr:`is_valid` instead.
 
        Raises
        ------
        Exception
            Any exception type that signals an invalid value. The exact
            type is left to the subclass.
        """
        ...

    @property
    def is_valid(self) -> bool:
        """Return ``True`` if :meth:`validate` passes without raising."""
        try:
            self.validate()
            return True

        except Exception:
            return False

    @abstractmethod
    def resolve(self) -> T:
        """
        Validate and return the final configuration value.
 
        Implementations should call :meth:`validate` and then return the
        resolved value of type ``T``. The resolved value may differ from
        the raw input (e.g. a ``Path`` field may accept a ``str`` and
        return a :class:`pathlib.Path`).
 
        Raises
        ------
        Exception
            Any exception raised by :meth:`validate`.
        """
        ...

    @abstractmethod
    def __repr__(self):
        ...

    @abstractmethod
    def __eq__(self, value) -> bool:
        ...

    @abstractmethod
    def __hash__(self):
        ...


FV = typing.TypeVar('FV', bound = FieldValue)

class FieldGeneric(typing.Generic[FV], ABC):
    """
    Runtime representation of a parameterised :class:`Field` annotation.
 
    Instances of ``FieldGeneric`` subclasses are produced by
    ``Field.__class_getitem__`` and stored as
    the ``type`` of a dataclass field. They carry the inner type
    parameter and know how to construct the appropriate
    :class:`FieldValue` instance for a raw value.
 
    ``FieldGeneric`` subclasses are internal to each field
    implementation and should not be instantiated directly by users.
 
    Subclasses must implement:
 
    - :meth:`instanciate` — wrap a raw value in the paired
      :class:`FieldValue` subclass.
    - :meth:`__repr__`
 
    The ``__instancecheck__`` hook always returns ``True`` so that
    ``dacite`` accepts :class:`FieldValue` instances as valid for
    fields annotated with a ``FieldGeneric`` alias.
 
    If a subclass requires no extra state beyond the inner type, it can
    rely on the inherited :meth:`__init__` without defining its own.
    """
    def __init__(self, inner_type: typing.Any):
        self.__inner_type__: typing.Any = inner_type
        self.__origin__: typing.Any = None

    def __instancecheck__(self, instance):
        return True

    @abstractmethod
    def __repr__(self):
        ...

    @abstractmethod
    def instanciate(self, value: typing.Any) -> FV:
        """
        Wrap a raw configuration value in the paired FieldValue subclass.
 
        Called by :func:`resolve_config_fields` for every field whose
        type annotation is an instance of this ``FieldGeneric``.
 
        Parameters
        ----------
        value:
            The raw value read from Django settings.
 
        Returns
        -------
        FV
            A :class:`FieldValue` instance wrapping ``value``.
        """
        ...


class Field(ABC):
    """
    Base class for dataclass field type annotations backed by
    :class:`FieldValue`.
 
    ``Field`` subclasses are used purely as type annotations in
    dataclass definitions. They are never instantiated at runtime.
    Parameterising a subclass (e.g. ``EmailField[str]``) returns a
    :class:`FieldGeneric` instance that ``dacite`` and
    :func:`resolve_config_fields` use to construct the appropriate
    :class:`FieldValue`.
 
    To create a custom field type, define three classes:
 
    1. A :class:`FieldValue` subclass with the validation and resolution
       logic.
    2. A :class:`FieldGeneric` subclass whose :meth:`~FieldGeneric.instanciate`
       constructs the ``FieldValue``.
    3. A ``Field`` subclass with ``_generic_class`` pointing at the
       ``FieldGeneric`` subclass.
 
    ``_generic_class`` is validated at subclass definition time via
    :meth:`__init_subclass__`, so configuration errors are caught as
    early as possible.
 
    Example
    -------
    ::

        if typing.TYPE_CHECKING:
            Email = EmailValue

        else:
            class Email(Field):
                _generic_class = _EmailGeneric
 
        @dataclass
        class MyConfig(BaseConfig):
            ADMIN_EMAIL: Email[str] = 'admin@example.com'
 
            @property
            def _prefix(self):
                return 'MYAPP'
 
    Raises
    ------
    TypeError
        If a subclass does not set ``_generic_class`` to a
        :class:`FieldGeneric` subclass, either at class definition time
        or when the annotation is parameterised.
    """

    _generic_class: typing.Type[FieldGeneric] = None

    def __class_getitem__(cls, item: typing.Any) -> FieldGeneric:
        cls._validate()
        alias = cls._generic_class(item)
        alias.__origin__ = cls
        return alias
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._validate()
        
    @classmethod
    def _validate(cls):
        """
        Assert that ``_generic_class`` is a valid :class:`FieldGeneric` subclass.
 
        Called by both :meth:`__init_subclass__` and
        :meth:`__class_getitem__` to ensure ``_generic_class`` is set
        correctly before any ``FieldGeneric`` instance is constructed.
 
        Raises
        ------
        TypeError
            If ``_generic_class`` is ``None`` or not a subclass of
            :class:`FieldGeneric`.
        """
        if (
            cls._generic_class is None or 
            not issubclass(cls._generic_class, FieldGeneric)
        ):
            raise TypeError(f'{cls.__name__}._generic_class must be a subclass of FieldGeneric!')


def is_config_field(field_type: typing.Any) -> bool:
    """
    Return ``True`` if ``field_type`` is a parameterised :class:`Field` annotation.
 
    A parameterised ``Field`` annotation is an instance of
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
    :meth:`FieldGeneric.instanciate` and replaced with the resulting
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
        result[field.name] = f_type.instanciate(value)
    return result


class ImportableValue(FieldValue):
    """
    Lazily resolves a dotted import path to a Python object.

    ``ImportableValue`` is the :class:`FieldValue` implementation for
    :data:`Importable` fields. It stores a dotted import string and
    resolves it to the target Python object only when :meth:`resolve` is
    called, caching the result for subsequent lookups.
 
    Supported import formats:
 
    - Python import paths: ``"package.module.ClassName"``
    - Django model references: ``"app_label.ModelName"``
    """
    def __init__(self, import_str: str, inner_type: typing.Any):
        self.import_str = import_str
        self.inner_type = inner_type
        self._imported_obj = None

    def _perform_import(self):
        """
        Resolve ``import_str`` to a Python object and cache the result.
 
        Tries :func:`django.apps.apps.get_model` first to support Django
        model references (``"app_label.ModelName"``). Falls back to
        :func:`django.utils.module_loading.import_string` for all other
        dotted paths.
 
        Does nothing if the object has already been imported.
 
        Raises
        ------
        ImportError
            If ``import_string`` cannot locate the target.
        Exception
            Any exception raised while importing the target module is
            propagated unchanged.
        """
        if self._imported_obj:
            return
        
        try:
            self._imported_obj = apps.get_model(self.import_str)
            
        except (LookupError, ValueError):
            self._imported_obj = import_string(self.import_str)

    def validate(self):
        """
        Import the target object and verify it matches ``inner_type``.
 
        Calls :meth:`_perform_import` to ensure the object is loaded,
        then checks it against the type argument supplied to
        ``Importable[T]``:
 
        - ``Importable[type[BaseClass]]`` — asserts the imported object
          is a subclass of ``BaseClass``.
        - ``Importable[Callable]`` — asserts the imported object is
          callable.
        - Other types — validated with ``isinstance()`` where possible;
          uninspectable generic aliases are accepted without error.
 
        Raises
        ------
        TypeError
            If the imported object does not satisfy the expected type.
        ImportError
            If the import path cannot be resolved (propagated from
            :meth:`_perform_import`).
        """
        self._perform_import()

        origin = typing.get_origin(self.inner_type)
        args = typing.get_args(self.inner_type)

        if origin is type:
            expected_base = args[0] if args else object
            nested_origin = typing.get_origin(expected_base)
            if nested_origin is not None:
                expected_base = nested_origin

            if not (
                isinstance(self._imported_obj, type) and 
                issubclass(self._imported_obj, expected_base)
            ):
                raise TypeError(
                    f'Resolving {self.import_str}: '
                    f'expected a subclass of {expected_base} but got {self._imported_obj}'
                )
        
        if any([
            self.inner_type is typing.Callable, 
            self.inner_type is abc.Callable,
            origin is abc.Callable, 
        ]):
            if not callable(self._imported_obj):
                raise TypeError(
                    f'Resolving {self.import_str}: '
                    f'expected a callable, but got {type(self._imported_obj)}'
                )
        
        try:
            valid = isinstance(self._imported_obj, self.inner_type)

        except TypeError:
            valid = True

        if not valid:
            raise TypeError(
                f'Resolving {self.import_str}: '
                f'expected a subclass of {self.inner_type} but got {type(self._imported_obj)}'
            )
        ...

    def resolve(self):
        """
        Validate and return the imported object.
 
        If the object has not been imported yet, calls :meth:`validate`. 
        Returns the cached object on subsequent calls.
 
        Returns
        -------
        object
            The resolved Python object identified by :attr:`import_str`.
 
        Raises
        ------
        ImportError
            If the import path cannot be resolved.
        TypeError
            If the imported object does not match the expected type.
        Exception
            Any exception raised while importing the target module.
        """
        if not self._imported_obj:
            self.validate()
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


class _ImportableGeneric(FieldGeneric):
    """
    Runtime representation of ``Importable[T]``.
 
    Produced by ``Importable[T]`` at annotation time and stored as the
    ``type`` of the corresponding dataclass field. Carries the inner
    type parameter and constructs :class:`ImportableValue` instances
    during :func:`resolve_config_fields`.
 
    Users should not instantiate this class directly.
    """
    def __repr__(self):
        return f'Importable[{self.__inner_type__}]'
    
    def instanciate(self, value):
        return ImportableValue(value, self.__inner_type__)


class _ImportableField(Field):
    """
    Type annotation for lazily imported configuration values.
 
    ``Importable[T]`` declares that a configuration field holds a
    dotted import path string which, when resolved, yields an object
    compatible with ``T``.
 
    At runtime ``Importable[T]`` returns an
    :class:`_ImportableGeneric` instance. Under static type checkers
    ``Importable`` is aliased to :class:`ImportableValue` so that
    ``.resolve()`` and other methods are type-checkable.
 
    The raw string is automatically wrapped in an
    :class:`ImportableValue` by :func:`resolve_config_fields` when
    the configuration is loaded. The import itself is deferred until
    :meth:`~ImportableValue.resolve` is called.
 
    Examples
    --------
    Import a class::
 
        CONFIG_CLASS: Importable[type[BaseConfig]]
 
    Import an instance::
 
        DEFAULT_RENDERER: Importable[Renderer]
 
    Import a callable::
 
        SERIALIZER: Importable[typing.Callable]
 
    Import a Django model::
 
        USER_MODEL: Importable[type[User]]
    """
    _generic_class = _ImportableGeneric



class PathValue(FieldValue[pathlib.Path]):
    """
    Resolves a raw configuration value into a :class:`pathlib.Path`.

    ``PathValue`` is the :class:`FieldValue` implementation for
    :data:`Path` fields. It accepts a filesystem path expressed as a
    ``str`` or :class:`os.PathLike` and resolves it to a
    :class:`pathlib.Path` object.

    Note
    ----
    The public :data:`Path` alias intentionally shadows
    :class:`pathlib.Path`. Within this module the standard library type
    is always referred to as ``pathlib.Path`` to avoid confusion.
    """
    def __init__(self, value: typing.Any, inner_type: typing.Any):
        self.value = value
        self.inner_type = inner_type

    def validate(self):
        """
        Verify the wrapped value is path-like.

        Raises
        ------
        TypeError
            If the value is neither a ``str`` nor an :class:`os.PathLike`.
        """
        if not isinstance(self.value, (str, os.PathLike)):
            raise TypeError(
                f'{self.value!r} is not a valid path (expected str or os.PathLike, '
                f'got {type(self.value).__name__})'
            )

    def resolve(self) -> pathlib.Path:
        """
        Validate and return the value as a :class:`pathlib.Path`.

        Returns
        -------
        pathlib.Path
            The path constructed from the raw value.

        Raises
        ------
        TypeError
            If the value is not path-like.
        """
        self.validate()
        return pathlib.Path(self.value)

    def __repr__(self):
        return f'Path({self.value!r})'

    def __eq__(self, other) -> bool:
        if isinstance(other, PathValue):
            return self.value == other.value
        return NotImplemented

    def __hash__(self):
        return hash(self.value)


class _PathGeneric(FieldGeneric):
    """
    Runtime representation of ``Path[T]``.

    Produced by ``Path[T]`` at annotation time and stored as the ``type``
    of the corresponding dataclass field. Constructs :class:`PathValue`
    instances during :func:`resolve_config_fields`.

    Users should not instantiate this class directly.
    """
    def __repr__(self):
        return f'Path[{self.__inner_type__}]'

    def instanciate(self, value):
        return PathValue(value, self.__inner_type__)


class _PathField(Field):
    """
    Type annotation for filesystem-path configuration values.

    ``Path[T]`` declares that a configuration field holds a filesystem
    path (as a ``str`` or :class:`os.PathLike`) which resolves to a
    :class:`pathlib.Path`.

    At runtime ``Path[T]`` returns a :class:`_PathGeneric` instance.
    Under static type checkers ``Path`` is aliased to :class:`PathValue`
    so that ``.resolve()`` is typed as returning :class:`pathlib.Path`.

    Example
    -------
    ::

        DOCUMENTS_ROOT: Path[str] = '/the/default/path/'
    """
    _generic_class = _PathGeneric


if typing.TYPE_CHECKING:
    Importable = ImportableValue
    Path = PathValue

else:
    Importable = _ImportableField
    Path = _PathField
