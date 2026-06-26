# Django DataclassConf

[![PyPI - Version](https://img.shields.io/pypi/v/django-dataclassconf?style=flat-square&logo=pypi&logoColor=white&color=blue)](https://pypi.org/project/django-dataclassconf/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-dataclassconf?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/django-dataclassconf/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)

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
from dataclasses import dataclass
from django_dataclassconf.conf import BaseConfig, config_loader

@dataclass
class MyPackageConfig(BaseConfig):
    DOCUMENTS_ROOT_PATH: str = '/the/default/path/'
    MAX_FILE_SIZE: int = 10000

    @property
    def _prefix(self) -> str:
        """
        Define the config's prefix here. Return a blank string if it doesn't
        have a prefix, such as when writing a configuration dataclass that
        will hold the `DEBUG` setting.
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
        from django_dataclassconf.conf import config_loader
        from .config import package_config

        config_loader.subscribe(package_config)
```

### 3. Access Your Settings Anywhere

The core practice is to import your configuration instance directly instead of using the global `django.conf.settings` object, to get full type safety and IDE autocomplete.

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

### Nested Dataclasses

Your configuration dataclass can also contain nested dataclasses.
You only need to inherit `BaseConfig` on the root configuration dataclass.

```python
from dataclasses import dataclass, field
from django_dataclassconf.conf import BaseConfig, config_loader

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

Which maps to this in `settings.py`:

```python
MY_PACKAGE = {
    'DOCUMENTS_ROOT_PATH': '/custom/path/',
    'PREVIEW': {
        'preview_page_count': 12,
        'strip_cover_page': True
    },
}
```

## Built-in Field Types

### Importable

For settings that hold a dotted import path to a class, instance, or callable in another module, annotate them with `Importable` from `fields.py`. The import is deferred — nothing is resolved until you explicitly call `.resolve()`.

```python
from dataclasses import dataclass
from django_dataclassconf.fields import Importable
import typing

from .models import Segment

@dataclass
class MyConfig(BaseConfig):
    SEGMENTER_FUNC: Importable[typing.Callable] = 'myapp.utils.segment_audio'
    SEGMENT_SERIALIZER_CLASS: Importable[typing.Type[Serializer]] = 'myapp.serializers.SegmentSerializer'
    SEGMENT_MODEL: Importable[typing.Type[Segment]] = 'myapp.Segment'

configuration = MyConfig()
```

Call `.resolve()` when you need the actual object. It validates the type on first call and caches the result:

```python
# Raises ImportError if the path is invalid, or TypeError if the
# resolved object does not match the annotated type.
try:
    segment_model = configuration.SEGMENT_MODEL.resolve()

except ImportError as ie:
    print(f'Could not import SEGMENT_MODEL: {ie}')

except TypeError as te:
    print(f'Imported value has different type than expected: {te}')
```

## Custom Field Types

*Introduced in version 0.3.0.*

You can define your own field types with custom validation and transformation logic by subclassing three base classes from `fields.py`: `FieldValue`, `FieldGeneric`, and `Field`.

Each custom field type requires three pieces:

* **`FieldValue` subclass** — holds the raw value, implements `validate()` (raises on invalid input) and `resolve()` (returns the final value).
* **`FieldGeneric` subclass** — the runtime object produced by `YourField[T]`. Implements `instanciate()` to construct the `FieldValue`.
* **`Field` subclass** — the annotation class used in dataclass definitions. Points at the `FieldGeneric` via `_generic_class`.

### Simple Example: Email Field

A straightforward validator that checks the value is a valid email address before returning it as a plain string.

```python
from django_dataclassconf.fields import Field, FieldGeneric, FieldValue
import typing


class EmailValue(FieldValue[str]):
    def __init__(self, value: str):
        self.value = value

    def validate(self):
        if not isinstance(self.value, str) or '@' not in self.value:
            raise ValueError(f'{self.value!r} is not a valid email address')

    def resolve(self) -> str:
        self.validate()
        return self.value

    def __repr__(self):
        return f'EmailValue({self.value!r})'

    def __eq__(self, other):
        if isinstance(other, EmailValue):
            return self.value == other.value
        return NotImplemented

    def __hash__(self):
        return hash(self.value)


class _EmailGeneric(FieldGeneric['EmailValue']):
    def __repr__(self):
        return f'Email[{self.__inner_type__}]'

    def instanciate(self, value: str) -> EmailValue:
        return EmailValue(value)


if typing.TYPE_CHECKING:
    Email = EmailValue

else:
    class Email(Field):
        _generic_class = _EmailGeneric
```

Use it in your configuration dataclass the same way as any built-in field type:

```python
@dataclass
class MyConfig(BaseConfig):
    ADMIN_EMAIL: Email[str] = 'admin@example.com'

    @property
    def _prefix(self):
        return 'MY_APP'
```

Call `.resolve()` to get the validated value, or check `.is_valid` if you want a boolean without raising:

```python
# Raises ValueError if the configured value is not a valid email address
admin_email = my_config.ADMIN_EMAIL.resolve()

# Non-raising check
if my_config.ADMIN_EMAIL.is_valid:
    ...
```

### Advanced Example: Deprecated Field

A field that emits a `DeprecationWarning` when validated, useful for marking settings that are still supported but scheduled for removal.

```python
from django_dataclassconf.fields import Field, FieldGeneric, FieldValue
import warnings
import typing


class DeprecatedValue(FieldValue):
    def __init__(self, value: typing.Any, inner_type: typing.Type[typing.Any]):
        self.value = value
        self.inner_type = inner_type

    def validate(self):
        if not isinstance(self.value, self.inner_type):
            raise TypeError(
                f'Instance {self.value} is not of type {self.inner_type.__name__}'
            )
        warnings.warn('This setting is deprecated', DeprecationWarning, stacklevel=2)

    def resolve(self):
        return self.value

    def __repr__(self):
        return repr(self.value)

    def __eq__(self, other):
        if isinstance(other, DeprecatedValue):
            return self.value == other.value and self.inner_type == other.inner_type
        return NotImplemented

    def __hash__(self):
        return hash((repr(self.value), repr(self.inner_type)))


class _DeprecatedGeneric(FieldGeneric['DeprecatedValue']):
    def __repr__(self):
        return f'Deprecated[{self.__inner_type__}]'

    def instanciate(self, value) -> DeprecatedValue:
        return DeprecatedValue(value, self.__inner_type__)


if typing.TYPE_CHECKING:
    Deprecated = DeprecatedValue

else:
    class Deprecated(Field):
        _generic_class = _DeprecatedGeneric
```

```python
@dataclass
class MyConfig(BaseConfig):
    LEGACY_PATH: Deprecated[str] = '/old/default/path/'

    @property
    def _prefix(self):
        return 'MY_APP'
```

Calling `.validate()` on a `Deprecated` field emits the warning without raising, as long as the value is the correct type:

```python
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    my_config.LEGACY_PATH.validate()

# caught[0].category is DeprecationWarning
```

## License

This project is licensed under the MIT License — see the LICENSE file for details.
