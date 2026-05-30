<!-- Add badges here later when I have github actions, pypi link, and all -->

# Django DataclassConf

[![PyPI - Version](https://img.shields.io/pypi/v/django-dataclassconf?style=flat-square&logo=pypi&logoColor=white&color=blue)](https://pypi.org/project/django-dataclassconf/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-dataclassconf?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/django-dataclassconf/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

A simple Django package setting loader that utilizes dataclasses for type hinting and type checking.

Bring modern Python typing, robust validation, and full IDE autocomplete to your Django configurations.

`django-dataclassconf` allows you to bind your Django settings cleanly to structured standard Python `dataclasses`. Powered by [`dacite`](https://github.com/konradhalas/dacite), it automatically catches dynamic setting updates while ensuring your configuration layer stays type-safe and isolated.

## But Why?

* **Fail-Fast Validation:** Catch bad configuration types or missing values instantly during server startup or container deployment rather than hitting silent runtime crashes mid-request.

* **Full IDE Autocomplete:** Say goodbye to blind `getattr(settings, "MY_SETTING")` calls. Enjoy full hovering type definitions and autocompletion in VS Code, PyCharm, and MyPy.

* **Dual Format Normalization:** Merges flat environment styles (`PREFIX_TIMEOUT = 30`) and structured dictionary blocks (`PREFIX = {"TIMEOUT": 30}`) into a single unified object seamlessly.

* **Test-Safe Isolation:** Fully supports Django's test suite cycles. When settings are overridden dynamically in unit tests, your dataclasses mutate cleanly in-place and revert automatically.

## Usage

### 1. Define Your Configuration Dataclass

Create a file named `config.py` (or any name you prefer tbh) within your application or package.
Inherit from `BaseConfig` and define your variables.

```python
from dataclasses import dataclass, field
from django_dataclassconf.config import BaseConfig, config_loader

@dataclass
class MyPackageConfig(BaseConfig):
    DOCUMENTS_ROOT_PATH: str = '/the/default/path/'
    MAX_FILE_SIZE: int = 10000
    INDEXER_CLASS: str = 'myapp.utils.DocumentIndexer'

    @property
    def _prefix(self) -> str:
        """
        Define the config's prefix here, return blank string if it doesn't 
        have a prefix such as when we write a configuration dataclass that 
        will hold the `DEBUG` setting
        """
        return 'MY_PACKAGE'

package_config = MyPackageConfig()
```

### 2. Subscribe to the Configuration Loader

For your dataclass to grab configuration data from Django's `settings.py` on startup and capture updates during tests, subscribe your instance into `config_loader` inside your app's initialization hook:

```python
# my_app/apps.py
class MyAppConfig(AppConfig):
    name = 'my_app'
    
    def ready(self):
        from django_dataclassconf.config import config_loader
        from .config import package_config

        config_loader.subscribe(package_config)
```

### 3. Access Your Settings Anywhere

Core Practice would be to import your configuration instance directly instead of using the global `django.conf.settings` object to harness the full type safety and IDE autocomplete.

```python
# my_app/views.py
from django.http import HttpResponse
from my_app.config import package_config

def my_view(request):
    ...
    # Your IDE now natively autocompletes these fields
    if file_size > package_config.MAX_FILE_SIZE:
        return HttpResponse(
            {'detail': 'File size has exceeded the maximum size limit!'}, 
            status = 400
        )
```

## Extras

Your Configuration Dataclass can also be a nested dataclasses, you only need to inherit `BaseConfig` to the root configuration dataclass.

```python
from dataclasses import dataclass, field
from django_dataclassconf.config import BaseConfig, config_loader

@dataclass
class DocumentPreview:
    preview_page_count: int = 10
    strip_cover_page: bool = False

@dataclass
class MyPackageConfig(BaseConfig):
    DOCUMENTS_ROOT_PATH: str = '/the/default/path/'
    PREVIEW: DocumentPreview = field(default_factory=DocumentPreview)

    @property
    def _prefix(self) -> str:
        return 'MY_PACKAGE'

configuration = MyPackageConfig()
config_loader.subscribe(configuration)
```

And it will look like this in `settings.py`

```python
MY_PACKAGE = {
    'DOCUMENTS_ROOT_PATH': '/custom/path/',
    'PREVIEW': {
        'preview_page_count': 12,
        'strip_cover_page': True
    },
}
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
