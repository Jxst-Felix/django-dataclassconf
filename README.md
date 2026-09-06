# Django DataclassConf

[![CI](https://github.com/Jxst-Felix/django-dataclassconf/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Jxst-Felix/django-dataclassconf/actions/workflows/pipeline.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/django-dataclassconf?style=flat-square&logo=pypi&logoColor=white&color=blue)](https://pypi.org/project/django-dataclassconf/)
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

    _prefix = 'MY_PACKAGE'

package_config = MyPackageConfig()
```

> _**Note:** Make sure to instantiate your config class for it to properly catch the settings and you can then access those settings via its instance._

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

    _prefix = 'MY_PACKAGE'

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

For settings that hold a dotted import path to a class, instance, or callable in another module, annotate them with `Importable` from `fields/types.py`. The import is deferred — nothing is resolved until you explicitly call `.resolve()`.

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

    _prefix = 'MY_PACKAGE'

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

### Path

For settings that hold a filesystem path, annotate them with `Path` from `fields/types.py`. The raw value may be a `str` or any `os.PathLike`; calling `.resolve()` validates it and returns a `pathlib.Path`.

```python
from dataclasses import dataclass
from django_dataclassconf.fields import Path

@dataclass
class MyConfig(BaseConfig):
    DOCUMENTS_ROOT: Path[str] = '/the/default/path/'

    _prefix = 'MY_PACKAGE'

configuration = MyConfig()
```

Call `.resolve()` to get the `pathlib.Path`:

```python
# Returns pathlib.Path('/the/default/path/')
root = configuration.DOCUMENTS_ROOT.resolve()

document = root / 'report.pdf'
```

> **Note:** `Path` intentionally shares its name with `pathlib.Path`. Import it under an alias (e.g. `from django_dataclassconf.fields import Path as PathField`) if you also need `pathlib.Path` in the same module.

## Custom Field Types

_Introduced in version 0.3.0._

You can define your own field types with custom validation and transformation logic by two ways.

### Decorator

**Introduced in _version 0.5.0_**, a simple way to customize a field type is by using a builder function:

* **`field_type`** — a decorator that automatically subclasses `FieldGeneric` and `Field`.
* **`create_field_type`** — a function that performs the same thing as `field_type`.

### Subclasses

**Introduced in _version 0.3.0_**, by subclassing three base classes from `fields/bases.py`: `FieldValue`, `FieldGeneric`, and `Field`.

Each custom field type requires three pieces:

* **`FieldValue` subclass** — holds the raw value, implements `validate()` (raises on invalid input) and `resolve()` (returns the final value).
* **`FieldGeneric` subclass** — the runtime object produced by `YourField[T]`. Implements `instanciate()` to construct the `FieldValue`.
* **`Field` subclass** — the annotation class used in dataclass definitions. Points at the `FieldGeneric` via `_generic_class`.

### Simple Example: Email Field (Decorator)

The simplified way of defining your own field type is by using the `field_type` decorator in `fields/decorators.py`.

```python
from django_dataclassconf.fields import field_type, FieldValue
import re

@field_type()
class Email(FieldValue):
    def validate(self):
        email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if not re.match(email_pattern, self.value):
            raise ValueError(f'Email value {self.value} is not a valid email address')

    def __str__(self):
        return self.value

    def __eq__(self, value):
        if isinstance(value, str):
            return self.value == value
        return super().__eq__(value)

# Email here serves as FieldValue subclass on static checkers but
# it is a subclass of Field during runtime
```

Alternatively, you may also use the builder function that the decorator uses internally which is `create_field_type` function located in `fields/utils.py`.

```python
from django_dataclassconf.fields import FieldValue, create_field_type
import re

class EmailValue(FieldValue):
    ... # implementation here

Email = create_field_type(EmailValue, 'Email')

# EmailValue here stays as FieldValue subclass and
# Email is a subclass of Field
```

Use it in your configuration dataclass the same way as any built-in field type:

```python
@dataclass
class MyConfig(BaseConfig):
    ADMIN_EMAIL: Email[str] = 'admin@example.com'

    _prefix = 'MY_APP'
```

Call `.resolve()` to get the validated value, or check `.is_valid` if you want a boolean without raising:

```python
# Raises ValueError if the configured value is not a valid email address
admin_email = my_config.ADMIN_EMAIL.resolve()

# Non-raising check
if my_config.ADMIN_EMAIL.is_valid:
    ...
```

### Advanced Example: Deprecated Field (Subclass)

A more controlled way to create your custom field type is by subclassing the classes `FieldValue`, `FieldGeneric`, and `Field`. An example will follow which is a field that emits a `DeprecationWarning` when validated, useful for marking settings that are still supported but scheduled for removal.

```python
from django_dataclassconf.fields import Field, FieldGeneric, FieldValue
import warnings
import typing


class DeprecatedValue(FieldValue):
    def validate(self):
        if not isinstance(self.value, self.inner_type):
            raise TypeError(
                f'Instance {self.value} is not of type {self.inner_type.__name__}'
            )
        warnings.warn('This setting is deprecated', DeprecationWarning, stacklevel=2)

# The following subclasses can be customized as much as you like
class _DeprecatedGeneric(FieldGeneric):
    _value_class = DeprecatedValue

    def instantiate(self, value):
        # you may add anything here
        return super().instantiate(value)

class _DeprecatedField(Field):
    _generic_class = _DeprecatedGeneric

if typing.TYPE_CHECKING:
    Deprecated = DeprecatedValue

else:
    Deprecated = _DeprecatedField
```

> _**Note:** A convention in naming your custom fields would to name `ObjValue` for subclass of `FieldValue`, `_ObjGeneric` for subclass of `FieldGeneric`, and `_ObjField` for subclass of `Field`. When using the decorator `field_type`, you may name your `FieldValue` subclass without the `..Value` suffix. When using the builder function `create_field_type`, add the `..Value` suffix on the subclass of `FieldValue`._

## License

This project is licensed under the MIT License — see the LICENSE file for details.
