from django_dataclassconf.fields import Field, FieldGeneric, FieldValue, field_type
import warnings
import typing
import re


class DeprecatedValue(FieldValue):
    def validate(self):
        if not isinstance(self.value, self.inner_type):
            raise TypeError(f'Instance {self.value} is not of type {self.inner_type.__name__}')
        warnings.warn(f'This setting is depricated', DeprecationWarning, stacklevel = 2)

class _DeprecatedGeneric(FieldGeneric):
    _value_class = DeprecatedValue

class _DeprecatedField(Field):
    _generic_class = _DeprecatedGeneric

if typing.TYPE_CHECKING:
    Deprecated = DeprecatedValue

else:
    Deprecated = _DeprecatedField


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
    