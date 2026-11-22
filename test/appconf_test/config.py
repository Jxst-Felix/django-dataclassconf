from django.contrib.auth.models import User

from rest_framework.settings import api_settings

from dataclasses import dataclass, asdict, field
import typing

from django_dataclassconf.core import BaseConfig
from django_dataclassconf.fields import Importable, Path

from .cust_fields import Deprecated, Email

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
    PROJECT_EMAIL: Email[str] = 'admin_project@domain.com'

    class Meta:
        prefix = 'TEST'

configuration = TestConfig()


@dataclass
class Test2Config(BaseConfig):
    DEFAULT_PATH: str = '/root/default/path/'
    MAX_RETRIES: int = 5

    class Meta:
        prefix = 'TEST'

configuration2 = Test2Config()


@dataclass
class WithDefaultsConfig(BaseConfig):
    MAX_RETRIES: int = 5
    KEEP_ACTIVE: bool = False

    class Meta:
        prefix = 'TEST_DEFAULTS'
        use_defaults = True


@dataclass
class WithExportInstanceConfig(BaseConfig):
    PAGE_SIZE: typing.Optional[int] = 10
    SEARCH_PARAM: str = 's'

    class Meta:
        prefix = 'REST_FRAMEWORK'
        export_to_config = api_settings


@dataclass
class WithDeprecationConfig(BaseConfig):
    OLD_RUNTIME_LIMIT: int = 5
    RUNTIME_LIMIT: int = 10

    class Meta:
        prefix = 'TEST'
        deprecated = [
            'OLD_RUNTIME_LIMIT',
        ]


@dataclass
class WithComputedFieldConfig(BaseConfig):
    WATER_TEMPERATURE: int = 28

    def get_water_temperature(self, value):
        return max(0, min(100, value))

    class Meta:
        prefix = 'TEST'


def new_as_dict(*args, **kwargs):
    return asdict(*args, **kwargs)

def foo_bar(x: str) -> bool:
    return '67' in x.strip()
