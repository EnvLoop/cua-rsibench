import unittest

from tools.retire_magento_v2_retry_runtime_failure_v1 import (
    is_missing_playwright_before_gui,
)


class RuntimeFailureClassificationTests(unittest.TestCase):
    def test_accepts_only_explicit_pre_gui_import_failure(self):
        traceback = (
            b"File 'qualify_magento_original_catalog_v1.py', line 160, in run\n"
            b"from playwright.async_api import async_playwright\n"
            b"ModuleNotFoundError: No module named 'playwright'\n"
        )
        self.assertTrue(is_missing_playwright_before_gui(traceback))
        self.assertFalse(is_missing_playwright_before_gui(
            traceback.replace(b"ModuleNotFoundError", b"RuntimeError")))
        self.assertFalse(is_missing_playwright_before_gui(
            traceback.replace(b"from playwright.async_api", b"from other")))


if __name__ == "__main__":
    unittest.main()
