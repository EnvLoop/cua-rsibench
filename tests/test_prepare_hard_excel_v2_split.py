"""The hard Excel candidate plan must preserve family boundaries and labels."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_hard_excel_v2_split import choose_families, screen


def fake_families(financial=20, debugging=10):
    rows = {}
    for category, count in (('Financial_Model', financial), ('Debugging', debugging)):
        for index in range(count):
            family_id = f'{category}:family-{index:02d}'
            rows[family_id] = {'family_id': family_id, 'category': category,
                               'screening_reasons': []}
    return rows


class HardExcelSplitTest(unittest.TestCase):
    def test_structural_rule_is_only_a_screen(self):
        features = {'sheets': 7, 'formula_cells': 1000, 'instantiated_cells': 400000,
                    'external_links': False, 'data_connections': False, 'vba_binary': False}
        self.assertEqual(screen(features), [])
        features['formula_cells'] = 999
        features['external_links'] = True
        self.assertEqual(screen(features), ['fewer_than_1000_formula_cells',
                                             'external_links_requires_separate_track'])

    def test_family_disjoint_20_selection_100_final(self):
        chosen = choose_families(fake_families())
        final = chosen['provisional_final']
        selection = chosen['selection']
        self.assertEqual(sum(5 if x['category'] == 'Financial_Model' else 10 for x in final), 100)
        self.assertEqual(sum(5 if x['category'] == 'Financial_Model' else 10 for x in selection), 20)
        self.assertFalse({x['family_id'] for x in final} &
                         {x['family_id'] for x in selection})
        self.assertEqual(chosen, choose_families(fake_families()))

    def test_insufficient_eligible_families_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Debugging: 5 eligible families; 6 required'):
            choose_families(fake_families(debugging=5))


if __name__ == '__main__':
    unittest.main()
