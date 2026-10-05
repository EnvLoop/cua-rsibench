"""Freeze the trusted Office download before actor input, then score against it.

This is an additive runtime adapter. Binding it into a new execution epoch
requires new native acceptance; previous manual controls do not qualify it.
"""
import hashlib
import inspect
import json
from pathlib import Path
import textwrap

from tools import office_owned_folder_runtime_v2 as original
from tools.office_current_package_v5 import Package as PreviousPackage
from ppt_wdi_factory import verify as ppt
from ppt_wdi_factory import office_revision_verifier_v2 as revision

ORIGINAL_RUNTIME_SHA = '0a7a628610d729ba99480c6ba9488c7d14f13e40f221fcc955bbb90c8fa3bd47'
CONTEXT_FILES = ('source-snapshot.private.json', 'source-provenance.private.json',
                 'source-country.private.zip')


class Package(PreviousPackage):
    def bind_native_baseline(self, baseline, receipt):
        if self.actor.cell_id != 'powerpoint-web':
            return
        original.require(not hasattr(self, 'office_baseline'),
                         'Office baseline is one-use and must precede actor input')
        self.revalidate()
        baseline, receipt = Path(baseline).resolve(), Path(receipt).resolve()
        record = json.loads(original.private(receipt))
        raw = original.private(baseline)
        original.require(baseline.is_relative_to(receipt.parent) and
                         record.get('task_id') == self.actor.task_id and
                         record.get('package_sha256') == self.binding_sha256 and
                         record.get('native_before_sha256') == original.sha(raw) and
                         isinstance(record.get('item_identity_sha256'), str) and
                         len(record['item_identity_sha256']) == 64,
                         'Owned evaluator before-actor download receipt required')
        original.require(self.neutral(baseline)['equivalent'] is True,
                         'Untouched Office baseline differs from original task source')
        # Reserve-task validation addresses these evaluator-only dependencies
        # relative to the source artifact. Copy only the original descriptor's
        # explicit, hash-bound context before freezing the native artifact.
        context = {}
        for name in CONTEXT_FILES:
            if name not in self.paths:
                continue
            raw_context = original.private(self.paths[name])
            expected = self.value['refs'][name]['sha256']
            original.require(original.sha(raw_context) == expected,
                             'Original evaluator source context changed')
            destination = baseline.parent / name
            original.write_new(destination, raw_context)
            context[name] = {'path': destination, 'sha256': expected}
        oracle = ppt.freeze(baseline, self.task, office_web_normalized=True)
        self.office_baseline = baseline
        self.office_baseline_sha256 = original.sha(raw)
        self.office_oracle = oracle
        self.office_baseline_receipt = receipt
        self.office_baseline_receipt_sha256 = original.sha(original.private(receipt))
        self.office_context = context

    def strict_score(self, candidate):
        if self.actor.cell_id != 'powerpoint-web':
            return super().strict_score(candidate)
        self.revalidate()
        if not hasattr(self, 'office_baseline'):
            original.require(Path(candidate).resolve() == self.paths['baseline'].resolve(),
                             'Freeze native before-actor baseline before candidate scoring')
            return super().strict_score(candidate)
        original.require(original.sha(original.private(self.office_baseline)) ==
                         self.office_baseline_sha256 and
                         original.sha(original.private(self.office_baseline_receipt)) ==
                         self.office_baseline_receipt_sha256,
                         'Frozen Office baseline or native receipt changed')
        for reference in self.office_context.values():
            original.require(original.sha(original.private(reference['path'])) == reference['sha256'],
                             'Frozen evaluator source context changed')
        result = revision.verify(self.office_baseline, Path(candidate), self.office_oracle)
        return {'score': result.get('score'), 'raw_strict': result,
                'native_metadata_normalization_applied': True,
                'evaluator_baseline_frozen_before_actor': True,
                'official_final_credit': 0}


class Runtime(original.Runtime):
    pass


def _bind_open():
    if hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest() != ORIGINAL_RUNTIME_SHA:
        raise ValueError('Original Office runtime source changed')
    source = textwrap.dedent(inspect.getsource(original.Runtime.open))
    anchor = "  active=self.host.actor_open(item,package.actor_projection(),self.root/'actor-private',account_lease=lease)"
    if source.count(anchor) != 1:
        raise ValueError('Original before-actor baseline boundary changed')
    source = source.replace(anchor,
        "  if package.actor.cell_id=='powerpoint-web':\n"
        "   write_new(self.root/'frozen-native-baseline.pptx',private(baseline))\n"
        "   package.bind_native_baseline(self.root/'frozen-native-baseline.pptx',self.root/'native-before.private.json')\n" + anchor)
    namespace = {**vars(original), 'Package': Package}
    exec(compile(source, __file__, 'exec'), namespace)
    return namespace['open']


Runtime.open = _bind_open()
