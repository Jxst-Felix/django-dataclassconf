from abc import ABC, abstractmethod
import typing


__all__ = [
    'FieldGeneric',
    'FieldValue',
    'Field',
]

T = typing.TypeVar('T')

class FieldValue(typing.Generic[T], ABC):
    """
    Base class for validated, typed configuration field values.
 
    ``FieldValue[T]`` is the runtime wrapper that holds a raw
    configuration value, validates it, and resolves it to a final
    Python object of type ``T``.
 
    Subclass ``FieldValue`` to implement custom field behavior. 
    Instances are created automatically by the paired
    :class:`FieldGeneric` subclass during
    :func:`resolve_config_fields`.
 
    Subclasses must implement:
    - :meth:`validate` — raise on invalid input.

    Subclasses may also override:
    - :meth:`resolve` — return the final value of type ``T``.
    - :meth:`__repr__`
    - :meth:`__eq__`
    - :meth:`__hash__`
 
    The concrete :attr:`is_valid` property is provided for free and
    should not normally be overridden.
    """
    def __init__(self, value: T, inner_type: typing.Type[T]):
        self.value = value
        self.inner_type = inner_type

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
        self.validate()
        return self.value

    def __repr__(self):
        return f'{type(self).__name__}({self.value!r}, expected={self.inner_type!r})'

    def __eq__(self, value) -> bool:
        if isinstance(value, type(self)):
            return (
                self.value == value.value
                and self.inner_type == value.inner_type
            )
        return NotImplemented

    def __hash__(self):
        return hash((self.value, repr(self.inner_type)))


FV = typing.TypeVar('FV', bound = FieldValue)

class FieldGeneric(typing.Generic[FV], ABC):
    """
    Runtime representation of a parameterised :class:`Field` annotation.
 
    Instances of ``FieldGeneric`` subclasses are produced by
    :meth:`Field.__class_getitem__` and stored as
    the ``type`` of a dataclass field. They carry the inner type
    parameter and know how to construct the appropriate
    :class:`FieldValue` instance for a raw value.
 
    ``FieldGeneric`` subclasses are internal to each field
    implementation and should not be instantiated directly by users.

    Subclasses must add:
    - :attr:`_value_class` — the :class:`FieldValue` that the
      ``FieldGeneric`` must instantiate.
 
    Subclasses may override:
 
    - :meth:`instantiate` — wrap a raw value in the paired
      :class:`FieldValue` subclass.
    - :meth:`__repr__`
 
    The ``__instancecheck__`` hook always returns ``True`` so that
    ``dacite`` accepts :class:`FieldValue` instances as valid for
    fields annotated with a ``FieldGeneric`` alias.
 
    If a subclass requires no extra state beyond the inner type, it can
    rely on the inherited :meth:`__init__` without defining its own.
    """
    _value_class: typing.Type[FV]

    def __init__(self, inner_type: typing.Type[typing.Any]):
        self.__inner_type__ = inner_type
        self.__origin__: typing.Any = None

    def __instancecheck__(self, instance):
        return isinstance(instance, self._value_class)

    def __repr__(self):
        return f'{type(self).__name__}[{self.__inner_type__!r}]'

    def instantiate(self, value: typing.Any) -> FV:
        """
        Wrap a raw configuration value in the paired :class:`FieldValue` subclass.
 
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
        return self._value_class(value, self.__inner_type__)


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
 
    To create a custom field type, check the [`docs`](https://github.com/Jxst-Felix/django-dataclassconf).
 
    :attr:`_generic_class` is validated at subclass definition time via
    :meth:`__init_subclass__`, so configuration errors are caught as
    early as possible.
 
    Raises
    ------
    TypeError
        If a subclass does not set :attr:`_generic_class` to a
        :class:`FieldGeneric` subclass, either at class definition time
        or when the annotation is parameterised.
    """

    _generic_class: typing.Type[FieldGeneric]

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
        Assert that :attr:`_generic_class` is a valid :class:`FieldGeneric` subclass.
 
        Called by both :meth:`__init_subclass__` and
        :meth:`__class_getitem__` to ensure :attr:`_generic_class` is set
        correctly before any :class:`FieldGeneric` instance is constructed.
 
        Raises
        ------
        TypeError
            If :attr:`_generic_class` is ``None`` or not a subclass of
            :class:`FieldGeneric`.
        """
        if (
            cls._generic_class is None or 
            not issubclass(cls._generic_class, FieldGeneric)
        ):
            raise TypeError(f'{cls.__name__}._generic_class must be a subclass of FieldGeneric!')
