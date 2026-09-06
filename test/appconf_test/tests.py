from django.test import SimpleTestCase, override_settings
from django.contrib.auth.models import User

from django_dataclassconf.core import BaseConfig, config_loader
from django_dataclassconf.fields import (
    FieldGeneric, 
    FieldValue, 
    Importable, 
    Field, 
    Path,
)

from dacite.exceptions import WrongTypeError

import pathlib
import typing

from appconf_test.models import UserSubclass
from appconf_test.config import (
    Test2Config,
    new_as_dict,
    TestConfig,
    Renderer,
)

from appconf_test.cust_fields import Email, DeprecatedValue


class NativeFieldTests(SimpleTestCase):
    # Importable
    def test_importable_field_is_generated(self):
        self.assertTrue(issubclass(Importable, Field))

    def test_importable_is_parameterized(self):
        possible_inner_types = [
            int,
            typing.Callable, 
            typing.Type,
            typing.Callable[[str], bool],
        ]

        for possible_field_type in possible_inner_types:
            field_type = Importable[possible_field_type]
            self.assertIsInstance(field_type, FieldGeneric)
            self.assertIs(field_type.__origin__, Importable)
            self.assertIs(field_type.__inner_type__, possible_field_type)

    def test_valid_import(self):
        importables = [
            (TestConfig, 'appconf_test.config.configuration'), # import var
            (typing.Type[BaseConfig], 'appconf_test.config.TestConfig'), # import class
            (typing.Type[User], 'appconf_test.UserSubclass'), # import Model
            (typing.Callable[[str], bool], 'appconf_test.config.foo_bar'), # import function
        ]

        for (inner_type, value) in importables:
            importable: Importable = Importable[inner_type].instantiate(value)
            self.assertTrue(importable.is_valid)

    def test_invalid_import(self):
        importables = [
            (TestConfig, 'appconf_test.config.non_existent'), # import var
            (typing.Type[BaseConfig], 'appconf_test.config.NonExistentConfig'), # import class
            (typing.Type[User], 'appconf_test.NotUserSubclass'), # import Model
            (typing.Callable[[str], bool], 'appconf_test.config.not_foo_bar'), # import function
        ]
        
        for (inner_type, value) in importables:
            importable: Importable = Importable[inner_type].instantiate(value)
            with self.assertRaises((ValueError, AttributeError, ImportError, TypeError)):
                importable.validate()

    def test_importable_equality(self):
        importables = [
            (TestConfig, 'appconf_test.config.configuration'), # import var
            (typing.Type[BaseConfig], 'appconf_test.config.TestConfig'), # import class
            (typing.Type[User], 'appconf_test.UserSubclass'), # import Model
            (typing.Callable[[str], bool], 'appconf_test.config.foo_bar'), # import function
        ]

        for (inner_type, value) in importables:
            importable: Importable = Importable[inner_type].instantiate(value)
            self.assertEqual(importable, Importable[inner_type].instantiate(value))
            self.assertEqual(importable, value)
            self.assertNotEqual(importable, 'this_is.not.Importable')

    # Path
    def test_path_field_is_generated(self):
        self.assertTrue(issubclass(Path, Field))

    @property
    def _path_generic(self):
        return Path[str]

    def _create_path_value(self, path_str: str) -> Path:
        return self._path_generic.instantiate(path_str)

    def test_path_is_parameterized(self):
        field_type = self._path_generic
        self.assertIsInstance(field_type, FieldGeneric)
        self.assertIs(field_type.__origin__, Path)
        self.assertIs(field_type.__inner_type__, str)

    def test_valid_path(self):
        path_str = '/absolute/path/'
        path_value = self._create_path_value(path_str)
        self.assertTrue(path_value.is_valid)
        self.assertEqual(path_value.resolve(), pathlib.Path(path_str))

    def test_invalid_path(self):
        path_str = 123
        path_value = self._create_path_value(path_str)
        self.assertFalse(path_value.is_valid)
        with self.assertRaises(TypeError):
            path_value.resolve()

    def test_path_equality(self):
        path_value = self._create_path_value('/a/b')
        self.assertEqual(path_value, '/a/b')
        self.assertEqual(path_value, self._create_path_value('/a/b'))
        self.assertNotEqual(path_value, '/a/c')
        self.assertNotEqual(path_value, self._create_path_value('/a/c'))


class CustomFieldTests(SimpleTestCase):
    # Deprecation
    def test_deprecated_field_raise_warning(self):
        deprecated = DeprecatedValue(67, int)
        with self.assertWarns(DeprecationWarning):
            deprecated.validate()

    def test_deprecated_field_type_mismatch(self):
        deprecated = DeprecatedValue('six-seven', int)
        with self.assertRaises(TypeError):
            deprecated.validate()

    # Email
    @property
    def _email_generic(self):
        return Email[str]

    def _create_email_value(self, email_str: str) -> Email:
        return self._email_generic.instantiate(email_str)

    def test_email_field_is_generated(self):
        self.assertTrue(issubclass(Email, Field))
    
    def test_email_field_is_parameterized(self):
        field_type = self._email_generic
        self.assertIsInstance(field_type, FieldGeneric)
        self.assertIs(field_type.__origin__, Email)
        self.assertIs(field_type.__inner_type__, str)

    def test_valid_email(self):
        email = self._create_email_value("admin_project@domain.com")
        self.assertTrue(email.is_valid)
        self.assertEqual(email.resolve(), "admin_project@domain.com")

    def test_invalid_email(self):
        email = self._create_email_value("not-an-email")
        with self.assertRaises(ValueError) as context:
            email.validate()
        self.assertEqual(str(context.exception), "Email value not-an-email is not a valid email address")

    def test_email_equality(self):
        email = self._create_email_value("admin_project@domain.com")
        self.assertEqual(email, self._create_email_value("admin_project@domain.com"))
        self.assertEqual(email, "admin_project@domain.com")
        self.assertNotEqual(email, "other@domain.com")


class DataclassConfSignalTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.config = TestConfig()
        config_loader.subscribe(self.config)

    @override_settings(TEST = {'PROJECT_EMAIL': 'another_email@next.ph'})
    def test_email_config_resolve(self):
        self.assertEqual(self.config.PROJECT_EMAIL.resolve(), 'another_email@next.ph')

    @override_settings(TEST_MAX_RETRIES = 24)
    def test_flat_config(self):
        self.assertEqual(self.config.MAX_RETRIES, 24)

    @override_settings(TEST = {'DEFAULT_PATH': '/a/path/to/somewhere'})
    def test_block_config(self):
        self.assertEqual(self.config.DEFAULT_PATH.resolve(), '/a/path/to/somewhere')

    @override_settings(TEST = {'RENDERER': {'refresh_rate': 24}})
    def test_nested_config(self):
        self.assertEqual(self.config.RENDERER.refresh_rate, 24)
        self.assertIsInstance(self.config.RENDERER, Renderer)

    def test_invalid_type_config(self):
        with self.assertRaises(WrongTypeError) as error:
            with override_settings(TEST_MAX_RETRIES = '1,000'):
                pass
        self.assertIn('MAX_RETRIES', str(error.exception))

    def test_importable_fields_are_field_value_subclass_after_subscribe(self):
        fvs = [
            self.config.CONFIG_SUBCLASS,
            self.config.CONFIG_INSTANCE, 
            self.config.USER_MODEL, 
            self.config.DATACLASS_AS_DICT,
        ]

        for fv in fvs:
            self.assertIsInstance(fv, FieldValue)

    def test_importable_value_stores_originalimport_string(self):
        importables = [
            (self.config.CONFIG_SUBCLASS, 'appconf_test.config.TestConfig'),
            (self.config.CONFIG_INSTANCE, 'appconf_test.config.configuration'), 
            (self.config.USER_MODEL, 'auth.User'), 
            (self.config.DATACLASS_AS_DICT, 'dataclasses.dataclass.asdict'),
        ]

        for (fv, value) in importables:
            self.assertEqual(fv.value, value)

    def test_resolve_config_subclass(self):
        resolved = self.config.CONFIG_SUBCLASS.resolve()
        self.assertIs(resolved, TestConfig)
        self.assertTrue(issubclass(resolved, BaseConfig))

    def test_resolve_config_instance(self):
        from appconf_test.config import configuration
        resolved = self.config.CONFIG_INSTANCE.resolve()
        self.assertIs(resolved, configuration)
        self.assertIsInstance(resolved, BaseConfig)

    def test_resolve_callable_via_override(self):
        with override_settings(TEST_DATACLASS_AS_DICT = 'appconf_test.config.new_as_dict'):
            resolved = self.config.DATACLASS_AS_DICT.resolve()
            self.assertIs(resolved, new_as_dict)
            self.assertTrue(callable(resolved))

    def test_resolve_user_subclass_via_override(self):
        with override_settings(TEST_USER_MODEL='appconf_test.models.UserSubclass'):
            resolved = self.config.USER_MODEL.resolve()
            self.assertIs(resolved, UserSubclass)
            self.assertTrue(issubclass(resolved, User))

    @override_settings(TEST_USER_MODEL = 'nonexistent.User')
    def test_resolve_bad_module_raises_import_error(self):
        with self.assertRaises(ImportError):
            self.config.USER_MODEL.resolve()

    def test_resolve_non_module_segment_raises_import_error(self):
        with self.assertRaises(ImportError):
            self.config.DATACLASS_AS_DICT.resolve()

    def test_override_replaces_importable_value(self):
        original_iv = self.config.CONFIG_SUBCLASS
        with override_settings(TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config'):
            updated_iv = self.config.CONFIG_SUBCLASS
            self.assertIsInstance(updated_iv, FieldValue)
            self.assertEqual(updated_iv.value, 'appconf_test.config.Test2Config')
            self.assertIsNot(updated_iv, original_iv)

        self.assertEqual(self.config.CONFIG_SUBCLASS.value, 'appconf_test.config.TestConfig')

    def test_override_new_importable_value_resolves_correctly(self):
        with override_settings(TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config'):
            resolved = self.config.CONFIG_SUBCLASS.resolve()
            self.assertIs(resolved, Test2Config)

    def test_non_importable_field_unaffected_by_importable_override(self):
        with override_settings(TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config'):
            self.assertEqual(self.config.MAX_RETRIES, 5)
            self.assertEqual(self.config.DEFAULT_PATH.resolve(), '/root/default/path/')

    def test_importable_and_plain_field_override_together(self):
        with override_settings(
            TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config',
            TEST_MAX_RETRIES = 99,
        ):
            self.assertEqual(self.config.MAX_RETRIES, 99)
            self.assertEqual(
                self.config.CONFIG_SUBCLASS.value,
                'appconf_test.config.Test2Config',
            )

    def test_field_deprecation_subclass(self):
        with self.assertWarns(DeprecationWarning):
            self.config.DEFAULT_PATH.validate()

    def test_path_field_is_path_value_after_subscribe(self):
        self.assertIsInstance(self.config.MEDIA_ROOT, FieldValue)

    def test_path_resolve_returns_pathlib_path(self):
        resolved = self.config.MEDIA_ROOT.resolve()
        self.assertIsInstance(resolved, pathlib.Path)
        self.assertEqual(resolved, pathlib.Path('/root/default/path/'))

    def test_path_override_via_flat_setting(self):
        with override_settings(TEST_MEDIA_ROOT='/custom/media/root'):
            self.assertIsInstance(self.config.MEDIA_ROOT, FieldValue)
            self.assertEqual(
                self.config.MEDIA_ROOT.resolve(),
                pathlib.Path('/custom/media/root'),
            )
        self.assertEqual(
            self.config.MEDIA_ROOT.resolve(),
            pathlib.Path('/root/default/path/'),
        )
