"""Deep original reader import must select the same current actor source."""
import json,unittest
from pathlib import Path
from magento_catalog_factory import native_surface_workers_v9 as worker,native_surface_budget_performance_v9 as budget
from magento_catalog_factory import native_surface_budget_performance_v1 as ancestor,native_queue_runtime_v9 as runtime
from magento_catalog_factory import native_surface_teacher_v7 as teacher,native_surface_shared_base_v7 as shared
from magento_catalog_factory import native_saved_baseline_migration_v2 as migration

class OriginalReaderTests(unittest.TestCase):
    def test_original_reader_bytecode_constants_unchanged_only_source_import_current(self):
        before=ancestor.audit_episode.__code__;after=budget._impl.original_audit.__code__
        self.assertEqual(before.co_code,after.co_code);self.assertEqual(before.co_consts,after.co_consts)
        self.assertEqual(after.co_names,tuple('native_surface_workers_v9' if n=='native_surface_workers_v1' else n for n in before.co_names))
        self.assertIs(worker._impl.verifier_sha256,budget.verifier_sha256)
        self.assertIs(teacher._impl.audit_episode,budget.audit_episode)
        self.assertIs(shared._impl.audit_episode,budget.audit_episode)
        self.assertIs(worker.execute_owned.__globals__['run_task'],runtime.run_task)

    def test_actual_baseline_reaudits_exact_original_epoch_without_relabel(self):
        s=worker.ROOT/'work/magento-native-dependency-ready-v16-root-20261002.private'
        p=s/'train-controls.private/attempt-000/baseline/native-row.private.json'
        if not p.is_file():self.skipTest('Actual completed current-readiness baseline unavailable')
        raw=p.read_bytes();identity=migration.private_json(s/'metadata.private/roster.private.json')['splits']['train'][0]
        result=migration.inspect(current_binding=worker.public_binding(),identity=identity,episode=p.parent,
            old_binding_path=s/'metadata.private/binding.private.json',old_launch_path=s/'train-supervision.private/launch-intent.private.json',
            old_terminal_path=s/'train-supervision.private/worker-terminal.private.json')
        self.assertEqual(result['independent_saved_baseline_score'],0);self.assertEqual(p.read_bytes(),raw)
        self.assertFalse(result['original_row_relabelled']);self.assertFalse(result['new_native_execution_claimed'])
        with self.assertRaises(ValueError):
            migration.inspect(current_binding={**worker.public_binding(),'binding_sha256':'0'*64},identity=identity,episode=p.parent,
                old_binding_path=s/'metadata.private/binding.private.json',old_launch_path=s/'train-supervision.private/launch-intent.private.json',
                old_terminal_path=s/'train-supervision.private/worker-terminal.private.json')

if __name__=='__main__':unittest.main()
