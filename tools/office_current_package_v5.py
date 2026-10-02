"""Additive private rich-SEC graph support; original Office lifecycle is unchanged.

The original graph source executes in an isolated, offline Python subprocess.
Every evaluator dependency and source excerpt is bound by the task descriptor.
This adapter grants no native Office qualification or final-study credit.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from tools import office_owned_folder_runtime_v2 as original
from tools.office_current_package_v4 import Package as LegacyPackage


def _worker(request_path):
    request = json.loads(Path(request_path).read_bytes())
    archive = Path(request['archive'])
    with tempfile.TemporaryDirectory(prefix='office-rich-oracle-') as directory:
        root = Path(directory)
        with ZipFile(archive) as source:
            members = source.infolist()
            original.require(len({m.filename for m in members}) == len(members) and
                sum(m.file_size for m in members) < 25_000_000,
                'Rich oracle archive duplicate or size invalid')
            for member in members:
                relative = Path(member.filename)
                original.require(not relative.is_absolute() and '..' not in relative.parts and
                    relative.suffix == '.py', 'Rich oracle archive path invalid')
                source.extract(member, root)
        verifier = root / request['verifier']
        original.require(verifier.is_relative_to(root) and verifier.is_file(), 'Rich verifier missing')
        sys.path[:0] = [str(verifier.parent), str(root / 'sec_excel_factory')]
        spec = importlib.util.spec_from_file_location('private_rich_office_graph', verifier)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        results = [module.verify(Path(candidate), Path(request['seed']), request['case'])
                   for candidate in request['candidates']]
        print(json.dumps({'results': results}, separators=(',', ':')))


class Package(LegacyPackage):
    def __init__(self, descriptor, *, package_root):
        value = json.loads(original.private(descriptor))
        self.rich = value.get('rich_sec_graph') is True
        if not self.rich:
            super().__init__(descriptor, package_root=package_root)
            return
        original.Package.__init__(self, descriptor, package_root=package_root)
        original.require(self.actor.cell_id == 'excel-web' and
            {'rich_oracle_source', 'rich_oracle_manifest', 'source_excerpt', 'private_oracle'} <= set(self.paths),
            'Rich SEC frozen evaluator references missing')
        self.rich_manifest = json.loads(original.private(self.paths['rich_oracle_manifest']))
        original.require(self.rich_manifest.get('schema') == 'office-rich-sec-oracle-private-v1' and
            self.rich_manifest.get('case_id') == self.value['case_id'] and
            self.rich_manifest.get('counterfactual_profiles') == 2 and
            type(self.rich_manifest.get('checked_targets')) is int and
            self.rich_manifest['checked_targets'] > 0, 'Rich SEC oracle identity invalid')

    def score_many(self, candidates):
        self.revalidate()
        original.require(self.rich, 'Rich graph batch scoring requires rich descriptor')
        cases = json.loads(original.private(self.paths['case_manifest']))
        original.require(len(cases) == 1 and cases[0]['case_id'] == self.value['case_id'],
                         'Rich case identity changed')
        case = dict(cases[0])
        # The copied source bytes are unchanged; only evaluator-local addressing changes.
        case['source_excerpt_path'] = str(self.paths['source_excerpt'].resolve())
        original.require(case['source_excerpt_sha256'] == self.value['refs']['source_excerpt']['sha256'],
                         'Rich original source hash mismatch')
        verifier = Path(self.rich_manifest['verifier'])
        original.require(not verifier.is_absolute() and '..' not in verifier.parts,
                         'Rich verifier path escaped sealed archive')
        request = {'archive': str(self.paths['rich_oracle_source'].resolve()), 'verifier': str(verifier),
                   'seed': str(self.paths['baseline'].resolve()), 'case': case,
                   'candidates': [str(Path(candidate).resolve()) for candidate in candidates]}
        with tempfile.TemporaryDirectory(prefix='office-rich-request-') as directory:
            path = Path(directory) / 'request.private.json'
            path.write_bytes(original.canonical(request)); path.chmod(0o600)
            completed = subprocess.run([sys.executable, '-m', __name__, '--worker-request', str(path)],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=120)
        original.require(completed.returncode == 0, 'Original rich SEC oracle failed; infrastructure-invalid')
        try:
            rows = json.loads(completed.stdout)['results']
        except (ValueError, KeyError):
            raise ValueError('Rich oracle saved result unreadable') from None
        original.require(type(rows) is list and len(rows) == len(candidates), 'Rich score count mismatch')
        output = []
        for raw in rows:
            original.require(type(raw.get('pass')) is bool and type(raw.get('errors')) is list and
                raw.get('checked_targets') == self.rich_manifest['checked_targets'] and
                raw.get('counterfactual_profiles') in (0, 2) and
                (raw['pass'] is False or raw.get('counterfactual_profiles') == 2) and
                not any(str(error).startswith('oracle_setup:') for error in raw['errors']),
                'Original rich SEC source/oracle setup failure remains infrastructure-invalid')
            output.append({'score': 1.0 if raw['pass'] else 0.0, 'raw_strict': raw,
                'native_metadata_normalization_applied': False, 'native_recalculation_verified': False})
        return output

    def strict_score(self, candidate):
        return self.score_many([candidate])[0] if self.rich else super().strict_score(candidate)

    def fresh_copy_reset(self, output):
        """Create a distinct local reset copy, without claiming a cloud reset."""
        self.revalidate()
        target = Path(output)
        original.require(target.resolve() != self.paths['baseline'].resolve(), 'Distinct reset copy required')
        result = original.write_new(target, original.private(self.paths['baseline']))
        original.require(self.neutral(target)['equivalent'] is True, 'Local reset source mismatch')
        return {'schema': 'office-local-fresh-copy-reset-v1', 'artifact': result,
                'native_reset_verified': False, 'official_final_credit': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-request')
    parser.add_argument('--descriptor'); parser.add_argument('--package-root')
    parser.add_argument('--candidate'); parser.add_argument('--reset-output')
    args = parser.parse_args()
    if args.worker_request:
        _worker(args.worker_request); return
    package = Package(args.descriptor, package_root=args.package_root)
    if args.reset_output:
        result = package.fresh_copy_reset(args.reset_output)
        print(json.dumps({'local_reset_equivalent': True, 'native_reset_verified': False,
                          'artifact_sha256': result['artifact']['sha256'], 'official_final_credit': 0}))
    else:
        result = package.strict_score(args.candidate)
        print(json.dumps({'score': result['score'], 'checked_targets': result['raw_strict']['checked_targets'],
            'counterfactual_profiles': result['raw_strict']['counterfactual_profiles'],
            'native_recalculation_verified': False, 'official_final_credit': 0}))


if __name__ == '__main__':
    main()
