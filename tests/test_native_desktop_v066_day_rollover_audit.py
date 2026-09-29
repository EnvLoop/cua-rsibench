"""The date amendment scopes one validated LibreOffice registry field."""

from __future__ import annotations

import unittest

from native_desktop_factory.v066_day_rollover_audit import _tip_day
from tests.test_native_desktop_v066_profile_scope_analysis import registry


class DayRolloverAuditTests(unittest.TestCase):
    def test_one_day_mask_preserves_every_other_registry_field(self):
        old, old_mask = _tip_day(registry(tip_day="20724"))
        new, new_mask = _tip_day(registry(tip_day="20725"))
        self.assertEqual((old, new), (20724, 20725))
        self.assertEqual(old_mask, new_mask)
        changed = registry(tip_day="20725", setting="8")
        self.assertNotEqual(old_mask, _tip_day(changed)[1])

    def test_malformed_or_duplicate_day_is_rejected(self):
        for raw in (registry(tip_day="bad"),
                    registry(tip_day="10000"),
                    registry(tip_day="20725").replace(
                        b'</items>',
                        b'<item oor:path="/org.openoffice.Office.Common/Misc">'
                        b'<prop oor:name="LastTipOfTheDayShown">'
                        b'<value>20725</value></prop></item></items>')):
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(ValueError):
                    _tip_day(raw)


if __name__ == "__main__":
    unittest.main()
