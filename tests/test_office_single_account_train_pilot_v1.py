"""Fake-only manual Office evidence audit; no Microsoft or provider call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from ppt_wdi_factory import plan as wdi_plan, verify as wdi_verify
from ppt_wdi_factory.build import (
    DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON,
    DEFAULT_SKILL, prepare_builder,
)

from tests.test_office_web_ppt_teacher_worker_v1 import (
    png, pptx, write_private,
)
from tests.test_sec_excel_web_train_oracle_v1 import workbook
from tests.test_office_web_excel_teacher_worker_v1 import FakeOracle
from tools import office_single_account_train_pilot_v1 as pilot


def ref(path: Path, root: Path) -> dict:
    return {'path': path.relative_to(root).as_posix(),
            'sha256': pilot._sha(path.read_bytes())}


class FakeScorer:
    def __init__(self, _spec, _paths):
        pass

    def baseline(self, path):
        return {'neutral_score': 0,
                'source_equivalence_sha256': pilot._sha(
                    path.read_bytes())}

    def saved(self, baseline, candidate):
        if baseline.read_bytes() == candidate.read_bytes():
            raise pilot.SingleAccountPilotError(
                'fake_saved_not_positive')
        return {'score': 1,
                'verifier_result_sha256':
                    pilot._sha(candidate.read_bytes())}

    def reset(self, baseline, candidate):
        if baseline.read_bytes() != candidate.read_bytes():
            raise pilot.SingleAccountPilotError(
                'fake_reset_changed')
        return {'score': 0,
                'verifier_result_sha256':
                    pilot._sha(candidate.read_bytes())}


class SingleAccountTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            dir=work, prefix='single-office-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work_root = work

    def fixture(self, cell: str) -> tuple[Path, Path, Path, dict, dict]:
        ppt = cell == 'powerpoint-web'
        extension = '.pptx' if ppt else '.xlsx'
        prefix = 'EL-PPT' if ppt else 'EL-Excel'
        task_id = ('ppt-wdi-' if ppt else 'xl-train-') + 'a' * 16
        package = self.root / 'packages' / 'train' / task_id
        package.mkdir(parents=True, mode=0o700)
        task_path = package / 'task.private.json'
        source = package / ('source.pptx' if ppt else 'actor.xlsx')
        before = pptx('baseline') if ppt else workbook()
        saved = (pptx('saved') if ppt else
                 workbook(formula='A1*3'))
        task_record = {
            'schema': ('ppt-wdi-original-candidates-v1' if ppt else
                       'excel-web-original-train-package-v1'),
            'split': 'train', 'task_id': task_id,
            'actor_task': 'Repair this train-only Office file.',
            'official_final_credit': 0,
        }
        if not ppt:
            task_record['actor_xlsx_sha256'] = pilot._sha(before)
        write_private(task_path, pilot._canonical(task_record))
        write_private(source, before)
        case_ref = reference_ref = case_id = None
        if not ppt:
            cases = self.root / 'case.private.json'
            reference = self.root / 'reference.private.xlsx'
            write_private(cases, pilot._canonical([{
                'case_id': 'train-case',
                'split': 'train_candidate',
                'source_package': {
                    'schema': 'sec-integrated-source-package-v1'},
            }]))
            write_private(reference, saved)
            case_ref = ref(cases, self.work_root)
            reference_ref = ref(reference, self.work_root)
            case_id = 'train-case'
        def item(role: str, guid: str) -> dict:
            name = f'{prefix}-Train-{role}{extension}'
            return {'file_name': name,
                    'edit_url': (
                        'https://onedrive.live.com/personal/' +
                        '1234567890abcdef/_layouts/15/Doc.aspx?' +
                        'sourcedoc=%7B00000000-0000-0000-0000-' +
                        guid + '%7D&file=' + name + '&action=edit')}
        spec = {
            'schema': pilot.SPEC_SCHEMA,
            'cell_id': cell, 'split': 'train',
            'task_id': task_id,
            'package_sha256': 'd' * 64,
            'task_ref': ref(task_path, self.work_root),
            'source_ref': ref(source, self.work_root),
            'cases_ref': case_ref,
            'case_id': case_id,
            'reference_ref': reference_ref,
            'account_principal_sha256': 'a' * 64,
            'folder_label_sha256': 'b' * 64,
            'actor_item': item('Actor', '000000000001'),
            'reset_item': item('Reset', '000000000002'),
            'official_final_credit': 0,
        }
        spec_path = self.root / f'{cell}-spec.private.json'
        write_private(spec_path, pilot._canonical(spec))
        actor = pilot._item(spec['actor_item'], cell)
        reset = pilot._item(spec['reset_item'], cell)
        phases = {}
        starting = datetime.now(timezone.utc)
        for index, phase in enumerate(('before', 'saved',
                                       'reset', 'cleanup')):
            shot = self.root / f'{cell}-{phase}.png'
            write_private(shot, png('white' if phase in
                                    ('before', 'cleanup') else
                                    'green'))
            inventory = self.root / f'{cell}-{phase}-inventory.private.json'
            write_private(inventory, pilot._canonical({
                'schema': pilot.INVENTORY_SCHEMA,
                'phase': phase,
                'account_principal_sha256': 'a' * 64,
                'folder_label_sha256': 'b' * 64,
                'items': ([] if phase == 'cleanup' else
                          [reset] if phase == 'reset' else [actor]),
                'screenshot_ref': ref(shot, self.work_root),
                'operator_reviewed': True,
                'observed_at_utc': (
                    starting + timedelta(minutes=index)).isoformat(),
            }))
            entry = {'inventory_ref': ref(inventory,
                                           self.work_root)}
            if phase != 'cleanup':
                content = saved if phase == 'saved' else before
                downloads = []
                for copy in (1, 2):
                    path = self.root / f'{cell}-{phase}-{copy}{extension}'
                    write_private(path, content)
                    downloads.append(ref(path, self.work_root))
                entry['downloads'] = downloads
            phases[phase] = entry
        gui_before = self.root / f'{cell}-gui-before.png'
        gui_after = self.root / f'{cell}-gui-after.png'
        write_private(gui_before, png('red'))
        write_private(gui_after, png('blue'))
        evidence = {
            'schema': pilot.EVIDENCE_SCHEMA,
            'spec_sha256': pilot._sha(spec_path.read_bytes()),
            'split': 'train',
            'manual_gui': {
                'operator_reviewed': True,
                'original_office_gui': True,
                'signed_in_dedicated_test_account': True,
                'model_calls': 0,
                'application_api_edits': False,
                'actor_edit_url_sha256': actor['edit_url_sha256'],
                'before_screenshot_ref': ref(gui_before,
                                             self.work_root),
                'after_screenshot_ref': ref(gui_after,
                                            self.work_root),
            },
            'phases': phases,
        }
        evidence_path = self.root / f'{cell}-evidence.private.json'
        write_private(evidence_path, pilot._canonical(evidence))
        output = self.root / f'{cell}-audit'
        return spec_path, evidence_path, output, spec, evidence

    def test_both_original_office_cells_accept_strict_train_evidence(self):
        for cell in ('powerpoint-web', 'excel-web'):
            with self.subTest(cell=cell):
                spec, evidence, output, _source, _events = \
                    self.fixture(cell)
                result = pilot.audit(
                    spec, evidence, output,
                    work_root=self.work_root,
                    scorer_factory=FakeScorer)
                self.assertTrue(result['saved_positive'])
                self.assertTrue(result['fresh_reset_neutral'])
                self.assertEqual(result['status'],
                                 'fake_test_control_only')
                self.assertFalse(result['independent_scorer_executed'])
                self.assertFalse(result[
                    'account_wide_acl_independently_verified'])
                self.assertFalse(result[
                    'download_item_identity_independently_verified'])
                self.assertEqual(result['official_final_credit'], 0)
                receipt = json.loads(
                    (output / 'receipt.private.json').read_bytes())
                self.assertEqual(receipt['download_count'], 6)

    def test_other_split_file_in_folder_inventory_fails(self):
        spec, evidence_path, output, _source, evidence = \
            self.fixture('powerpoint-web')
        inventory_path, _ = pilot._ref(
            evidence['phases']['saved']['inventory_ref'],
            self.work_root)
        inventory = json.loads(inventory_path.read_bytes())
        inventory['items'].append({
            'file_name': 'EL-PPT-Final-Hidden.pptx',
            'edit_url_sha256': 'e' * 64,
            'sourcedoc_sha256': 'f' * 64})
        write_private(inventory_path, pilot._canonical(inventory))
        evidence['phases']['saved']['inventory_ref'] = ref(
            inventory_path, self.work_root)
        write_private(evidence_path, pilot._canonical(evidence))
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    'inventory_not_one_current_item'):
            pilot.audit(spec, evidence_path, output,
                        work_root=self.work_root,
                        scorer_factory=FakeScorer)
        self.assertFalse(output.exists())

    def test_excel_saved_and_reset_use_existing_independent_oracle(self):
        spec, evidence, output, source, _events = \
            self.fixture('excel-web')
        reference_path, _ = pilot._ref(
            source['reference_ref'], self.work_root)
        with patch.object(pilot, 'SecOracleSubprocess',
                          lambda: FakeOracle(reference_path)):
            result = pilot.audit(spec, evidence, output,
                                 work_root=self.work_root)
        self.assertTrue(result['saved_positive'])
        self.assertTrue(result['fresh_reset_neutral'])
        self.assertEqual(result['status'],
                         'manual_train_development_control_only')
        self.assertTrue(result['independent_scorer_executed'])
        self.assertEqual(result['official_final_credit'], 0)

    @unittest.skipUnless(DEFAULT_SKILL.is_dir() and
                         DEFAULT_MODULES.is_dir(),
                         'bundled presentation runtime unavailable')
    def test_ppt_saved_and_reset_use_pinned_wdi_seven_slide_oracle(self):
        spec_path, evidence_path, output, spec, evidence = \
            self.fixture('powerpoint-web')
        private = self.root / 'real-ppt-source'
        task = wdi_plan.build(bytes.fromhex('f0' * 32))[
            'sets']['train'][0]
        package = private / 'packages' / 'train' / task['task_id']
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
        baseline = package / 'normalized-test.pptx'
        with ZipFile(source) as original, ZipFile(
                baseline, 'w', compression=ZIP_DEFLATED) as output_zip:
            for name in original.namelist():
                output_zip.writestr(name, original.read(name))
            output_zip.writestr(
                'ppt/theme/theme2.xml',
                original.read('ppt/slideMasters/theme/theme2.xml'))
        baseline.chmod(0o600)
        oracle = wdi_verify.freeze(
            baseline, task, office_web_normalized=True)
        positive = package / 'positive.pptx'
        wdi_verify._write_variant(
            baseline, positive,
            {'summary': oracle['targets']['summary']['correct']},
            oracle)
        positive.chmod(0o600)
        spec['task_id'] = task['task_id']
        spec['task_ref'] = ref(task_path, self.work_root)
        spec['source_ref'] = ref(source, self.work_root)
        write_private(spec_path, pilot._canonical(spec))
        evidence['spec_sha256'] = pilot._sha(spec_path.read_bytes())
        for phase in ('before', 'saved', 'reset'):
            content = (positive.read_bytes() if phase == 'saved'
                       else baseline.read_bytes())
            for index, old_ref in enumerate(
                    evidence['phases'][phase]['downloads']):
                path, _ = pilot._ref(old_ref, self.work_root)
                write_private(path, content)
                evidence['phases'][phase]['downloads'][index] = ref(
                    path, self.work_root)
        write_private(evidence_path, pilot._canonical(evidence))
        result = pilot.audit(spec_path, evidence_path, output,
                             work_root=self.work_root)
        self.assertTrue(result['saved_positive'])
        self.assertTrue(result['fresh_reset_neutral'])
        self.assertEqual(result['status'],
                         'manual_train_development_control_only')
        self.assertTrue(result['independent_scorer_executed'])
        self.assertEqual(result['official_final_credit'], 0)

    def test_saved_pair_or_reset_drift_fails_before_receipt(self):
        spec, evidence_path, output, _source, evidence = \
            self.fixture('excel-web')
        second, _ = pilot._ref(
            evidence['phases']['saved']['downloads'][1],
            self.work_root)
        write_private(second, workbook(number='101'))
        evidence['phases']['saved']['downloads'][1] = ref(
            second, self.work_root)
        write_private(evidence_path, pilot._canonical(evidence))
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    'exact_double_download_changed'):
            pilot.audit(spec, evidence_path, output,
                        work_root=self.work_root,
                        scorer_factory=FakeScorer)
        self.assertFalse(output.exists())

    def test_changed_neutral_copy_is_invalid_not_a_zero_score(self):
        spec, evidence_path, output, _source, evidence = \
            self.fixture('excel-web')
        for index, old_ref in enumerate(
                evidence['phases']['reset']['downloads']):
            path, _ = pilot._ref(old_ref, self.work_root)
            write_private(path, workbook(number='101'))
            evidence['phases']['reset']['downloads'][index] = ref(
                path, self.work_root)
        write_private(evidence_path, pilot._canonical(evidence))
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    'fake_reset_changed'):
            pilot.audit(spec, evidence_path, output,
                        work_root=self.work_root,
                        scorer_factory=FakeScorer)
        self.assertFalse(output.exists())

    def test_train_only_url_and_distinct_reset_document_required(self):
        spec_path, evidence_path, output, spec, evidence = \
            self.fixture('powerpoint-web')
        spec['reset_item'] = spec['actor_item']
        write_private(spec_path, pilot._canonical(spec))
        evidence['spec_sha256'] = pilot._sha(spec_path.read_bytes())
        write_private(evidence_path, pilot._canonical(evidence))
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    'reset_copy_not_distinct'):
            pilot.audit(spec_path, evidence_path, output,
                        work_root=self.work_root,
                        scorer_factory=FakeScorer)

    def test_selection_split_cannot_enter_manual_train_auditor(self):
        spec_path, evidence_path, output, spec, evidence = \
            self.fixture('excel-web')
        spec['split'] = 'selection'
        write_private(spec_path, pilot._canonical(spec))
        evidence['spec_sha256'] = pilot._sha(spec_path.read_bytes())
        write_private(evidence_path, pilot._canonical(evidence))
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,
                                    'train_spec_invalid'):
            pilot.audit(spec_path, evidence_path, output,
                        work_root=self.work_root,
                        scorer_factory=FakeScorer)
        self.assertFalse(output.exists())
