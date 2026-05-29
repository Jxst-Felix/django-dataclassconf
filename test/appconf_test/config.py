from dataclasses import dataclass, asdict, field
from django_dataclassconf.conf import BaseConfig

@dataclass
class Renderer:
    length: int = 256
    width: int = 256
    refresh_rate: int = 60


@dataclass
class TestConfig(BaseConfig):
    DEFAULT_PATH: str = '/root/default/path/'
    MAX_RETRIES: int = 5
    RENDERER: Renderer = field(default_factory = Renderer)

    @property
    def _prefix(self):
        return 'TEST'


configuration = TestConfig()