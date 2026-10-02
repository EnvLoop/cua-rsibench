import unittest

from tools.audit_magento_v2_modal_stop_v1 import is_premutation_modal_timeout


class ModalStopClassificationTests(unittest.TestCase):
    def test_requires_specific_pre_edit_release_notification_obstruction(self):
        trace = (b"line 50, in read_quote_in_gui\n"
                 b"playwright._impl._errors.TimeoutError: "
                 b"Locator.click: Timeout 60000ms exceeded.\n"
                 b"admin__form-loading-mask\n"
                 b"modal-popup confirm _show intercepts pointer events")
        self.assertTrue(is_premutation_modal_timeout(trace))
        for marker in (
            b"line 50, in read_quote_in_gui",
            b"admin__form-loading-mask",
            b"modal-popup confirm _show",
        ):
            self.assertFalse(
                is_premutation_modal_timeout(trace.replace(marker, b"other")),
                marker,
            )

    def test_generic_timeout_or_modal_is_not_this_failure(self):
        self.assertFalse(is_premutation_modal_timeout(
            b"Locator.click: Timeout 60000ms exceeded."))
        self.assertFalse(is_premutation_modal_timeout(
            b"modal-popup confirm _show intercepts pointer events"))


if __name__ == "__main__":
    unittest.main()
