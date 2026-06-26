from django.test import SimpleTestCase, override_settings
from django.contrib.auth.models import User

from django_dataclassconf.conf import BaseConfig, config_loader
from django_dataclassconf.fields import ImportableValue

from dacite.exceptions import WrongTypeError

from appconf_test.config import TestConfig, Test2Config, Renderer, new_as_dict
from appconf_test.models import UserSubclass


class DataclassConfSignalTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.config = TestConfig()
        config_loader.subscribe(self.config)

    @override_settings(TEST_MAX_RETRIES = 24)
    def test_flat_config(self):
        self.assertEqual(self.config.MAX_RETRIES, 24)

    @override_settings(TEST = {'DEFAULT_PATH': '/a/path/to/somewhere'})
    def test_block_config(self):
        self.assertEqual(self.config.DEFAULT_PATH, '/a/path/to/somewhere')

    @override_settings(TEST = {'RENDERER': {'refresh_rate': 24}})
    def test_nested_config(self):
        self.assertEqual(self.config.RENDERER.refresh_rate, 24)
        self.assertIsInstance(self.config.RENDERER, Renderer)

    def test_invalid_type_config(self):
        with self.assertRaises(WrongTypeError) as error:
            with override_settings(TEST_MAX_RETRIES = '1,000'):
                pass
        self.assertIn('MAX_RETRIES', str(error.exception))

    def test_importable_fields_are_importable_value_after_subscribe(self):
        self.assertIsInstance(self.config.CONFIG_SUBCLASS, ImportableValue)
        self.assertIsInstance(self.config.CONFIG_INSTANCE, ImportableValue)
        self.assertIsInstance(self.config.USER_MODEL, ImportableValue)
        self.assertIsInstance(self.config.DATACLASS_AS_DICT, ImportableValue)

    def test_importable_value_stores_originalimport_string(self):
        self.assertEqual(self.config.CONFIG_SUBCLASS.import_str, 'appconf_test.config.TestConfig')
        self.assertEqual(self.config.CONFIG_INSTANCE.import_str, 'appconf_test.config.configuration')
        self.assertEqual(self.config.USER_MODEL.import_str, 'auth.User')
        self.assertEqual(self.config.DATACLASS_AS_DICT.import_str, 'dataclasses.dataclass.asdict')

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

    def test_resolve_type_mismatch_subclass_raises_type_error(self):
        iv = ImportableValue('builtins.str', type[BaseConfig])
        with self.assertRaises(TypeError) as ctx:
            iv.resolve()
        self.assertIn('subclass', str(ctx.exception))

    def test_resolve_instance_mismatch_raises_type_error(self):
        iv = ImportableValue('builtins.int', BaseConfig)
        with self.assertRaisesRegex(
            TypeError, r'Resolving builtins.int: expected a subclass of'
        ):
            iv.resolve()

    def test_resolve_bad_attr_raises_import_error(self):
        iv = ImportableValue('builtins.NonExistent', object)
        with self.assertRaises(ImportError) as ctx:
            iv.resolve()
        self.assertIn('NonExistent', str(ctx.exception))

    def test_resolve_bare_name_raises_value_error(self):
        iv = ImportableValue('TestConfig', type[BaseConfig])
        with self.assertRaises((ValueError, ImportError)):
            iv.resolve()

    def test_override_replaces_importable_value(self):
        original_iv = self.config.CONFIG_SUBCLASS
        with override_settings(TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config'):
            updated_iv = self.config.CONFIG_SUBCLASS
            self.assertIsInstance(updated_iv, ImportableValue)
            self.assertEqual(updated_iv.import_str, 'appconf_test.config.Test2Config')
            self.assertIsNot(updated_iv, original_iv)

        self.assertEqual(self.config.CONFIG_SUBCLASS.import_str, 'appconf_test.config.TestConfig')

    def test_override_new_importable_value_resolves_correctly(self):
        with override_settings(TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config'):
            resolved = self.config.CONFIG_SUBCLASS.resolve()
            self.assertIs(resolved, Test2Config)

    def test_non_importable_field_unaffected_by_importable_override(self):
        with override_settings(TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config'):
            self.assertEqual(self.config.MAX_RETRIES, 5)
            self.assertEqual(self.config.DEFAULT_PATH, '/root/default/path/')

    def test_importable_and_plain_field_override_together(self):
        with override_settings(
            TEST_CONFIG_SUBCLASS = 'appconf_test.config.Test2Config',
            TEST_MAX_RETRIES = 99,
        ):
            self.assertEqual(self.config.MAX_RETRIES, 99)
            self.assertEqual(
                self.config.CONFIG_SUBCLASS.import_str,
                'appconf_test.config.Test2Config',
            )

    def test_importable_value_equality(self):
        a = ImportableValue('appconf_test.config.TestConfig', type[BaseConfig])
        b = ImportableValue('appconf_test.config.TestConfig', type[BaseConfig])
        self.assertEqual(a, b)

    def test_importable_value_inequality_different_path(self):
        a = ImportableValue('appconf_test.config.TestConfig', type[BaseConfig])
        b = ImportableValue('appconf_test.config.Test2Config', type[BaseConfig])
        self.assertNotEqual(a, b)

    def test_importable_value_is_hashable(self):
        iv = ImportableValue('appconf_test.config.TestConfig', type[BaseConfig])
        self.assertIsInstance(hash(iv), int)

    def test_importable_value_repr_contains_path(self):
        iv = ImportableValue('appconf_test.config.TestConfig', type[BaseConfig])
        self.assertIn('appconf_test.config.TestConfig', repr(iv))

    def test_field_deprecation_subclass(self):
        with self.assertWarns(DeprecationWarning):
            self.config.DEFAULT_PATH.validate()