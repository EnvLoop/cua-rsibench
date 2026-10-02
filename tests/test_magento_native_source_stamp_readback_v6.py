"""Same actor semantics, complete private reader exports and honest old rows."""
import json,tempfile,types,unittest
from hashlib import sha256
from pathlib import Path
from magento_catalog_factory import native_surface_actor_v1 as old_actor,native_surface_actor_v2 as actor
from magento_catalog_factory import native_surface_workers_v6 as worker,native_queue_runtime_v6 as runtime
from magento_catalog_factory import native_surface_budget_performance_v6 as auditor,native_surface_facade_v6 as facade
from magento_catalog_factory import native_surface_teacher_v4 as teacher,native_surface_shared_base_v4 as shared
from magento_catalog_factory import native_saved_baseline_migration_v1 as migration

class SourceStampTests(unittest.TestCase):
    def test_actor_bytecode_changes_only_source_binding_import(self):
        before=old_actor.run_task.__code__;after=actor.run_task.__code__
        self.assertEqual(before.co_code,after.co_code)
        expected=tuple('native_surface_workers_v6' if name=='native_surface_workers_v1' else name for name in before.co_names)
        self.assertEqual(after.co_names,expected)
        self.assertEqual(before.co_consts,after.co_consts)

    def test_every_role_shares_current_actor_reader_and_auditor(self):
        self.assertIs(runtime._impl.original_run_task,actor.run_task)
        self.assertIs(runtime._read,runtime._impl._read)
        self.assertIs(worker.Inputs.__init__.__globals__['Runtime'],runtime.Runtime)
        self.assertIs(worker.execute_owned.__globals__['run_task'],runtime.run_task)
        self.assertIs(teacher._impl.run_task,runtime.run_task)
        self.assertIs(teacher._impl.audit_episode,auditor.audit_episode)
        self.assertIs(shared._impl.Inputs,worker.Inputs)
        self.assertIs(shared._impl.audit_episode,auditor.audit_episode)
        self.assertIs(facade.run_controls.__globals__['run_task'],runtime.run_task)
        self.assertIs(facade.run_controls.__globals__['audit_episode'],auditor.audit_episode)

    def test_actual_saved_baseline_independent_audit_keeps_original_source_stamp(self):
        root=worker.ROOT/'work/magento-native-quote-navigation-v13-root-20261002.private/train-controls.private/attempt-000/baseline'
        if not (root/'native-row.private.json').is_file():self.skipTest('Saved actual baseline unavailable')
        before=(root/'native-row.private.json').read_bytes();row=json.loads(before)
        self.assertEqual(row['native_source_binding_sha256'],'c6dddc008803c1552108dd493bed755e6383d749560c15185e908299454466f2')
        result=auditor.audit_episode(root,row,provider_close_required=False)
        self.assertEqual(result['score'],0)
        self.assertEqual((root/'native-row.private.json').read_bytes(),before)
        self.assertEqual(row['native_queue_profile'],'magento-native-single-attribute-consumer-v5-bounded-native-exec-transition')

    def test_reviewed_saved_migration_reopens_originals_and_rejects_relabelled_summary(self):
        root=worker.ROOT/'work/magento-native-quote-navigation-v13-root-20261002.private'
        episode=root/'train-controls.private/attempt-000/baseline'
        if not (episode/'native-row.private.json').is_file():self.skipTest('Saved actual baseline unavailable')
        manifest=json.loads((root/'metadata.private/roster.private.json').read_bytes());identity=manifest['splits']['train'][0]
        value=migration.inspect(current_binding=worker.public_binding(),identity=identity,episode=episode,
            old_binding_path=root/'metadata.private/binding.private.json',old_launch_path=root/'train-supervision.private/launch-intent.private.json',
            old_terminal_path=root/'train-supervision.private/worker-terminal.private.json')
        baseline={'score':0,'episode_root':str(episode),'native_row_sha256':value['original_row_sha256']}
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'migration.private.json'
            def save(data):
                path.write_text(json.dumps(data));path.chmod(0o600)
                return {'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest()}
            reference=save(value)
            self.assertEqual(migration.checked(reference,current_binding=worker.public_binding(),identity=identity,baseline_proof=baseline),value)
            for key,new in [('original_row_relabelled',True),('independent_saved_baseline_score',1),
                ('current_binding_sha256','0'*64),('new_native_execution_claimed',True)]:
                with self.subTest(key=key),self.assertRaises(ValueError):
                    migration.checked(save({**value,key:new}),current_binding=worker.public_binding(),identity=identity,baseline_proof=baseline)

if __name__=='__main__':unittest.main()
