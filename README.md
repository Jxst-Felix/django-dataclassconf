# Django DataclassConf

[![CI](https://github.com/Jxst-Felix/django-dataclassconf/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Jxst-Felix/django-dataclassconf/actions/workflows/pipeline.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/django-dataclassconf?style=flat-square&logo=pypi&logoColor=white&color=blue)](https://pypi.org/project/django-dataclassconf/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)

A Django configuration management package built around Python dataclasses.

`django-dataclassconf` provides a structured and type-aware way to manage Django settings. Instead of accessing configuration through Django's global settings object, you can define dedicated dataclass configurations with explicit fields, defaults, and type annotations.

Powered by [`dacite`](https://github.com/konradhalas/dacite), it handles configuration loading, type validation, and conversion while keeping your settings organized, predictable, and easy to work with.

## But Why?

- **Structured Configuration**: Organize related settings into dedicated dataclasses instead of relying on scattered references to Django's global settings object.

- **Type Safety and Validation**: Define expected types through Python annotations and validate incoming configuration values, catching invalid settings early.

- **IDE Support**: Take advantage of native autocompletion, type information, and static analysis when accessing configuration fields.

- **Flexible Configuration Sources**: Support both flat Django settings and dictionary-based configuration blocks, allowing you to organize settings according to your project's needs.

- **Customizable Configuration Behavior**: Use configuration metadata to control settings namespaces, validation fallbacks, external configuration exports, and deprecated settings.

- **Dynamic Settings Updates**: Automatically respond to Django settings changes, including settings overrides during tests, while maintaining the same configuration instances.

- **Extensible Field Types**: Define custom field types with validation and transformation logic, or use built-in types for common configuration values such as import paths and filesystem paths. _(This is currently **WIP** since I'm not able to touch this project much due to academics 🥲)_

## Installation

To use _django-dataclassconf_, you can install it via **pip**:

```shell
pip install django-dataclassconf
```

## Usage

### 1. Define Your Configuration Dataclass

Create a file named `config.py` (or any name you prefer tbh) within your application or package.
Inherit from `BaseConfig` and define your variables.

```python
from dataclasses import dataclass
from django_dataclassconf.core import BaseConfig, config_loader

@dataclass
class MyPackageConfig(BaseConfig):
    DOCUMENTS_ROOT_PATH: str = '/the/default/path/'
    MAX_FILE_SIZE: int = 10000

    class Meta:
        prefix = 'MY_PACKAGE'

package_config = MyPackageConfig()
```

> _**Note:** Make sure to instantiate your config class for it to properly catch the settings and you can then access those settings via its instance._

### 2. Subscribe to the Configuration Loader

> _**Note:** This step is optional ever since version **0.6.0** because a self-discovery mechanism was added in `BaseConfig`. You only need to instantiate your dataclass configuration class._

For your dataclass to grab configuration data from Django's `settings.py` on startup and capture updates during tests, subscribe your instance into `config_loader` inside your app's initialization hook:

```python
# my_app/apps.py
class MyAppConfig(AppConfig):
    name = 'my_app'

    def ready(self):
        from django_dataclassconf.core import config_loader
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

## Configuration Metadata

_Introduced in version 0.6.0._

You can customize the behavior of your configuration class by defining an inner `Meta` class. The `Meta` class provides configuration options that control how `BaseConfig` loads, validates, and handles your settings.

```python
from dataclasses import dataclass
from django_dataclassconf.core import BaseConfig

@dataclass
class MyPackageConfig(BaseConfig):
    MAX_FILE_SIZE: int = 10000

    class Meta:
        prefix = 'MY_PACKAGE'
        use_defaults = False
        export_to_config = None
        deprecated = []
```

### Available Options

| Attribute | Default | Description |
| --- | --- | --- |
| `prefix` | `''` | The prefix used to identify settings belonging to this configuration. |
| `use_defaults` | `False` | Whether to fall back to dataclass defaults when incoming settings fail validation. |
| `export_to_config` | `None` | An optional configuration target where loaded settings will also be exported. |
| `deprecated` | `[]` | A collection of settings marked as deprecated. |
| `auto_resolve` | `False` | Whether settings that are field types must have a fail-fast behavior. |

### Prefix

The `prefix` attribute determines the namespace used when retrieving settings from Django's settings module.

> _This used to be the `_prefix` attribute of the configuration class in earlier versions of **django-dataclassconf**._

For example, with `prefix = 'MY_PACKAGE'`, the configuration loader can retrieve settings from both flat and dictionary-based configurations:

```python
# settings.py

MY_PACKAGE_MAX_FILE_SIZE = 20000

# Alternatively:
MY_PACKAGE = {
    'MAX_FILE_SIZE': 20000,
}
```

### Use Defaults

By default, invalid configuration values raise an exception during validation. Setting `use_defaults = True` allows the configuration loader to fall back to the dataclass field's default value when an incoming value fails validation.

```python
@dataclass
class MyPackageConfig(BaseConfig):
    MAX_FILE_SIZE: int = 10000
    ENABLE_PREVIEWS: bool = True

    class Meta:
        prefix = 'MY_PACKAGE'
        use_defaults = True
```

Given the following Django settings:

```python
# settings.py

MY_PACKAGE = {
    'MAX_FILE_SIZE': 'invalid',
    'ENABLE_PREVIEWS': False,
}
```

The resulting configuration will use the default value of `MAX_FILE_SIZE` while retaining the valid value of `ENABLE_PREVIEWS`.

```python
configuration = MyPackageConfig()

print(configuration.MAX_FILE_SIZE)  # 10000
print(configuration.ENABLE_PREVIEWS) # False
```

### Export to Configuration

The `export_to_config` attribute allows loaded settings to be exported to another configuration target. This is useful when integrating with third-party packages that expect their configuration to be available through a separate object or class.

```python
from rest_framework.settings import api_settings

@dataclass
class MyPackageConfig(BaseConfig):
    PAGE_SIZE: int = 20

    class Meta:
        prefix = 'MY_PACKAGE'
        export_to_config = api_settings
```

The configuration loader exports the loaded settings to the specified target after successful validation of the dataclass configuration.

The target may be a dictionary, a class, or an object instance. Exported values are assigned to the corresponding attributes or dictionary keys.

### Deprecated Settings

The `deprecated` attribute allows you to identify settings that are deprecated. This can be used to notify users when they continue to configure settings that are scheduled for removal.

```python
@dataclass
class MyPackageConfig(BaseConfig):
    NEW_SETTING: str = 'default'

    class Meta:
        prefix = 'MY_PACKAGE'
        deprecated = ('OLD_SETTING',)
```

When a deprecated setting is encountered, the configuration loader can issue a deprecation warning to notify users that they should migrate to the replacement setting or stop using the deprecated setting.

```python
from dataclasses import dataclass, field
from django_dataclassconf.core import BaseConfig, config_loader

@dataclass
class DocumentPreview:
    preview_page_count: int = 10
    strip_cover_page: bool = False

@dataclass
class MyPackageConfig(BaseConfig):
    DOCUMENTS_ROOT_PATH: str = '/the/default/path/'
    PREVIEW: DocumentPreview = field(default_factory=DocumentPreview)

    class Meta:
        prefix = 'MY_PACKAGE'

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

## Configuration Fields

### Computed Fields

---

Computed fields allow you to define custom processing logic for individual configuration fields. They are useful when a configuration value needs to be transformed, normalized, or otherwise processed before it is applied to your configuration instance.

To define a computed field, create a method following the `get_FIELDNAME` naming convention, where `FIELDNAME` corresponds to the configuration field's name (case-insensitively).

#### Defining Computed Fields

Consider the following example:

```python
@dataclass
class AppConfig(BaseConfig):
    MAX_RETRIES: int = 5
    DEBUG: bool = False

    def get_max_retries(self, value: int) -> int:
        return max(0, value)
```

The `get_max_retries` method is automatically associated with the `MAX_RETRIES` field. Whenever the field is processed, the method receives its current value and returns the value that will be used by the configuration instance.

For example, if `MAX_RETRIES` is assigned a negative value through Django settings, the computed field ensures that the resulting value is never below zero.

### Considerations

- **Naming convention:** Computed field methods must follow the `get_FIELDNAME` naming convention. The field name is matched without regard to case.
- **Method signature:** A computed field method should accept the field's current value as its argument and return the processed value.
- **Field-specific processing:** Each computed field operates on its corresponding field value. It does not automatically receive the entire configuration instance or derive its value from other configuration fields.
- **Exceptions:** Exceptions raised during processing are propagated through the configuration processing flow. Ensure that your methods handle invalid input appropriately when necessary.

Computed fields provide a convenient way to encapsulate field-specific transformations directly within your configuration class, keeping configuration definitions expressive and their processing logic organized.

> _**Note:** Every return value of computed fields are still subject to type validation and coercion which will be handled automatically by `dacite`._

### Built-in Field Types

---

This package makes use of wrapper classes that transforms a raw input into a desired object for instant use instead of manually converting or transforming the setting value into a workable object.

In general, wrappers doesn't have a fail-fast behavior and its `resolve` method must be called each time the workable object is in demand which might raise an exception if the raw setting value does not pass the validation and conversion/transformation.

For field types to have a fail-fast behavior, set `auto_resolve` to `True` in the meta class of your configuration class.

#### **`Importable`**

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

    class Meta:
        prefix = 'MY_PACKAGE'

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

#### **`Path`**

For settings that hold a filesystem path, annotate them with `Path` from `fields/types.py`. The raw value may be a `str` or any `os.PathLike`; calling `.resolve()` validates it and returns a `pathlib.Path`.

```python
from dataclasses import dataclass
from django_dataclassconf.fields import Path

@dataclass
class MyConfig(BaseConfig):
    DOCUMENTS_ROOT: Path[str] = '/the/default/path/'

    class Meta:
        prefix = 'MY_PACKAGE'

configuration = MyConfig()
```

Call `.resolve()` to get the `pathlib.Path`:

```python
# Returns pathlib.Path('/the/default/path/')
root = configuration.DOCUMENTS_ROOT.resolve()

document = root / 'report.pdf'
```

> **Note:** `Path` intentionally shares its name with `pathlib.Path`. Import it under an alias (e.g. `from django_dataclassconf.fields import Path as PathField`) if you also need `pathlib.Path` in the same module.

### Custom Field Types

---

_Introduced in version 0.3.0._

You can define your own field types with custom validation and transformation logic by two ways.

#### **Decorator**

**Introduced in _version 0.5.0_**, a simple way to customize a field type is by using a builder function:

- **`field_type`** — a decorator that automatically subclasses `FieldGeneric` and `Field`.

- **`create_field_type`** — a function that performs the same thing as `field_type`.

#### **Subclasses**

**Introduced in _version 0.3.0_**, by subclassing three base classes from `fields/bases.py`: `FieldValue`, `FieldGeneric`, and `Field`.

Each custom field type requires three pieces:

- **`FieldValue` subclass** — holds the raw value, implements `validate()` (raises on invalid input) and `resolve()` (returns the final value).
- **`FieldGeneric` subclass** — the runtime object produced by `YourField[T]`. Implements `instanciate()` to construct the `FieldValue`.
- **`Field` subclass** — the annotation class used in dataclass definitions. Points at the `FieldGeneric` via `_generic_class`.

## Fail-Fast Field Types

Whenever you set the `auto_resolve` attribute to `True` in the Meta class of you configuration class, fail-fast behavior will be enforced in all of the field types in your configuration enabling you to catch exceptions upon instantiation of your configuration class.

```python
@dataclass
class MyPackageConfig(BaseConfig):
    USER_SERIALIZER: Importable[typing.Type[Serializer]] = 'path/to/serializer_class'

    class Meta:
        prefix = 'MY_PACKAGE'
        auto_resolve = True

config = MyPackageConfig()
```

Upon instantiation of your config class, the field type will automatically resolve the raw setting value. Introduced in version _**0.8.0**_, if your `auto_resolve` is `True`, you may access the output of `resolve` method like this:

```python
config.USER_SERIALIZER # provides the output of `resolve`
```

Otherwise, if your `auto_resolve` is `False`, you can only access the output of `resolve` method by invoking method.

```python
config.USER_SERIALIZER.resolve()
```

## Configuration Field Examples

### Computed Field Examples

Computed fields are particularly useful for applying field-specific rules without having to implement custom logic in the configuration loading process.

#### **Value normalization**

```python
@dataclass
class AppConfig(BaseConfig):
    APP_NAME: str = 'My Application'

    def get_app_name(self, value: str) -> str:
        return value.strip().lower()
```

#### **Enforcing value constraints**

```python
@dataclass
class AppConfig(BaseConfig):
    MAX_CONNECTIONS: int = 10

    def get_max_connections(self, value: int) -> int:
        return max(1, min(value, 100))
```

#### **Custom transformations**

```python
@dataclass
class AppConfig(BaseConfig):
    ALLOWED_HOSTS: list[str] = None

    def get_allowed_hosts(self, value: list[str]) -> list[str]:
        return [host.lower().strip() for host in value]
```

### Custom Field Type Examples

#### **Simple Example: Email Field (Decorator)**

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

    class Meta:
        prefix = 'MY_APP'
```

Call `.resolve()` to get the validated value, or check `.is_valid` if you want a boolean without raising:

```python
# Raises ValueError if the configured value is not a valid email address
admin_email = my_config.ADMIN_EMAIL.resolve()

# Non-raising check
if my_config.ADMIN_EMAIL.is_valid:
    ...
```

#### **Advanced Example: Deprecated Field (Subclass)**

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
