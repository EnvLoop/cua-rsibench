"""Fresh epoch controls require exact review and never reuse a saved baseline."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from magento_catalog_factory import native_reference_qualification_v7 as qualification

class QualificationTests(unittest.TestCase):
    def test_exact_review_no_replay_and_three_actual_calls_in_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);output=root/'controls.private'
            binding=qualification.workers.public_binding()
            identity={'task_id':'synthetic-fixture','package_sha256':'a'*64}
            inputs=SimpleNamespace(binding=binding,roster={'splits':{'train':[identity]*20}},
                runtime=lambda:'runtime',username=lambda:'admin',load=lambda *_:{'case':'fixture'})
            def private(path,expected=None):
                return contract if str(path)=='review' else {}
            with patch.object(qualification.workers,'Inputs',return_value=inputs),patch.object(qualification,'private_json',side_effect=private):
                contract=qualification.review_contract(inputs_path='inputs',inputs_sha256='b'*64,train_index=0,output=output)
                self.assertEqual(contract['modes'],['baseline','positive','wrong_variant'])
                self.assertFalse(contract['old_baseline_promotion_authorized'])
                rows=[{'score':score,'native_source_binding_sha256':binding['binding_sha256']} for _,score in qualification.MODES]
                task=AsyncMock(side_effect=rows)
                with patch.object(qualification.workers,'run_task',task),patch.object(qualification.reference,'sampler',side_effect=lambda case,mode:mode),patch.object(qualification.audit,'audit_episode') as audit:
                    summary=qualification.run(inputs_path='inputs',inputs_sha256='b'*64,train_index=0,output=output,
                        root_review_path='review',root_review_sha256='c'*64,execute=True)
                    self.assertEqual([call.kwargs['sampler'] for call in task.await_args_list],contract['modes'])
                    self.assertEqual(audit.call_count,3)
                    self.assertTrue(summary['fresh_three_modes_completed']);self.assertFalse(summary['original_baseline_promoted'])
                    with self.assertRaises(Exception):qualification.run(inputs_path='inputs',inputs_sha256='b'*64,train_index=0,output=root/'other',root_review_path='review',root_review_sha256='c'*64,execute=True)
                    self.assertEqual(task.await_count,3)

    def test_unreviewed_or_changed_source_never_constructs_native_runtime(self):
        task=AsyncMock()
        with patch.object(qualification.workers,'run_task',task):
            with self.assertRaises(Exception):qualification.run(inputs_path='absent',inputs_sha256='b'*64,train_index=0,
                output='absent',root_review_path='absent',root_review_sha256='c'*64,execute=False)
            with patch.object(qualification,'review_contract',return_value={'current_source':'new'}),patch.object(qualification,'private_json',return_value={'current_source':'old'}):
                with self.assertRaises(Exception):qualification.run(inputs_path='absent',inputs_sha256='b'*64,train_index=0,
                    output='absent',root_review_path='absent',root_review_sha256='c'*64,execute=True)
        task.assert_not_called()

if __name__=='__main__':unittest.main()
