from django.contrib.auth.models import User

from dataclasses import dataclass, asdict, field
import typing

from django_dataclassconf.conf import BaseConfig
from django_dataclassconf.fields import Importable, Path

from .cust_fields import Deprecated

@dataclass
class Renderer:
    length: int = 256
    width: int = 256
    refresh_rate: int = 60


@dataclass
class TestConfig(BaseConfig):
    DEFAULT_PATH: Deprecated[str] = '/root/default/path/'
    MAX_RETRIES: int = 5
    RENDERER: Renderer = field(default_factory = Renderer)
    CONFIG_SUBCLASS: Importable[type[BaseConfig]] = 'appconf_test.config.TestConfig'
    CONFIG_INSTANCE: Importable[BaseConfig] = 'appconf_test.config.configuration'
    USER_MODEL: Importable[type[User]] = 'auth.User'
    DATACLASS_AS_DICT: Importable[typing.Callable] = 'dataclasses.dataclass.asdict'
    MEDIA_ROOT: Path[str] = '/root/default/path/'

    @property
    def _prefix(self):
        return 'TEST'


@dataclass
class Test2Config(BaseConfig):
    DEFAULT_PATH: str = '/root/default/path/'
    MAX_RETRIES: int = 5

    @property
    def _prefix(self):
        return 'TEST'

def new_as_dict(*args, **kwargs):
    return asdict(*args, **kwargs)


configuration = TestConfig()
configuration2 = Test2Config()