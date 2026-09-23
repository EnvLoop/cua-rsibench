"""A new cohort reuses the original's declared baseline, never a private path."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
import prepare_model6_extension as extension
from cursibench.factory_cases import SourceRegistry, compile_case, digest
from cursibench.factory_campaign import digest as protocol_digest


def package(case, destination, **kwargs):
    destination = Path(destination)
    (destination / 'environment').mkdir(parents=True)
    (destination / 'tests').mkdir()
    extension.write(destination / 'environment/scenario.json', {k: v for k, v in case.items() if k != 'targets'})
    extension.write(destination / 'tests/targets.json', case['targets'])
    extension.write(destination / 'contract.json', {'case_sha256': digest(case)})


class BaselineLayoutTests(unittest.TestCase):
    def original(self, root, declared):
        original = root / 'original'
        original.mkdir()
        public = REPO / 'datasets/public/kanboard_issues.json'
        destination = root / 'datasets/public/kanboard_issues.json'
        destination.parent.mkdir(parents=True)
        destination.write_bytes(public.read_bytes())
        snapshot = extension.read(destination)
        selection = snapshot['records'][12:24]
        registry = SourceRegistry(snapshot, [r['number'] for r in selection],
            [r['number'] for r in snapshot['records'][:12] + snapshot['records'][24:36]], partition='selection')
        cases = []
        for task in extension.SELECTION:
            recipe = {'id': task, 'mode': 'direct', 'source_numbers': [selection[0]['number'], selection[1]['number']],
                'select_numbers': [selection[0]['number']], 'changes': {'owner': 'Chen', 'priority': 2, 'score': 5}}
            case = compile_case(recipe, registry)
            package(case, original / 'selection' / task)
            cases.append({'id': case['id'], 'hash': digest(case)})
        final = snapshot['records'][24:36]
        opened = sorted((r['number'] for r in final if r['state'] == 'open'))
        closed = sorted((r['number'] for r in final if r['state'] == 'closed'))
        ids = opened[:3] + closed[:1]
        registry = SourceRegistry(snapshot, ids, [r['number'] for r in snapshot['records'] if r['number'] not in ids], partition='final')
        entries = []
        for index, recipe in enumerate(extension.final_recipes(ids)):
            recipe = copy.deepcopy(recipe)
            recipe['id'] = recipe['id'].removeprefix('model6-')
            case = compile_case(recipe, registry)
            chunk = f'chunk-{index // 3}'
            package(case, original / 'sealed-final' / chunk / recipe['id'])
            entries.append({'task': recipe['id'], 'chunk': chunk, 'case_sha256': digest(case)})
        seal = {'cases': entries, 'source_ids': ids}
        extension.write(original / 'sealed-final/manifest.json', seal)
        manifest = {'student': 'Qwen/Qwen3.5-4B', 'training': {'profile': 'factory-v1', 'steps': 32},
            'sampling': {'max_tokens': 512, 'temperature': 0, 'seed': 23},
            'evaluation': {'task_count': 3}, 'cases': cases, 'engine_hashes': {}}
        extension.write(original / 'manifest.json', manifest)
        summary = {'status': 'scored', 'score': 0.0,
            'tasks': [{'task': name, 'score': 0, 'error_type': None} for name in extension.SELECTION]}
        relative = declared if declared is not None else 'cache-repair/base'
        baseline = original / relative
        baseline.mkdir(parents=True)
        extension.write(baseline / 'result.json', {'inference_kind': 'base', 'training_model': manifest['student'],
            'training_checkpoint': manifest['student'], 'environment': 'journal', 'factory_contract': True,
            'task_count': 3, 'proxy_request_capacity': 270, 'proxy_destroyed': True,
            'proxy_ready': True, 'harbor_exit': 0})
        (baseline / 'marker.txt').write_text('test-only baseline evidence\n')
        for alias in ('astra', 'sol'):
            protocol = {'selection_manifest_sha256': extension.sha(original / 'manifest.json'),
                'final_manifest_sha256': digest(seal)}
            if declared is not None:
                protocol['baseline_directory'] = declared
            extension.write(original / f'{alias}-campaign.json', {
                'protocol': protocol, 'protocol_hash': protocol_digest(protocol), 'baseline': summary})
        return original, baseline, summary

    def test_both_legacy_and_fresh_layouts_bind_copy_hashes_and_provenance(self):
        for declared in (None, 'baseline'):
            with self.subTest(declared=declared), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                original, baseline, summary = self.original(root, declared)
                before = extension.tree_hashes(original)
                target = root / 'extension'
                with patch.object(extension, 'ROOT', root), patch.object(extension, 'export_case', side_effect=package), \
                        patch.object(extension, 'summarize', return_value=summary) as summarize:
                    result = extension.prepare(original, target)
                self.assertEqual(result['provider_calls'], 0)
                self.assertEqual(summarize.call_args_list[0].args[0], baseline)
                self.assertEqual(summarize.call_args_list[1].args[0], target / 'baseline')
                self.assertEqual(extension.tree_hashes(target / 'baseline'), extension.tree_hashes(baseline))
                reuse = extension.read(target / 'reuse-provenance.json')
                self.assertEqual(reuse['source_baseline'], declared or 'cache-repair/base')
                self.assertEqual(reuse['baseline_file_hashes'], extension.tree_hashes(baseline))
                self.assertEqual(extension.tree_hashes(original), before)

    def test_check_only_uses_an_explicit_nested_layout_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            original, baseline, summary = self.original(root, 'runs/base')
            target = root / 'extension'
            with patch.object(extension, 'ROOT', root), patch.object(extension, 'summarize', return_value=summary) as summarize:
                result = extension.prepare(original, target, check_only=True)
            self.assertEqual(result['source_baseline'], 'runs/base')
            summarize.assert_called_once_with(baseline, extension.SELECTION)
            self.assertFalse(target.exists())

    def test_campaign_layout_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'disagree'):
                extension.resolve_baseline_directory(root, {'astra': {'baseline_directory': 'baseline'}, 'sol': {}})
            with self.assertRaisesRegex(ValueError, 'both original'):
                extension.resolve_baseline_directory(root, {'astra': {}})

    def test_unsafe_relative_paths_are_rejected(self):
        for value in ('', '.', '/tmp/baseline', '../outside', 'sub/../baseline', './baseline',
                      'baseline/', 'sub//baseline', 'C:/baseline', 'sub\\baseline', None):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                protocols = {alias: {'baseline_directory': value} for alias in ('astra', 'sol')}
                with self.assertRaisesRegex(ValueError, 'safe relative'):
                    extension.resolve_baseline_directory(temporary, protocols)

    def test_symlinked_or_missing_evidence_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / 'study'
            outside = root / 'outside'
            original.mkdir()
            outside.mkdir()
            (original / 'baseline').symlink_to(outside, target_is_directory=True)
            protocols = {alias: {'baseline_directory': 'baseline'} for alias in ('astra', 'sol')}
            with self.assertRaisesRegex(ValueError, 'symlink'):
                extension.resolve_baseline_directory(original, protocols)
            (original / 'baseline').unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                extension.resolve_baseline_directory(original, protocols)


if __name__ == '__main__':
    unittest.main()
