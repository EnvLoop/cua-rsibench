"""All seven actor roles and all saved auditors select one current counterpart."""
import types,unittest
from magento_catalog_factory import native_surface_workers_v1 as ancestor
from magento_catalog_factory import native_surface_workers_v3 as prior,native_surface_workers_v4 as current
from magento_catalog_factory import native_surface_teacher_v2 as teacher,native_surface_shared_base_v2 as shared
from magento_catalog_factory import native_surface_facade_v4 as controls
from magento_catalog_factory import native_queue_runtime_v4 as runtime,native_surface_budget_performance_v4 as auditor

def constants(code):
    yield from code.co_names
    for value in code.co_consts:
        if isinstance(value,types.CodeType):yield from constants(value)
        elif isinstance(value,str):yield value

class UniformClosureTests(unittest.TestCase):
    def test_every_lazy_verifier_import_and_shared_admission_is_current(self):
        module=current._impl
        for value in vars(module).values():
            functions=[value] if isinstance(value,types.FunctionType) else [v for v in vars(value).values() if isinstance(v,types.FunctionType)] if isinstance(value,type) else []
            for function in functions:
                for name in constants(function.__code__):
                    self.assertNotIn('native_surface_budget_performance_v2',name)
                    self.assertNotIn('native_surface_shared_base_v1',name)
        self.assertIn('native_surface_budget_performance_v4',list(constants(module.final_outcome.__code__)))
        self.assertIn('native_surface_shared_base_v2',list(constants(module.run_shared_base.__code__)))

    def test_teacher_base_selection_final_and_control_share_runtime_and_verifier(self):
        self.assertIs(current.Inputs.__init__.__globals__['Runtime'],runtime.Runtime)
        self.assertIs(current.execute_owned.__globals__['run_task'],runtime.run_task)
        self.assertIs(teacher._impl.run_task,runtime.run_task)
        self.assertIs(teacher._impl.audit_episode,auditor.audit_episode)
        self.assertIs(shared._impl.Inputs,current.Inputs)
        self.assertIs(shared._impl.audit_episode,auditor.audit_episode)
        self.assertIs(controls.run_controls.__globals__['Inputs'],current.Inputs)
        self.assertIs(controls.run_controls.__globals__['run_task'],runtime.run_task)
        self.assertIs(controls.run_controls.__globals__['audit_episode'],auditor.audit_episode)
        self.assertIs(current._impl.verifier_sha256,auditor.verifier_sha256)

    def test_immutable_prior_native_binding_and_actual_v12_epoch_preserved(self):
        self.assertEqual(ancestor.public_binding()['binding_sha256'],'c6dddc008803c1552108dd493bed755e6383d749560c15185e908299454466f2')
        self.assertEqual(prior.public_binding()['binding_sha256'],'4a8e797d6fe0043dba386e92df405bead9c599717019dc8d411f9bfdd0c2adec')
        new=current.public_binding();old=prior.public_binding()
        for key in ['profile','policy_sha256','max_actions','actor_seconds','owned_lifecycle_seconds','verifier_sha256']:
            self.assertEqual(new[key],old[key])
        self.assertTrue(new['all_lazy_auditors_and_teacher_shared_base_bridges_current'])
        for name in ['native_surface_teacher_v2.py','native_surface_shared_base_v2.py','native_surface_facade_v4.py']:
            self.assertIn('magento_catalog_factory/'+name,new['source_sha256s'])

if __name__=='__main__':unittest.main()
