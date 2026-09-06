from django.utils.module_loading import import_string
from django.apps import apps

from collections import abc
import pathlib
import typing
import os

from .bases import FieldValue
from .decorators import field_type


__all__ = [
    'Importable',
    'Path',
]

@field_type()
class Importable(FieldValue):
    """
    Lazily resolves a dotted import path to a Python object.

    Stores a dotted import string and
    resolves it to the target Python object only when :meth:`resolve` is
    called, caching the result for subsequent lookups.
 
    Supported import formats:
 
    - Python import paths: ``"package.module.ClassName"``
    - Django model references: ``"app_label.ModelName"``
    """
    def __init__(self, value, inner_type):
        super().__init__(value, inner_type)
        self._imported_obj = None

    def _perform_import(self):
        """
        Resolve :attr:`value` to a Python object and cache the result.
         
        Tries :func:`django.apps.apps.get_model` first to support Django
        model references (``"app_label.ModelName"``). Falls back to
        :func:`django.utils.module_loading.import_string` for all other
        dotted paths.
         
        Does nothing if the object has already been imported.
         
        Raises
        ------
        ImportError
            If :func:`import_string` cannot locate the target.
        Exception
            Any exception raised while importing the target module is
            propagated unchanged.
        """
        if self._imported_obj:
            return

        try:
            self._imported_obj = apps.get_model(self.value)

        except (LookupError, ValueError):
            self._imported_obj = import_string(self.value)

    def validate(self):
        """
        Import the target object and verify it matches :attr:`inner_type`.
         
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
                    f'Resolving {self.value}: '
                    f'expected a subclass of {expected_base} but got {self._imported_obj}'
                )

        if any([
            self.inner_type is typing.Callable, 
            self.inner_type is abc.Callable,
            origin is abc.Callable, 
        ]):
            if not callable(self._imported_obj):
                raise TypeError(
                    f'Resolving {self.value}: '
                    f'expected a callable, but got {type(self._imported_obj)}'
                )

        try:
            valid = isinstance(self._imported_obj, self.inner_type)
        
        except TypeError:
            valid = True
        
        if not valid:
            raise TypeError(
                f'Resolving {self.value}: '
                f'expected a subclass of {self.inner_type} but got {type(self._imported_obj)}'
            )

    def resolve(self):
        """
        Validate and return the imported object.
         
        If the object has not been imported yet, calls :meth:`validate`. 
        Returns the cached object on subsequent calls.
         
        Returns
        -------
        object
            The resolved Python object identified by :attr:`value`.
         
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
        return self.value

    def __eq__(self, value):
        if isinstance(value, str):
            return self.value == value
        return super().__eq__(value)


@field_type()
class Path(FieldValue[pathlib.Path]):
    """
    Resolves a raw configuration value into a :class:`pathlib.Path`.
    
    Accepts a filesystem path expressed as a
    ``str`` or :class:`os.PathLike` and resolves it to a
    :class:`pathlib.Path` object.
    
    Note
    ----
    The public :data:`Path` alias intentionally shadows
    :class:`pathlib.Path`. Within this module the standard library type
    is always referred to as :class:`pathlib.Path` to avoid confusion.
    """

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

    def resolve(self):
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
        return pathlib.Path(
            super().resolve()
        )

    def __str__(self):
        return self.value

    def __eq__(self, value):
        if isinstance(value, str):
            return self.value == value
        return super().__eq__(value)
