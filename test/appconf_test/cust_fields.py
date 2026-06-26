from django_dataclassconf.fields import Field, FieldGeneric, FieldValue
import warnings
import typing


class DeprecatedValue(FieldValue):
    def __init__(self, value: typing.Any, inner_type: typing.Type[typing.Any]):
        self.value = value
        self.inner_type: typing.Type[typing.Any] = inner_type

    def validate(self):
        if not isinstance(self.value, self.inner_type):
            raise TypeError(f'Instance {self.value} is not of type {self.inner_type.__name__}')
        warnings.warn(f'This setting is depricated', DeprecationWarning, stacklevel = 2)
    
    def resolve(self):
        return self.value
    
    def __repr__(self):
        return repr(self.value)
    
    def __eq__(self, value):
        if isinstance(value, DeprecatedValue):
            return (
                self.value == value.value 
                and self.inner_type == value.inner_type
            )
        
        if isinstance(value, self.inner_type):
            return self.value == value
        return NotImplemented
    
    def __hash__(self):
        return hash((repr(self.value), repr(self.inner_type)))


class DeprecatedGeneric(FieldGeneric):
    def __repr__(self):
        return f'Deprecated[{self.__inner_type__}]'

    def instanciate(self, value):
        return DeprecatedValue(value, self.__inner_type__)


if typing.TYPE_CHECKING:
    Deprecated = DeprecatedValue

else:
    class Deprecated(Field):
        _generic_class = DeprecatedGeneric