"""Prove HTML-lowercased XBRL dimensions bind the new TRAIN source scope."""

from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest import mock

from lxml import html

from tools import sec_train_remaining_four_review_v1 as current


class DimensionExtractorTest(unittest.TestCase):
    def test_html_lowercases_explicit_member_and_extracts_scope(self):
        tree = html.fromstring(
            '<html><xbrli:context id="c-test">'
            '<xbrli:scenario><xbrldi:explicitMember '
            'dimension="us-gaap:RetirementPlanTypeAxis">'
            'us-gaap:ForeignPlanMember</xbrldi:explicitMember>'
            '</xbrli:scenario></xbrli:context></html>')
        self.assertEqual(current._dimensions(tree, 'c-test'),
                         current.PENSION_DIMENSIONS[12])
        self.assertEqual(
            len(tree.xpath('.//*[contains(name(),"explicitMember")]')), 0)

    def test_typed_members_are_not_misclassified_as_dimensionless(self):
        tree = html.fromstring(
            '<html><xbrli:context id="c-test">'
            '<xbrli:scenario><xbrldi:typedMember dimension="example:Axis">'
            '<example:value>X</example:value>'
            '</xbrldi:typedMember></xbrli:scenario>'
            '</xbrli:context></html>')
        self.assertEqual(current._dimensions(tree, 'c-test'), [
            {'kind': 'typed', 'dimension': 'example:Axis', 'member': 'X'}])

    @unittest.skipUnless(os.getenv('SEC_TRAIN_REMAINING_RAW_ROOT'),
                         'private original SEC TRAIN source replay is opt-in')
    def test_saved_international_plan_and_afs_scope(self):
        root = Path(os.environ['SEC_TRAIN_REMAINING_RAW_ROOT'])
        for index in (12, 13):
            tree = html.fromstring((root / f'source-{index:02}' /
                                    '10k.html').read_bytes())
            periods = current._pension(index, tree,
                '2025-12-27' if index == 12 else '2025-12-31')
            for period in periods:
                for fact in period['fields'].values():
                    context = fact.get('context_period')
                    if context is not None:
                        self.assertEqual(context['dimension_members'],
                                         current.PENSION_DIMENSIONS[index])
            with self.subTest(index=index), mock.patch.object(
                    current, '_dimensions', return_value=[]):
                with self.assertRaises(ValueError):
                    current._pension(index, tree,
                        '2025-12-27' if index == 12 else '2025-12-31')
        for index in (18, 19):
            tree = html.fromstring((root / f'source-{index:02}' /
                                    '10k.html').read_bytes())
            periods, maturity = current._afs(index, tree, '2025-12-31')
            for period in periods:
                self.assertTrue(all(
                    fact['context_period']['dimension_members'] == []
                    for fact in period['fields'].values()))
            self.assertEqual(maturity['filed_total_fair']
                             ['context_period']['dimension_members'], [])
            with self.subTest(index=index), mock.patch.object(
                    current, '_dimensions',
                    return_value=current.PENSION_DIMENSIONS[12]):
                with self.assertRaises(ValueError):
                    current._afs(index, tree, '2025-12-31')


if __name__ == '__main__':
    unittest.main()
