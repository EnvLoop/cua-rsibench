"""Private output, allocation and sealed-final access boundary regressions."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from native_desktop_factory import native_selection_reference_preparation_v1 as preparation


class PreparationTests(unittest.TestCase):
    def call(self,root,output,**overrides):
        arguments={'candidate_root':root,'inventory_sha256':'a'*64,
                   'runtime_sha256':'b'*64,'output':output}
        arguments.update(overrides)
        return preparation.prepare(**arguments)

    def test_public_output_refused_before_private_reads(self):
        with patch.object(preparation,'file_ref',side_effect=AssertionError('Private source opened')):
            with self.assertRaisesRegex(ValueError,'Evaluator-private'):
                self.call('/unused','/tmp/public-output.json')

    def test_existing_output_is_not_overwritten_or_replayed(self):
        with tempfile.TemporaryDirectory(suffix='.private') as folder:
            output=Path(folder)/'packet.json';output.write_bytes(b'original evidence')
            with patch.object(preparation,'file_ref',side_effect=AssertionError('Private source opened')):
                with self.assertRaisesRegex(ValueError,'Fresh private'):
                    self.call('/unused',output)
            self.assertEqual(output.read_bytes(),b'original evidence')

    def test_inventory_tamper_refused_before_package_oracle_reads(self):
        with tempfile.TemporaryDirectory(suffix='.private') as folder:
            root=Path(folder);(root/'candidate-inventory.json').write_text('{}')
            with patch.object(preparation.admit,'_package',side_effect=AssertionError('Oracle opened')):
                with self.assertRaisesRegex(ValueError,'inventory hash'):
                    self.call(root,root/'output.json')

    def test_narrow_or_overlapping_allocation_refused_before_final_reads(self):
        for duplicate in (False,True):
            with tempfile.TemporaryDirectory(suffix='.private') as folder:
                root=Path(folder)
                rows=[{'split':split,'task_id':'duplicate' if duplicate else f'{split}-{i}'}
                      for split,count in [('train',20),('selection',20),('final_candidate',100 if duplicate else 99)]
                      for i in range(count)]
                raw=json.dumps({'design_revision':'v2-distinct-structures','tasks':rows}).encode()
                (root/'candidate-inventory.json').write_bytes(raw)
                with patch.object(preparation.admit,'_package',side_effect=AssertionError('Sealed oracle opened')):
                    with self.assertRaisesRegex(ValueError,'allocation|overlap'):
                        self.call(root,root/'output.json',inventory_sha256=sha256(raw).hexdigest())

    def test_wrong_runtime_epoch_refused_before_task_bodies(self):
        with tempfile.TemporaryDirectory(suffix='.private') as folder:
            root=Path(folder);rows=[{'split':split,'task_id':f'{split}-{i}'}
                for split,count in [('train',20),('selection',20),('final_candidate',100)] for i in range(count)]
            raw=json.dumps({'design_revision':'v2-distinct-structures','tasks':rows}).encode()
            (root/'candidate-inventory.json').write_bytes(raw)
            with patch.object(preparation.admit,'_package',side_effect=AssertionError('Oracle opened')):
                with self.assertRaisesRegex(ValueError,'Source100'):
                    self.call(root,root/'output.json',inventory_sha256=sha256(raw).hexdigest())


if __name__=='__main__':unittest.main()
