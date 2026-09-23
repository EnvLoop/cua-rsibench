import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cursibench.factory_cases import digest
from cursibench.factory_export import export_case
from cursibench.factory_provenance import validate_selection_packages, verify_factory_identity


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA = '6548946b406bc8640dfe20a884dd9cdf708d8d6c25eeacdabd374a36d5e98237'


def write(path, value):
    path.write_text(json.dumps(value))


class SelectionProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.study = Path(self.temporary.name)
        self.task = 'selection-direct-01'
        self.package = self.study / 'selection' / self.task
        self.case = {'id': 'factory-' + self.task, 'kind': 'factory-direct',
                     'instruction': 'Edit the designated task.',
                     'provenance': {'source_split': 'selection'},
                     'targets': {'GH-1': {'priority': 2}}}
        archive = self.study / 'fixture.tar.gz'
        archive.write_bytes(b'unit-test application archive')
        export_case(self.case, self.package, archive)
        self.manifest = {'evaluation': {'task_count': 1}, 'cases': [
            {'id': self.case['id'], 'hash': digest(self.case), 'family': 'direct', 'target_count': 1}]}
        self.state = {'protocol': {'selection_tasks': [self.task]}}
        self.seal_manifest()
        # Canonical executable validation is real. Only the binary archive's
        # known-good fixture digest is substituted, avoiding a network download.
        def fixture_sha(path):
            path = Path(path)
            data = path.read_bytes()
            if path.name == 'kanboard.tar.gz' and data == archive.read_bytes():
                return ARCHIVE_SHA
            return hashlib.sha256(data).hexdigest()
        self.hash_patch = patch('cursibench.factory_final.sha', side_effect=fixture_sha)
        self.hash_patch.start()
        self.addCleanup(self.hash_patch.stop)

    def seal_manifest(self):
        write(self.study / 'manifest.json', self.manifest)
        self.state['protocol']['selection_manifest_sha256'] = hashlib.sha256(
            (self.study / 'manifest.json').read_bytes()).hexdigest()

    def validate(self):
        return validate_selection_packages(ROOT, self.study, self.state)

    def test_valid_package_returns_exact_task_and_case_bindings(self):
        proof = self.validate()
        self.assertEqual(set(proof['task_package_hashes']), {self.task})
        self.assertEqual(proof['case_hashes'][self.task], digest(self.case))

    def test_missing_package_is_rejected_even_with_a_valid_manifest(self):
        self.package.rename(self.package.with_name('unexpected'))
        with self.assertRaisesRegex(ValueError, 'package task identities'):
            self.validate()

    def test_extra_nested_task_is_rejected(self):
        nested = self.package / 'extra'
        nested.mkdir()
        (nested / 'task.toml').write_text('')
        with self.assertRaisesRegex(ValueError, 'package task identities'):
            self.validate()

    def test_changed_manifest_and_duplicate_case_are_rejected(self):
        self.manifest['cases'].append(self.manifest['cases'][0])
        write(self.study / 'manifest.json', self.manifest)
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            self.validate()
        self.seal_manifest()
        with self.assertRaisesRegex(ValueError, 'manifest task identities'):
            self.validate()

    def test_target_and_instruction_tampering_are_rejected(self):
        write(self.package / 'tests/targets.json', {'GH-2': {'priority': 2}})
        with self.assertRaisesRegex(ValueError, 'sealed case'):
            self.validate()
        write(self.package / 'tests/targets.json', self.case['targets'])
        (self.package / 'instruction.md').write_text('Another task')
        with self.assertRaisesRegex(ValueError, 'instruction'):
            self.validate()

    def test_partition_change_is_rejected_even_when_new_case_hash_matches(self):
        self.case['provenance']['source_split'] = 'train'
        write(self.package / 'environment/scenario.json',
              {k: v for k, v in self.case.items() if k != 'targets'})
        contract = json.loads((self.package / 'contract.json').read_text())
        contract.update(case_sha256=digest(self.case), source_partition='train')
        write(self.package / 'contract.json', contract)
        self.manifest['cases'][0]['hash'] = digest(self.case)
        self.seal_manifest()
        with self.assertRaisesRegex(ValueError, 'sealed case'):
            self.validate()

    def test_scenario_identity_and_contract_hash_are_checked(self):
        altered = {k: v for k, v in self.case.items() if k != 'targets'}
        altered['id'] = 'factory-wrong'
        write(self.package / 'environment/scenario.json', altered)
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            self.validate()
        altered['id'] = self.case['id']
        write(self.package / 'environment/scenario.json', altered)
        contract = json.loads((self.package / 'contract.json').read_text())
        contract['case_sha256'] = 'wrong'
        write(self.package / 'contract.json', contract)
        with self.assertRaisesRegex(ValueError, 'sealed case'):
            self.validate()

    def test_changed_exported_verifier_or_archive_is_rejected(self):
        verifier = self.package / 'tests/verify.py'
        original = verifier.read_text()
        verifier.write_text(original + '\n# changed\n')
        with self.assertRaisesRegex(ValueError, 'noncanonical task executable'):
            self.validate()
        verifier.write_text(original)
        (self.package / 'environment/kanboard.tar.gz').write_bytes(b'changed application')
        with self.assertRaisesRegex(ValueError, 'application archive changed'):
            self.validate()

    def test_hidden_targets_cannot_be_copied_into_actor_visible_scenario(self):
        write(self.package / 'environment/scenario.json', self.case)
        with self.assertRaisesRegex(ValueError, 'actor/verifier contract changed'):
            self.validate()

    def test_prompt_contract_version_is_checked(self):
        contract = json.loads((self.package / 'contract.json').read_text())
        contract['contract'] = 'other-version'
        write(self.package / 'contract.json', contract)
        with self.assertRaisesRegex(ValueError, 'actor/verifier contract changed'):
            self.validate()


class FactoryIdentityTests(unittest.TestCase):
    def test_requested_model_and_fixed_teacher_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            factory = Path(temporary)
            spec = {'researcher': 'gpt-6-sol', 'teacher': 'gpt-5.6-sol', 'limits': {'rollouts': 3}}
            write(factory / 'spec.json', spec)
            write(factory / 'result.json', {'spec': spec, 'complete': True})
            proof = verify_factory_identity(factory, 'gpt-6-sol')
            self.assertEqual(proof['researcher'], 'gpt-6-sol')
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                verify_factory_identity(factory, 'gpt-5.6-sol')
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                verify_factory_identity(factory, 'gpt-6-sol', 'gpt-6-sol')

    def test_result_cannot_relabel_or_change_its_saved_specification(self):
        with tempfile.TemporaryDirectory() as temporary:
            factory = Path(temporary)
            spec = {'researcher': 'gpt-6-luna', 'teacher': 'gpt-5.6-sol', 'max_turns': 20}
            write(factory / 'spec.json', spec)
            write(factory / 'result.json', {'spec': dict(spec, max_turns=40)})
            with self.assertRaisesRegex(ValueError, 'differs from saved'):
                verify_factory_identity(factory, 'gpt-6-luna')


if __name__ == '__main__':
    unittest.main()
