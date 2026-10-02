"""Regression for HTML-lowercased inline-XBRL dimension members."""

import unittest

from lxml import html

from tools.sec_train_next_four_review_v1 import _period


class DimensionContextTests(unittest.TestCase):
    def test_html_case_and_two_axis_scope(self):
        document = html.fromstring("""
          <html><body>
            <xbrli:context id="pension">
              <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant>
              </xbrli:period>
              <xbrldi:explicitMember dimension="us-gaap:RetirementPlanTypeAxis">
                us-gaap:PensionPlansDefinedBenefitMember
              </xbrldi:explicitMember>
              <xbrldi:explicitMember dimension="srt:StatementGeographicalAxis">
                country:US
              </xbrldi:explicitMember>
            </xbrli:context>
            <xbrli:context id="consolidated">
              <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant>
              </xbrli:period>
            </xbrli:context>
          </body></html>
        """)
        scoped = _period(document, "pension")
        plain = _period(document, "consolidated")
        self.assertEqual(scoped["dimension_member_count"], 2)
        self.assertEqual([row["member"] for row in scoped["dimension_members"]],
                         ["us-gaap:PensionPlansDefinedBenefitMember", "country:US"])
        self.assertEqual(plain["dimension_member_count"], 0)
        self.assertEqual(plain["dimension_members"], [])


if __name__ == "__main__":
    unittest.main()
