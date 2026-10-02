"""Boundary checks for the additive SEC source-scope correction audit."""

from __future__ import annotations

import unittest

from lxml import html

from tools import sec_next_four_scope_correction_audit_v1 as correction


class CorrectionTests(unittest.TestCase):
    def test_only_member_list_and_count_changes_are_accepted(self):
        old = {"periods": [{"fields": {"sample": {
            "value": 123, "context_period": {
                "instant": "2025-12-31", "dimension_member_count": 0}}}}]}
        new = {"periods": [{"fields": {"sample": {
            "value": 123, "context_period": {
                "instant": "2025-12-31", "dimension_member_count": 1,
                "dimension_members": [{"axis": "type", "member": "pension"}]}}}}]}
        counts = correction.classify_json_changes(old, new)
        self.assertEqual(counts["member_lists_added"], 1)
        self.assertEqual(counts["direct_field_counts_changed"], 1)
        new["periods"][0]["fields"]["sample"]["value"] = 124
        with self.assertRaisesRegex(ValueError, "non_scope_review_value_changed"):
            correction.classify_json_changes(old, new)

    def test_lowercase_html_dimension_axis_and_member_are_recovered(self):
        tree = html.fromstring("""
          <div><xbrli:context id="x">
            <xbrldi:explicitMember dimension="plan:PlanAxis">plan:PensionMember</xbrldi:explicitMember>
            <xbrldi:explicitMember dimension="country:CountryAxis">country:US</xbrldi:explicitMember>
          </xbrli:context></div>""")
        context = tree.xpath('//*[name()="xbrli:context"]')[0]
        self.assertEqual(correction.original_members(context), [
            {"axis": "plan:PlanAxis", "member": "plan:PensionMember"},
            {"axis": "country:CountryAxis", "member": "country:US"},
        ])


if __name__ == "__main__":
    unittest.main()
