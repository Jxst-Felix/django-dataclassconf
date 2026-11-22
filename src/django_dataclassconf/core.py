"""
Configuration loading and automatic settings synchronization.

This module provides a lightweight observer system that keeps dataclass-
based configuration objects synchronized with Django settings.

Configuration instances are registered with a global
:class:`PackageConfigLoader` and are automatically refreshed whenever
Django emits the `setting_changed` signal.

Supported configuration styles:

- Prefixed settings::

      TEST_MAX_RETRIES = 10

- Dictionary settings::

      TEST = {
          "MAX_RETRIES": 10,
      }

When both forms are present, prefixed settings take precedence.
"""
from django.test.signals import setting_changed
from django.conf import settings

from dataclasses import asdict, fields, MISSING
from dacite import from_dict, WrongTypeError

from contextvars import ContextVar
from abc import ABC

import warnings
from collections.abc import Callable
from typing import (
    Dict,
    List,
    Set,
    Any,
)

from .fields import resolve_config_fields

__all__ = [
    'BaseConfig', 
    'config_loader',
]


_internal_construction = ContextVar(
    'internal_construction',
    default = False,
)

class BaseConfig(ABC):
    """
    Base class for dataclass-backed configuration objects.

    Subclasses define configuration fields as dataclass attributes and
    provide a settings prefix through the `prefix` property in the :class:`Meta` class.

    Registered configuration instances are automatically updated when
    Django settings change.

    Example
    -------
    ::

        @dataclass
        class MyConfig(BaseConfig):
            MAX_RETRIES: int = 5

            class Meta:
                prefix = "MYAPP"

    This configuration can then be customized using either::

        MYAPP = {"MAX_RETRIES": 10}

    or::

        MYAPP_MAX_RETRIES = 10
    """
    class Meta:
        """
        Configuration metadata.

        Attributes:
            prefix: *(default: `''`)* Namespace prefix for Django settings.
            use_defaults: *(default: `False`)* Fall back to defaults on validation failure.
            export_to_config: *(default: `None`)* Override an existing configuration.
            deprecated: *(default: `[]`)* Settings that should trigger deprecation warnings.
        """
        prefix: str = ''
        use_defaults: bool = False
        export_to_config: object = None
        deprecated: List[str] = []

    def __post_init__(self):
        self._default_fields = {
            field.name: field
            for field in fields(self.__class__)
        }

        if not _internal_construction.get():
            self.update(asdict(self))
            config_loader.subscribe(self)

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        cls._computed_fields: Dict[str, str] = {
            name.removeprefix('get_').upper(): name
            for name in dir(cls)
            if name.startswith('get_')
        }

        sub_meta = cls.__dict__.get("Meta")
        if sub_meta is None:
            return

        if not isinstance(sub_meta, type):
            raise TypeError(
                f"{cls.__name__}.Meta must be a class."
            )

        parent_meta = next(
            (
                base.__dict__["Meta"]
                for base in cls.__mro__[1:]
                if "Meta" in base.__dict__
            ),
            BaseConfig.Meta,
        )

        inherited_attrs = {
            key: value
            for key, value in vars(parent_meta).items()
            if not key.startswith("_")
        }

        inherited_attrs.update({
            key: value
            for key, value in vars(sub_meta).items()
            if not key.startswith("_")
        })

        setattr(cls, "Meta", type("Meta", (), inherited_attrs))

    def _process_computed_fields(self, data: Dict[str, Any]):
        data_copy = data.copy()
        for setting, value in data_copy.items():
            method = self._computed_fields.get(setting, None)
            if method is not None:
                processor: Callable[[Any], Any] = getattr(self, method)
                data_copy[setting] = processor(value)
        return data_copy

    def _get_default_value(self, field_name: str):
        field = self._default_fields.get(field_name, None)
        if field is None:
            return MISSING
        
        if field.default is not MISSING:
            return field.default

        if field.default_factory is not MISSING:
            return field.default_factory()
        return None

    def _construct_validated_instance(self, data):
        token = _internal_construction.set(True)
        try:
            return from_dict(
                data_class = self.__class__,
                data = data,
            )
        finally:
            _internal_construction.reset(token)

    def _get_instance_with_defaults(
        self, data: Dict[str, Any]
    ):
        fallback_fields = set()
        while True:
            try:
                return self._construct_validated_instance(
                    data = data
                )

            except WrongTypeError as exc:
                field_name = exc.field_path
                if (
                    field_name in fallback_fields or
                    field_name not in self._default_fields.keys()
                ):
                    raise

                default_value = self._get_default_value(field_name)
                if default_value is MISSING:
                    raise

                default = {field_name: default_value}
                if field_name in self._computed_fields:
                    default = self._process_computed_fields(default)

                data.update(default)
                fallback_fields.add(field_name)

    def update(self, config_data: Dict[str, Any]):
        """
        Update the configuration instance from raw configuration data.

        Incoming values are merged with the current configuration state,
        normalized through :func:`resolve_config_fields`, and validated using
        `dacite.from_dict()`.

        Parameters
        ----------
        config_data:
            Mapping of configuration keys to values.

        Raises
        ------
        DaciteError
            If the resulting configuration cannot be validated against the
            dataclass schema.
        """
        deprecated_fields = (
            set(self.Meta.deprecated) &
            set(config_data.keys())
        )

        if deprecated_fields:
            warnings.warn(
                message = (
                    'The following fields are marked as '
                    f'DEPRECATED: {deprecated_fields}'
                ),
                category = DeprecationWarning,
                stacklevel = 2
            )

        previous_data = asdict(self)
        computed_data = self._process_computed_fields(config_data)
        data_with_field_types = resolve_config_fields(computed_data, self.__class__)
        new_data = {**previous_data, **data_with_field_types}

        validated_instance = (
            self._get_instance_with_defaults(
                data = new_data
            ) if self.__class__.Meta.use_defaults else (
                self._construct_validated_instance(
                    data = new_data
                )
            )
        )

        if self.Meta.export_to_config is not None:
            for setting, value in new_data.items():
                setattr(
                    self.Meta.export_to_config,
                    setting, value,
                )

        vars(self).update(vars(validated_instance))


class PackageConfigLoader:
    """
    Registry and refresh manager for configuration instances.

    The loader tracks subscribed :class:`BaseConfig` instances and
    refreshes them when relevant Django settings change.

    Most applications interact with the module-level
    :data:`config_loader` singleton rather than creating their own
    loader.
    """
    def __init__(self):
        self._dataclass_configs: List[BaseConfig] = []

    @property
    def prefixes(self) -> Set[str]:
        """Return all registered non-empty configuration prefixes."""
        return set([
            config.Meta.prefix
            for config in self._dataclass_configs 
            if config.Meta.prefix
        ])

    def subscribe(self, config: BaseConfig):
        """
        Register a configuration instance with the loader.

        Newly subscribed configurations are immediately populated from the
        current Django settings.
        """
        if not any(
            subscriber is config
            for subscriber in self._dataclass_configs
        ):
            self._dataclass_configs.append(config)
            self.refresh_config(config, self._settings_as_dict())

    def refresh_config(
        self, config: BaseConfig, 
        config_data: Dict[str, Any]
    ):
        """
        Refresh a single configuration instance.

        Configuration values are loaded from two sources:

        1. A dictionary setting matching the configuration prefix.
        2. Individual settings using the ``PREFIX_*`` convention.

        For example, a prefix of ``TEST`` supports::

            TEST = {
                "MAX_RETRIES": 5,
            }

            TEST_MAX_RETRIES = 10

        If both forms define the same key, the prefixed setting takes
        precedence.
        """
        prefix = config.Meta.prefix
        if not prefix:
            config.update(config_data)
            return
        
        prefix_ = f'{prefix}_'
        flat_config = { 
            k.removeprefix(prefix_): v 
            for k, v in config_data.items() 
            if k.startswith(prefix_) 
        }

        config_dict = config_data.get(prefix, {})
        if isinstance(config_dict, config.__class__):
            config_dict = asdict(config_dict)

        elif not isinstance(config_dict, dict):
            config_dict = {}

        config.update({**config_dict, **flat_config})

    def refresh_all(self, setting: str):
        """
        Refresh all configurations affected by a settings change.

        Only configurations whose prefix matches the changed setting are
        updated.
        """
        config_data = None
        for config in self._dataclass_configs:
            prefix = config.Meta.prefix
            prefix_ = f'{prefix}_'

            if not prefix or setting == prefix or setting.startswith(prefix_):
                if config_data is None:
                    config_data = self._settings_as_dict()
                self.refresh_config(config, config_data)

    def _settings_as_dict(self) -> Dict[str, Any]:
        """
        Convert Django settings into a plain dictionary.

        Only uppercase settings are included.
        """
        return {
            k: getattr(settings, k)
            for k in dir(settings)
            if k.isupper()
        }


config_loader = PackageConfigLoader()

def refresh_settings(sender, setting, value, enter, **kwargs):
    config_loader.refresh_all(setting)
setting_changed.connect(refresh_settings)
