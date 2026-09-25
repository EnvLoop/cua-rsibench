"""Paired full-study statistics must preserve task IDs and source families."""

import unittest

from cursibench.full_study_stats_v1 import holm_adjust, paired_summary


def ten_family_scores():
    ids = [f'task-{index:03d}' for index in range(100)]
    families = {task: f'family-{index // 10:02d}'
                for index, task in enumerate(ids)}
    base = {task: int(index % 10 < 5) for index, task in enumerate(ids)}
    selected = {task: int(index % 10 < 6) for index, task in enumerate(ids)}
    return base, selected, families


class FullStudyStatisticsTests(unittest.TestCase):
    def test_paired_gain_and_family_uncertainty_are_separate(self):
        base, selected, families = ten_family_scores()
        result = paired_summary(base, selected, families, replicates=1000)
        self.assertEqual((result['task_count'], result['source_family_count']), (100, 10))
        self.assertEqual((result['base_wins'], result['selected_wins']), (50, 60))
        self.assertEqual((result['improved_tasks'], result['regressed_tasks'],
                          result['unchanged_tasks']), (10, 0, 90))
        self.assertEqual(result['paired_delta_pp'], 10)
        self.assertEqual(result['primary_family_cluster_interval_pp'], [10.0, 10.0])
        self.assertEqual(result['family_interval_interpretation'],
                         'cluster_resampled_conditional_on_one_checkpoint_and_rollout')
        self.assertLess(result['secondary_task_bootstrap_interval_pp'][0], 10)
        self.assertGreater(result['secondary_task_bootstrap_interval_pp'][1], 10)
        self.assertTrue(result['single_rollout_stability_unknown'])
        self.assertEqual(result, paired_summary(base, selected, families, replicates=1000))

    def test_one_source_family_is_not_called_a_hundred_worlds(self):
        base, selected, _ = ten_family_scores()
        families = {task: 'one-deck' for task in base}
        result = paired_summary(base, selected, families, replicates=200)
        self.assertEqual(result['source_family_count'], 1)
        self.assertIsNone(result['primary_family_cluster_interval_pp'])
        self.assertEqual(result['family_interval_interpretation'],
                         'descriptive_fewer_than_ten_families')

    def test_infrastructure_invalid_or_unmatched_identity_never_becomes_zero(self):
        base, selected, families = ten_family_scores()
        selected['task-000'] = None
        with self.assertRaisesRegex(ValueError, 'nonbinary score'):
            paired_summary(base, selected, families, replicates=100)
        selected['task-000'] = True
        with self.assertRaisesRegex(ValueError, 'nonbinary score'):
            paired_summary(base, selected, families, replicates=100)
        selected.pop('task-000')
        selected['different-task'] = 0
        with self.assertRaisesRegex(ValueError, 'identities differ'):
            paired_summary(base, selected, families, replicates=100)

    def test_holm_adjustment_is_monotone_in_sorted_p_values(self):
        self.assertEqual(holm_adjust([0.01, 0.04, 0.02]), [0.03, 0.04, 0.04])
        with self.assertRaisesRegex(ValueError, 'finite p-values'):
            holm_adjust([0.1, float('nan')])


if __name__ == '__main__':
    unittest.main()
