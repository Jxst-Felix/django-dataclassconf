"""Implements an Observer pattern for when settings have changed"""
from django.test.signals import setting_changed
from django.conf import settings

from abc import ABC, abstractmethod
from dataclasses import asdict
from dacite import from_dict
import typing


class BaseConfig(ABC):
    """Base class that updates a dataclass to use them as config classes"""
    @property
    @abstractmethod
    def _prefix(self) -> str: ...

    def update(self, config_data: typing.Dict[str, typing.Any]):
        previous_data = asdict(self)
        new_data = {**previous_data, **config_data}
        validated_instance = from_dict(data_class = self.__class__, data = new_data)
        vars(self).update(vars(validated_instance))


class PackageConfigLoader:
    """Loads config into multiple dataclasses"""
    def __init__(self):
        self._dataclass_configs: typing.List[BaseConfig] = []

    @property
    def prefixes(self) -> typing.List[str]:
        """Provides the list of prefixes available in config loader, excludes empty prefixes"""
        return [
            config._prefix 
            for config in self._dataclass_configs 
            if config._prefix
        ]
    
    def subscribe(self, config: BaseConfig):
        if config not in self._dataclass_configs:
            self._dataclass_configs.append(config)
            self.refresh_config(config, self._settings_as_dict())

    def refresh_config(
        self, config: BaseConfig, 
        config_data: typing.Dict[str, typing.Any]
    ):
        """Refreshes a single specific configuration instance from raw settings"""
        prefix = config._prefix
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
        config_data = None
        for config in self._dataclass_configs:
            prefix = config._prefix
            prefix_ = f'{prefix}_'

            if not prefix or setting == prefix or setting.startswith(prefix_):
                if config_data is None:
                    config_data = self._settings_as_dict()
                self.refresh_config(config, config_data)

    def _settings_as_dict(self) -> typing.Dict[str, typing.Any]:
        return {
            k: getattr(settings, k)
            for k in dir(settings)
            if k.isupper()
        }


config_loader = PackageConfigLoader()

def refresh_settings(sender, setting, value, enter, **kwargs):
    config_loader.refresh_all(setting)
setting_changed.connect(refresh_settings)
