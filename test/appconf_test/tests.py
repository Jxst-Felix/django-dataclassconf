from django.test import SimpleTestCase, override_settings
from django_dataclassconf.conf import config_loader

from dacite.exceptions import WrongTypeError

from appconf_test.config import TestConfig, Renderer


class DataclassConfSignalTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = TestConfig()
        config_loader.subscribe(cls.config)

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