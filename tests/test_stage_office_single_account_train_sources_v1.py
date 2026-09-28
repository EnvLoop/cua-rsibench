"""Offline source/gold segregation and byte-identical upload staging."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_office_web_ppt_teacher_worker_v1 import (
    pptx, write_private,
)
from tests.test_sec_excel_web_train_oracle_v1 import workbook
from tools import stage_office_single_account_train_sources_v1 as stage


class StageSourcesTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            dir=work, prefix='office-single-stage-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ppt_task = self.root / 'ppt-task.private.json'
        self.ppt_source = self.root / 'ppt-source.pptx'
        self.ppt_positive = self.root / 'ppt-positive.pptx'
        write_private(self.ppt_task, b'{"split":"train"}\n')
        write_private(self.ppt_source, pptx('draft'))
        write_private(self.ppt_positive, pptx('positive'))
        self.excel_source = self.root / 'excel-actor.xlsx'
        self.excel_reference = self.root / 'excel-reference.xlsx'
        write_private(self.excel_source, workbook())
        write_private(self.excel_reference,
                      workbook(formula='A1*3'))
        self.ppt = {
            'task_id': 'ppt-wdi-' + 'a' * 16,
            'task_path': self.ppt_task,
            'source_path': self.ppt_source,
            'positive_path': self.ppt_positive,
            'plan_sha256': 'a' * 64,
            'ratified_train_split': True,
        }
        source_hash = stage._sha(self.excel_source.read_bytes())
        self.excel = {
            'task_id': 'xl-train-' + 'b' * 16,
            'task': {'schema':
                     'excel-web-original-train-package-v1',
                     'split': 'train',
                     'official_final_credit': 0,
                     'task_id': 'xl-train-' + 'b' * 16,
                     'actor_task': 'Repair this train workbook.',
                     'actor_xlsx_sha256': source_hash},
            'source_path': self.excel_source,
            'positive_path': self.excel_reference,
            'case': {'case_id': 'private-train-case',
                     'split': 'train_candidate'},
            'case_manifest_sha256': 'b' * 64,
            'ratified_train_split': True,
        }

    def test_evaluator_gold_is_separate_from_two_source_equal_uploads(self):
        output = self.root / 'staged'
        with patch.object(stage, '_ppt_source',
                          return_value=self.ppt), patch.object(
                              stage, '_excel_source',
                              return_value=self.excel):
            result = stage.stage(
                ppt_root=self.root / 'ignored-ppt-source',
                excel_root=self.root / 'ignored-excel-source',
                output=output)
        self.assertTrue(result['actor_reset_byte_identical_per_cell'])
        self.assertEqual(result['cloud_calls'], 0)
        for cell, prefix, suffix in (
                ('powerpoint-web', 'EL-PPT', '.pptx'),
                ('excel-web', 'EL-Excel', '.xlsx')):
            actor = (output / cell / 'upload-actor' /
                     f'{prefix}-Train-Actor{suffix}')
            reset = (output / cell / 'upload-reset' /
                     f'{prefix}-Train-Reset{suffix}')
            self.assertEqual(actor.read_bytes(), reset.read_bytes())
            self.assertEqual(actor.stat().st_mode & 0o077, 0)
            self.assertEqual(reset.stat().st_mode & 0o077, 0)
            self.assertEqual(len(list((output / cell /
                                       'upload-actor').iterdir())), 1)
            self.assertEqual(len(list((output / cell /
                                       'upload-reset').iterdir())), 1)
        self.assertTrue((output / 'excel-web' / 'evaluator' /
                         'reference.private.xlsx').is_file())
        self.assertFalse((output / 'excel-web' / 'upload-actor' /
                          'reference.private.xlsx').exists())
        receipt = json.loads((output /
                              'stage-receipt.private.json').read_bytes())
        self.assertEqual(receipt['official_final_credit'], 0)

    def test_v12_source_name_is_refused_before_staging(self):
        with self.assertRaisesRegex(stage.StageError,
                                    'active_v13_required'):
            stage._ppt_source(self.root / 'ppt-revised-six-reserves-v12')
        self.assertFalse((self.root / 'staged').exists())


if __name__ == '__main__':
    unittest.main()
