"""Offline per-ID Office candidate controls; no live browser or model call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from ppt_wdi_factory import plan as wdi_plan, verify as wdi_verify
from ppt_wdi_factory.build import (
    DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON,
    DEFAULT_SKILL, prepare_builder,
)

from tests import test_office_single_account_train_pilot_v1 as train_tests
from tests.test_office_web_ppt_teacher_worker_v1 import (
    png, write_private,
)
from tools import office_single_account_train_pilot_v1 as common
from tools import office_single_account_candidate_control_v1 as candidate


class CandidateControlTests(unittest.TestCase):
    def setUp(self):
        fixture = train_tests.SingleAccountTests(
            methodName='test_both_original_office_cells_accept_strict_train_evidence')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.base = fixture
        self.root = fixture.root
        self.work_root = fixture.work_root

    def fixture(self, cell: str, split: str):
        spec_path, evidence_path, _out, spec, evidence = \
            self.base.fixture(cell)
        role = 'Selection' if split == 'selection' else 'Final'
        source_task, _ = common._ref(spec['task_ref'], self.work_root)
        source, _ = common._ref(spec['source_ref'], self.work_root)
        package = (self.root / 'packages' / split /
                   spec['task_id'])
        package.mkdir(parents=True, mode=0o700)
        task_path = package / 'task.private.json'
        source_path = package / source.name
        write_private(task_path, source_task.read_bytes())
        write_private(source_path, source.read_bytes())
        spec['schema'] = candidate.SPEC_SCHEMA
        spec['split'] = split
        spec['task_ref'] = train_tests.ref(task_path,
                                           self.work_root)
        spec['source_ref'] = train_tests.ref(source_path,
                                             self.work_root)
        spec.pop('official_final_credit')
        spec.update({
            'source_group_sha256': common._sha('source-family'),
            'template_group_sha256': common._sha('template-family'),
            'browser_run_sha256': common._sha(
                'browser-' + cell + '-' + split),
            'folder_url': 'https://onedrive.live.com/?id=private-folder',
            'pre_result': True,
            'hidden_final_model_attempts': 0,
            'official_final_credit': 0,
        })
        if cell == 'powerpoint-web':
            spec['case_id'] = None
        else:
            spec['case_id'] = 'train-case'
        for field in ('actor_item', 'reset_item'):
            item = spec[field]
            item['edit_url'] = item['edit_url'].replace(
                '-Train-', '-' + role + '-')
            item['file_name'] = item['file_name'].replace(
                '-Train-', '-' + role + '-')
        actor = candidate._item(spec['actor_item'], cell, split)
        reset = candidate._item(spec['reset_item'], cell, split)
        evidence['schema'] = candidate.EVIDENCE_SCHEMA
        evidence['split'] = split
        evidence['manual_gui']['actor_edit_url_sha256'] = \
            actor['edit_url_sha256']
        for phase in ('before', 'saved', 'reset', 'cleanup'):
            inventory_path, _ = common._ref(
                evidence['phases'][phase]['inventory_ref'],
                self.work_root)
            inventory = json.loads(inventory_path.read_bytes())
            inventory['items'] = ([] if phase == 'cleanup' else
                                  [reset] if phase == 'reset' else
                                  [actor])
            write_private(inventory_path,
                          common._canonical(inventory))
            evidence['phases'][phase]['inventory_ref'] = \
                train_tests.ref(inventory_path,
                                self.work_root)
        phases = {}
        for phase in ('before', 'saved', 'reset', 'cleanup'):
            path, _ = common._ref(
                evidence['phases'][phase]['inventory_ref'],
                self.work_root)
            phases[phase] = datetime.fromisoformat(
                json.loads(path.read_bytes())['observed_at_utc'])
        stamp = (
            phases['before'] - timedelta(seconds=10),
            phases['before'] + timedelta(seconds=10),
            phases['before'] + timedelta(seconds=20),
            phases['before'] + timedelta(seconds=30),
            phases['saved'] + timedelta(seconds=10),
            phases['reset'] + timedelta(seconds=10),
        )
        kinds = ('open_folder', 'open_actor', 'edit_actor',
                 'save_actor', 'open_reset', 'finish_folder')
        urls = (spec['folder_url'], spec['actor_item']['edit_url'],
                spec['actor_item']['edit_url'],
                spec['actor_item']['edit_url'],
                spec['reset_item']['edit_url'], spec['folder_url'])
        events = []
        for index, (kind, url, observed) in enumerate(
                zip(kinds, urls, stamp)):
            screenshot = self.root / f'{cell}-{split}-trace-{index}.png'
            write_private(screenshot, png(
                ('red', 'green', 'blue', 'yellow', 'orange', 'purple')[index]))
            events.append({
                'kind': kind, 'url': url,
                'observed_at_utc': observed.isoformat(),
                'screenshot_ref': train_tests.ref(
                    screenshot, self.work_root),
                'operator_reviewed': True,
            })
        trace_path = self.root / f'{cell}-{split}-trace.private.json'
        write_private(trace_path, common._canonical({
            'schema': candidate.TRACE_SCHEMA,
            'split': split, 'task_id': spec['task_id'],
            'browser_run_sha256': spec['browser_run_sha256'],
            'account_principal_sha256':
                spec['account_principal_sha256'],
            'folder_label_sha256': spec['folder_label_sha256'],
            'operator_reviewed': True,
            'events': events,
        }))
        evidence['browser_trace_ref'] = train_tests.ref(
            trace_path, self.work_root)
        write_private(spec_path, common._canonical(spec))
        evidence['spec_sha256'] = common._sha(
            spec_path.read_bytes())
        write_private(evidence_path,
                      common._canonical(evidence))
        output = self.root / f'{cell}-{split}-candidate-audit'
        return spec_path, evidence_path, output, spec, evidence

    def test_selection_and_final_controls_are_per_id_and_never_admitted(self):
        for cell, split in (
                ('powerpoint-web', 'selection'),
                ('powerpoint-web', 'final_candidate'),
                ('excel-web', 'selection'),
                ('excel-web', 'final_candidate')):
            with self.subTest(cell=cell, split=split):
                spec, evidence, output, _source, _events = \
                    self.fixture(cell, split)
                result = candidate.audit(
                    spec, evidence, output,
                    work_root=self.work_root,
                    scorer_factory=train_tests.FakeScorer)
                self.assertEqual(result['status'],
                                 'fake_candidate_test_only')
                self.assertTrue(result['saved_known_positive'])
                self.assertFalse(result['official_final_admitted'])
                self.assertFalse(result[
                    'fresh_browser_sandbox_independently_verified'])
                self.assertEqual(result['official_selection_credit'], 0)
                receipt = json.loads((output /
                    'candidate-control.private.json').read_bytes())
                self.assertEqual(receipt['download_count'], 6)
                self.assertFalse(receipt[
                    'full_cell_denominator_completed'])

    def test_navigation_to_another_item_is_rejected(self):
        spec, evidence_path, out, _source, evidence = \
            self.fixture('powerpoint-web', 'final_candidate')
        trace_path, _ = common._ref(
            evidence['browser_trace_ref'], self.work_root)
        trace = json.loads(trace_path.read_bytes())
        trace['events'][2]['url'] = \
            'https://onedrive.live.com/other-document'
        write_private(trace_path, common._canonical(trace))
        evidence['browser_trace_ref'] = train_tests.ref(
            trace_path, self.work_root)
        write_private(evidence_path, common._canonical(evidence))
        with self.assertRaisesRegex(candidate.CandidateControlError,
                                    'browser_left_exact_task_allowlist'):
            candidate.audit(spec, evidence_path, out,
                            work_root=self.work_root,
                            scorer_factory=train_tests.FakeScorer)
        self.assertFalse(out.exists())
        invalid = candidate.preserve_invalid(
            spec, evidence_path, out,
            work_root=self.work_root,
            reason_type='CandidateControlError',
            reason_code='candidate_browser_left_exact_task_allowlist')
        self.assertEqual(invalid['official_final_credit'], 0)
        self.assertTrue((out / 'invalid.private.json').is_file())

    def test_wrong_split_and_source_family_fail_before_scoring(self):
        spec_path, evidence_path, out, spec, evidence = \
            self.fixture('excel-web', 'selection')
        spec['split'] = 'final_candidate'
        write_private(spec_path, common._canonical(spec))
        evidence['spec_sha256'] = common._sha(spec_path.read_bytes())
        write_private(evidence_path, common._canonical(evidence))
        with self.assertRaisesRegex(candidate.CandidateControlError,
                                    'task_package_split_path_invalid'):
            candidate.audit(spec_path, evidence_path, out,
                            work_root=self.work_root,
                            scorer_factory=train_tests.FakeScorer)
        self.assertFalse(out.exists())

    @unittest.skipUnless(DEFAULT_SKILL.is_dir() and
                         DEFAULT_MODULES.is_dir(),
                         'bundled presentation runtime unavailable')
    def test_real_wdi_selection_and_final_candidate_oracle_controls(self):
        for split in ('selection', 'final_candidate'):
            with self.subTest(split=split):
                spec_path, evidence_path, output, spec, evidence = \
                    self.fixture('powerpoint-web', split)
                task = wdi_plan.build(bytes.fromhex('f0' * 32))[
                    'sets'][split][0]
                private = self.root / ('real-wdi-' + split)
                package = private / 'packages' / split / task['task_id']
                package.mkdir(parents=True, mode=0o700)
                task_path = package / 'task.private.json'
                write_private(task_path, wdi_plan.canonical(task))
                builder = prepare_builder(private, DEFAULT_MODULES)
                environment = {
                    **os.environ,
                    'PRESENTATIONS_SKILL_DIR': str(DEFAULT_SKILL),
                    'RUNTIME_PYTHON': str(DEFAULT_PYTHON),
                    'RUNTIME_NODE': str(DEFAULT_NODE),
                    'RUNTIME_NODE_MODULES': str(DEFAULT_MODULES),
                }
                subprocess.run([
                    str(DEFAULT_NODE), str(builder), str(task_path),
                    str(package / 'draft.pptx')], check=True,
                    capture_output=True, env=environment)
                source = package / 'source.pptx'
                subprocess.run([
                    str(DEFAULT_NODE),
                    str(Path('ppt_wdi_factory/finalize_deck.mjs').resolve()),
                    str(package / 'draft.pptx'), str(source)],
                    check=True, capture_output=True, env=environment)
                source.chmod(0o600)
                baseline = package / 'synthetic-normalized.pptx'
                with ZipFile(source) as original, ZipFile(
                        baseline, 'w',
                        compression=ZIP_DEFLATED) as output_zip:
                    for name in original.namelist():
                        output_zip.writestr(name, original.read(name))
                    output_zip.writestr(
                        'ppt/theme/theme2.xml',
                        original.read(
                            'ppt/slideMasters/theme/theme2.xml'))
                baseline.chmod(0o600)
                oracle = wdi_verify.freeze(
                    baseline, task, office_web_normalized=True)
                positive = package / 'positive.pptx'
                wdi_verify._write_variant(
                    baseline, positive,
                    {name: row['correct'] for name, row in
                     oracle['targets'].items()}, oracle)
                positive.chmod(0o600)
                spec['task_id'] = task['task_id']
                spec['task_ref'] = train_tests.ref(
                    task_path, self.work_root)
                spec['source_ref'] = train_tests.ref(
                    source, self.work_root)
                spec['source_group_sha256'] = common._sha(
                    task['source_group'])
                spec['template_group_sha256'] = common._sha(
                    task['template_group'])
                write_private(spec_path, common._canonical(spec))
                evidence['spec_sha256'] = common._sha(
                    spec_path.read_bytes())
                for phase in ('before', 'saved', 'reset'):
                    content = (positive.read_bytes() if phase == 'saved'
                               else baseline.read_bytes())
                    for index, old_ref in enumerate(
                            evidence['phases'][phase]['downloads']):
                        path, _ = common._ref(old_ref, self.work_root)
                        write_private(path, content)
                        evidence['phases'][phase]['downloads'][index] = \
                            train_tests.ref(path, self.work_root)
                trace_path, _ = common._ref(
                    evidence['browser_trace_ref'], self.work_root)
                trace = json.loads(trace_path.read_bytes())
                trace['task_id'] = task['task_id']
                write_private(trace_path, common._canonical(trace))
                evidence['browser_trace_ref'] = train_tests.ref(
                    trace_path, self.work_root)
                write_private(evidence_path,
                              common._canonical(evidence))
                result = candidate.audit(spec_path, evidence_path,
                                         output, work_root=self.work_root)
                self.assertEqual(result['status'],
                                 'pre_result_candidate_control_only')
                self.assertTrue(result['independent_scorer_executed'])
                self.assertFalse(result['official_final_admitted'])

    def test_integrated_excel_candidate_split_and_numeric_oracle_contract(self):
        for split, target_count in (('selection', 33),
                                    ('final_candidate', 48)):
            with self.subTest(split=split):
                spec_path, evidence_path, output, spec, evidence = \
                    self.fixture('excel-web', split)
                task_path, _ = common._ref(
                    spec['task_ref'], self.work_root)
                source_path, _ = common._ref(
                    spec['source_ref'], self.work_root)
                task = {
                    'schema': candidate.EXCEL_TASK_SCHEMA,
                    'split': ('selection_candidate' if
                              split == 'selection' else
                              'final_candidate'),
                    'task_id': spec['task_id'],
                    'actor_task': 'Repair this SEC workbook.',
                    'workflow': 'sec-integrated',
                    'source_group': 'issuer-A',
                    'template_group': 'integrated-close-A',
                    'actor_xlsx_sha256': common._sha(
                        source_path.read_bytes()),
                    'official_final_credit': 0,
                }
                write_private(task_path, common._canonical(task))
                spec['task_ref'] = train_tests.ref(
                    task_path, self.work_root)
                spec['source_group_sha256'] = common._sha(
                    task['source_group'])
                spec['template_group_sha256'] = common._sha(
                    task['template_group'])
                cases_path, _ = common._ref(
                    spec['cases_ref'], self.work_root)
                write_private(cases_path, common._canonical([{
                    'case_id': spec['case_id'],
                    'split': task['split'],
                    'source_package': {
                        'schema': 'sec-integrated-source-package-v1'},
                }]))
                spec['cases_ref'] = train_tests.ref(
                    cases_path, self.work_root)
                write_private(spec_path, common._canonical(spec))
                evidence['spec_sha256'] = common._sha(
                    spec_path.read_bytes())
                write_private(evidence_path,
                              common._canonical(evidence))
                reference_path, _ = common._ref(
                    spec['reference_ref'], self.work_root)
                def fake_verify(candidate_path, seed_path, case):
                    positive = (candidate_path.read_bytes() ==
                                reference_path.read_bytes())
                    return {'pass': positive,
                            'checked_targets': target_count,
                            'counterfactual_profiles': (
                                2 if positive else 0),
                            'errors': ([] if positive else
                                       ['target_formula_missing'])}
                with patch.object(candidate.excel_oracle,
                                  'sec_verify', fake_verify):
                    result = candidate.audit(
                        spec_path, evidence_path, output,
                        work_root=self.work_root)
                self.assertEqual(result['status'],
                                 'pre_result_candidate_control_only')
                self.assertTrue(result['independent_scorer_executed'])
                self.assertFalse(result['official_final_admitted'])


if __name__ == '__main__':
    unittest.main()
