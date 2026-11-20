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

from abc import ABC
from dataclasses import asdict
from dacite import from_dict
import typing

from .fields import resolve_config_fields

__all__ = [
    'BaseConfig', 
    'config_loader',
]

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
        # use_defaults: bool = False
        # export_to_config: object = None
        deprecated: typing.List[str] = []

    def __post_init__(self):
        config_loader.subscribe(self)

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        parent_meta = next(
            (
                base.__dict__["Meta"]
                for base in cls.__mro__[1:]
                if "Meta" in base.__dict__
            ),
            BaseConfig.Meta,
        )

        sub_meta = cls.__dict__.get("Meta")
        if sub_meta is None:
            return

        if not isinstance(sub_meta, type):
            raise TypeError(
                f"{cls.__name__}.Meta must be a class."
            )

        inherited_attrs = {
            k: v
            for k, v in vars(parent_meta).items()
            if not k.startswith("_")
        }

        inherited_attrs.update({
            k: v
            for k, v in vars(sub_meta).items()
            if not k.startswith("_")
        })

        cls.Meta = type("Meta", (), inherited_attrs)

    def update(self, config_data: typing.Dict[str, typing.Any]):
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
        previous_data = asdict(self)
        data_with_field_types = resolve_config_fields(config_data, self.__class__)
        new_data = {**previous_data, **data_with_field_types}
        validated_instance = from_dict(
            data_class = self.__class__, 
            data = new_data, 
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
        self._dataclass_configs: typing.List[BaseConfig] = []

    @property
    def prefixes(self) -> typing.List[str]:
        """Return all registered non-empty configuration prefixes."""
        return [
            config.Meta.prefix
            for config in self._dataclass_configs 
            if config.Meta.prefix
        ]
    
    def subscribe(self, config: BaseConfig):
        """
        Register a configuration instance with the loader.

        Newly subscribed configurations are immediately populated from the
        current Django settings.
        """
        if config not in self._dataclass_configs:
            self._dataclass_configs.append(config)
            self.refresh_config(config, self._settings_as_dict())

    def refresh_config(
        self, config: BaseConfig, 
        config_data: typing.Dict[str, typing.Any]
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

    def _settings_as_dict(self) -> typing.Dict[str, typing.Any]:
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
