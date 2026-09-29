"""Independent SEC parser boundary checks without private issuer fixtures."""

from __future__ import annotations

from decimal import Decimal
import unittest

from lxml import html

from tools import sec_next_four_second_person_audit_v1 as review


class ContextTests(unittest.TestCase):
    def test_html_lowercase_explicitmember_is_counted_and_scoped(self):
        tree = html.fromstring("""
          <html><body>
            <xbrli:context id="c1"><xbrli:entity>
              <xbrli:identifier>0000012345</xbrli:identifier>
              <xbrli:segment>
                <xbrldi:explicitMember>us-gaap:PensionPlansDefinedBenefitMember</xbrldi:explicitMember>
                <xbrldi:explicitMember>country:US</xbrldi:explicitMember>
              </xbrli:segment>
            </xbrli:entity><xbrli:period>
              <xbrli:startDate>2025-01-01</xbrli:startDate>
              <xbrli:endDate>2025-12-31</xbrli:endDate>
            </xbrli:period></xbrli:context>
          </body></html>""")
        context = review.contexts(tree)["c1"]
        self.assertEqual(len(tree.xpath(
            './/*[contains(name(),"explicitMember")]')), 0)
        self.assertEqual(len(context["members"]), 2)
        self.assertTrue(review.context_matches(
            context, year=2025, kind="duration", scope="us_pension"))
        self.assertFalse(review.context_matches(
            context, year=2025, kind="duration", scope="pension"))
        self.assertFalse(review.context_matches(
            context, year=2025, kind="duration", scope="bank"))

    def test_signed_outflow_dash_and_nil_remain_distinct(self):
        nodes = html.fromstring("""
          <div>
            <ix:nonFraction unitRef="usd" scale="6">437</ix:nonFraction>
            <ix:nonFraction unitRef="usd" scale="6">—</ix:nonFraction>
            <ix:nonFraction unitRef="usd" xsi:nil="true"></ix:nonFraction>
          </div>""").xpath('.//*[name()="ix:nonfraction"]')
        self.assertEqual(review.decode(nodes[0], outflow=True),
                         (Decimal(-437), "reported"))
        self.assertEqual(review.decode(nodes[1]),
                         (Decimal(0), "disclosed_dash"))
        self.assertEqual(review.decode(nodes[2]),
                         (None, "not_separately_reported"))

    def test_bank_companyfacts_requires_same_accession_full_year(self):
        facts = {"facts": {"us-gaap": {"InterestExpenseOperating": {
            "units": {"USD": [
                {"accn": "different", "form": "10-K",
                 "start": "2025-01-01", "end": "2025-12-31", "val": 123_000_000},
                {"accn": "exact", "form": "10-K",
                 "start": "2025-07-01", "end": "2025-12-31", "val": 123_000_000},
            ]}}}}}
        with self.assertRaisesRegex(ValueError, "full_period_mismatch"):
            review.companyfacts_bank_match(
                facts, "exact", 2025, "InterestExpenseOperating",
                Decimal(123), "duration")
        facts["facts"]["us-gaap"]["InterestExpenseOperating"]["units"]["USD"].append(
            {"accn": "exact", "form": "10-K", "start": "2025-01-01",
             "end": "2025-12-31", "val": 123_000_000})
        review.companyfacts_bank_match(
            facts, "exact", 2025, "InterestExpenseOperating",
            Decimal(123), "duration")


if __name__ == "__main__":
    unittest.main()
