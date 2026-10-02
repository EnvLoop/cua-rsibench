"""Synthetic saved evidence; no native, provider or hidden real-world reads."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from tools import prepare_odoo20_final_source_qa_v2 as subject


class SavedQATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.worker = self.root/'official_hidden'
        self.private = self.worker/'private'; self.private.mkdir(parents=True, mode=0o700)
        self.run = self.private/'synthetic-controls'; self.run.mkdir(mode=0o700)
        self.output = self.root/'work/qa.private'
        self.assets, metadata, entries = {}, [], []
        world = {'split': 'official_hidden', 'cases': {}}
        raw = io.BytesIO(); Image.new('RGB', (37, 23), '#173259').save(raw, format='PNG')
        self.native = raw.getvalue()
        for family in ('purchase', 'inventory', 'sales', 'crm'):
            cases = []
            for index in range(25):
                name = f'SYNTHETIC-{family}-{index}'
                cases.append({'id': name, 'family': family})
                if index >= 5: continue
                ordinal = len(metadata)
                asset = (b'%PDF-SYNTHETIC' if ordinal == 0 else f'SYNTHETIC SOURCE {name}\nQuantity: 17\n'.encode())
                self.assets[name] = asset
                row = {'task_id': name, 'package_sha256': 'a'*64, 'family': family,
                    'source_asset_sha256': subject.digest(asset)}
                metadata.append(row)
                attempt = self.run/f'attempt-{ordinal:03d}'; attempt.mkdir(mode=0o700)
                frame = subject._write(attempt/'native.png', self.native)
                receipt = subject._json(attempt/'attempt.private.json', {'worker_pid': 424242,
                    'finished_at_utc': '2026-10-02T00:00:00+00:00', 'refs': {'source_frame': {
                        'path': 'native.png', 'sha256': frame['sha256']}}})
                entries.append({'metadata': row, 'attempt': {'path': f'attempt-{ordinal:03d}/attempt.private.json',
                                                            'sha256': receipt['sha256']}})
            world['cases'][family] = cases
        subject._json(self.private/'partition_cases.json', world)
        self.plan = {'frozen_twenty_metadata': metadata, 'trial_plan_ref': {'sha256': 'b'*64},
            'native_core_plan': {'native_worker_binding_sha256': 'c'*64},
            'reference_binding': {'reference_binding_sha256': 'd'*64}}
        self.result = {'status': subject.controls.PENDING, 'saved_control_count': 20, 'entries': entries}
        self.result_path = self.run/'controls-result.private.json'
        subject._json(self.result_path, self.result)
        stamp = datetime(2026, 10, 2, tzinfo=timezone.utc).timestamp()
        self.terminal_path = self.root/'terminal.private.json'
        self.terminal = {'pid': 424242, 'exit_code': 0, 'automatic_restarts': 0, 'started_at': stamp-100, 'ended_at': stamp+1}
        self.terminal_ref = subject._json(self.terminal_path, self.terminal)

    def render_fixture_pdf(self, path, output):
        image = Image.new('RGB', (51, 41), 'white')
        ref = subject._png(output/'source-page-1.png', image)
        return [image], [ref]

    def prepare(self):
        with patch.object(subject, 'ROOT', self.root), patch.object(subject, '_pid_alive', return_value=False), \
             patch.object(subject.controls, '_load', return_value=self.plan), \
             patch.object(subject.controls, 'audit', return_value={'status': subject.controls.PENDING, 'control_count': 20}), \
             patch.object(subject, 'source_asset', side_effect=lambda case, world: self.assets[case['id']]), \
             patch.object(subject, '_pdf_pages', side_effect=self.render_fixture_pdf):
            return subject.prepare(plan_path=self.root/'plan.private.json', plan_sha='e'*64, worker_dir=self.worker,
                run_dir=self.run, terminal_receipt_path=self.terminal_path, terminal_receipt_sha=self.terminal_ref['sha256'],
                output_root=self.output)

    def test_exact_asset_native_pixels_and_order_are_preserved_all_reviews_pending(self):
        before = self.result_path.read_bytes()
        result = self.prepare()
        manifest = json.loads(Path(result['qa_manifest_ref']['path']).read_bytes())
        pending = json.loads(Path(result['pending_review_ref']['path']).read_bytes())
        self.assertEqual([row['metadata'] for row in manifest['rows']], self.plan['frozen_twenty_metadata'])
        self.assertEqual(len(manifest['rows']), 20)
        self.assertEqual(manifest['original_world_count'], 100)
        self.assertIsNone(manifest['reviewer_approval'])
        self.assertIsNone(pending['reviewer_independent_of_actor'])
        self.assertEqual(before, self.result_path.read_bytes())
        for row in manifest['rows']:
            self.assertEqual(Path(row['native_frame_copy']['path']).read_bytes(), self.native)
            self.assertEqual(Path(row['exact_source_asset_copy']['path']).read_bytes(), self.assets[row['task_id']])
            self.assertIsNone(row['source_attachment_readable'])
            self.assertIsNone(row['source_matches_package'])
            self.assertIsNone(row['reviewed_at_utc'])
            self.assertIsNone(row['visual_approval'])
            with Image.open(row['side_by_side_qa']['path']) as pair:
                x, y = row['native_crop_origin']
                with Image.open(io.BytesIO(self.native)) as native:
                    self.assertEqual(pair.crop((x, y, x+native.width, y+native.height)).tobytes(), native.tobytes())

    def test_live_failed_or_restarted_worker_cannot_generate_qa(self):
        with patch.object(subject, '_pid_alive', return_value=True):
            with self.assertRaisesRegex(subject.controls.evaluator.legacy.OdooFinalWorkerError, 'terminal_worker'):
                subject._terminal(self.terminal_path, self.terminal_ref['sha256'])
        for field in ('exit_code', 'automatic_restarts'):
            terminal = {**self.terminal, field: 1}
            path = self.root/(field+'.private.json'); ref = subject._json(path, terminal)
            with patch.object(subject, '_pid_alive', return_value=False), self.assertRaisesRegex(subject.controls.evaluator.legacy.OdooFinalWorkerError, 'terminal_worker'):
                subject._terminal(path, ref['sha256'])

    def test_wrong_metadata_order_is_rejected(self):
        changed = {**self.result, 'entries': list(reversed(self.result['entries']))}
        self.result_path.write_bytes(subject.controls.workers.canonical(changed))
        with self.assertRaisesRegex(subject.controls.evaluator.legacy.OdooFinalWorkerError, 'twenty_order'):
            self.prepare()

    def test_corrupted_original_native_bytes_are_rejected_before_manifest(self):
        path = self.run/'attempt-000/native.png'
        path.write_bytes(path.read_bytes()+b'SYNTHETIC-CORRUPTION')
        with self.assertRaisesRegex(ValueError, 'saved_reference_hash_changed'):
            self.prepare()
        self.assertFalse((self.output/'qa-manifest.private.json').exists())

    def test_pdf_renderer_requires_poppler_and_never_silently_substitutes(self):
        with patch.object(subject.shutil, 'which', return_value=None), self.assertRaisesRegex(subject.controls.evaluator.legacy.OdooFinalWorkerError, 'poppler_required'):
            subject._pdf_pages(self.root/'synthetic.pdf', self.root)

    def test_output_cannot_overwrite_a_consumed_qa_namespace(self):
        self.prepare()
        with self.assertRaisesRegex(subject.controls.evaluator.legacy.OdooFinalWorkerError, 'fresh_owned_private_namespace'):
            self.prepare()


if __name__ == '__main__': unittest.main()
