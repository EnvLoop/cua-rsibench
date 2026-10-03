"""Read-only source/authority/role boundaries; no native or provider calls."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import office_current_facade_v6 as facade
from tools import office_owned_folder_runtime_v2 as office
from tools import office_neutral_lifecycle_pilot_v4 as pilot

ROOT=Path(__file__).resolve().parents[1]


class Host6FacadeTests(unittest.TestCase):
    def test_complete59_source_map_retains_all53_historical_bytes(self):
        actual=facade.current_sources(ROOT)
        self.assertEqual(len(facade.PARENT_SHA256S),53)
        self.assertEqual(len(actual),59)
        self.assertEqual({key:actual[key] for key in facade.PARENT_SHA256S},facade.PARENT_SHA256S)
        self.assertEqual(len(facade.supplemental_sources(ROOT)),11)
        for key in facade.V6_FILES:self.assertIn(key,actual)
        target=ROOT/next(iter(facade.PARENT_SHA256S))
        original=Path.read_bytes
        def changed(path):
            return b'changed historical source' if path==target else original(path)
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'Historical Office53'):
                facade.current_sources(ROOT)

    def test_python_and_javascript_complete_supplemental_maps_match(self):
        result=subprocess.run(['node','--input-type=module','-e',
            "import {officeV6SourceHashes} from './tools/office_current_cua_pump_v6.mjs';console.log(JSON.stringify(await officeV6SourceHashes()));"],
            cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout),facade.supplemental_sources(ROOT))

    def test_all_roles_share_rich_package_source_map_and_original_actor_identity(self):
        modules=facade.parent.checked_modules()
        prior={name:(getattr(module,'Package',None),getattr(module,'current_sources',None),getattr(module,'office',None)) for name,module in modules.items()}
        execution=modules['tools/office_current_execution_v4.py']
        actor_class=execution.TaskWorker;actor_code=actor_class.run.__code__;old_init=actor_class.__init__;old_files=pilot.V4_FILES
        with facade.source_epoch() as active:
            for module in active.values():
                if hasattr(module,'Package'):self.assertIs(module.Package,facade.parent.Package)
                if hasattr(module,'current_sources'):self.assertEqual(module.current_sources(ROOT),facade.current_sources(ROOT))
                if hasattr(module,'TaskWorker'):self.assertIs(module.TaskWorker,actor_class)
            self.assertIs(actor_class.run.__code__,actor_code)
            self.assertEqual(pilot.V4_FILES,facade.SUPPLEMENTAL_FILES)
            neutral=facade.neutral_module()
            self.assertIs(neutral.runtime.Package,facade.parent.Package)
            self.assertEqual(neutral.V4_FILES,facade.SUPPLEMENTAL_FILES)
            self.assertEqual(neutral.source_hashes(ROOT),facade.current_sources(ROOT))
        self.assertEqual(pilot.V4_FILES,old_files)
        self.assertIs(actor_class.__init__,old_init)
        for name,module in modules.items():
            self.assertEqual((getattr(module,'Package',None),getattr(module,'current_sources',None),getattr(module,'office',None)),prior[name])

    def test_epoch_restores_globals_after_an_exception(self):
        modules=facade.parent.checked_modules();authority=modules['tools/office_current_authority_v4.py'];original=(authority.current_sources,authority.verify_qualification,pilot.V4_FILES)
        with self.assertRaisesRegex(RuntimeError,'fixture stop'):
            with facade.source_epoch():raise RuntimeError('fixture stop')
        self.assertEqual((authority.current_sources,authority.verify_qualification,pilot.V4_FILES),original)

    def test_old_or_wrong_transport_qualification_refuses_before_private_control_body(self):
        with tempfile.TemporaryDirectory() as directory,facade.source_epoch() as modules:
            path=Path(directory)/'qualification.private.json';qualify=modules['tools/office_current_authority_v4.py'].verify_qualification
            values=[{'schema':'office-current-source-qualification-v4','accepted':True},
                    {'schema':'office-current-source-qualification-v5','accepted':True},
                    {'schema':facade.QUALIFICATION_SCHEMA,'accepted':True,'source_epoch':facade.SOURCE_EPOCH,'baseline_upload_transport':'filechooser','native_picker_app_id':facade.NATIVE_PICKER_APP_ID}]
            for value in values:
                raw=office.canonical(value);path.write_bytes(raw);path.chmod(0o600)
                with patch('cursibench.full_study_final_dispatch_v1.private_reference',side_effect=AssertionError('private control body reached')):
                    with self.assertRaises(ValueError):qualify(object(),'powerpoint-web',path,sha256(raw).hexdigest())

    def test_retagging_old_control_metadata_cannot_promote_old_episode_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);episode=root/'episode';episode.mkdir(mode=0o700)
            office.write_new(episode/'native-source-admission.private.json',office.canonical({
                'schema':'office-owned-folder-native-host-source-review-v2','actual_native_lifecycle_qualified':True,
                'supplemental_source_sha256s':{}}))
            value={'schema':facade.QUALIFICATION_SCHEMA,'source_epoch':facade.SOURCE_EPOCH,
                   'baseline_upload_transport':facade.BASELINE_UPLOAD_TRANSPORT,'native_picker_app_id':facade.NATIVE_PICKER_APP_ID,
                   'controls':[{'path':'fixture-control.private.json','sha256':'a'*64}]}
            path=root/'qualification.private.json';raw=office.canonical(value);office.write_new(path,raw)
            def reader(*args):return value  # Isolates the extra admission check, never a scorer or accepted qualification.
            qualify=facade._qualification(reader,{})
            control=office.canonical({'episode_root':str(episode)})
            with patch('cursibench.full_study_final_dispatch_v1.private_reference',return_value=(root/'fixture-control.private.json',control)):
                with self.assertRaisesRegex(ValueError,'Exact same Host6'):
                    qualify(SimpleNamespace(repo_root=ROOT),'powerpoint-web',path,office.sha(raw))

    def test_cli_rejects_old_configuration_before_study_or_body_load(self):
        with facade.source_epoch() as modules:
            cli=modules['tools/office_current_worker_cli_v4.py']
            config={'schema':'office-current-execution-configuration-v4','source_epoch':facade.SOURCE_EPOCH,
                    'baseline_upload_transport':facade.BASELINE_UPLOAD_TRANSPORT,'native_picker_app_id':facade.NATIVE_PICKER_APP_ID}
            with patch.object(cli,'load',side_effect=AssertionError('study loading reached')):
                with self.assertRaisesRegex(ValueError,'configuration required'):cli.execute(config,'check')

    def test_registry_keeps_full_authority_and_budgets_without_qualification_credit(self):
        value=facade.counterpart_registry(ROOT)
        self.assertEqual((value['distinct_official_task_identities'],value['campaign_count'],value['initial_slot_task_results']),(600,24,3000))
        self.assertFalse(value['native_qualified']);self.assertEqual(value['old_manual_baseline_credit'],0)
        for cell in value['cells'].values():
            self.assertEqual((cell['max_actions'],cell['actor_seconds'],cell['lease_seconds']),(90,720,1200))
            self.assertEqual(cell['frame_ttl_seconds'],150);self.assertFalse(cell['qualified'])
            self.assertEqual(cell['native_pump'],'tools/office_current_cua_pump_v6.mjs')
            self.assertEqual(cell['baseline_upload_transport'],facade.BASELINE_UPLOAD_TRANSPORT)
            self.assertTrue(cell['all_actor_paths_same_native_loop']);self.assertEqual(len(cell['student_slots']),5)

    def test_metadata_writer_preserves_binary_and_does_not_promote_native_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);binary=root/'document.private.bin';raw=b'PK\x03\x04local binary fixture'
            facade._write_new(binary,raw);self.assertEqual(binary.read_bytes(),raw)
            path=root/'native-source-admission.private.json'
            facade._write_new(path,office.canonical({'schema':'office-owned-folder-native-host-source-review-v2',
                'supplemental_source_sha256s':facade.supplemental_sources(ROOT),'actual_native_lifecycle_qualified':False}))
            value=json.loads(path.read_bytes());self.assertFalse(value['actual_native_lifecycle_qualified']);facade._transport(value)

    def test_neutral_metadata_prepare_validate_uses_current_schema_and_complete_map(self):
        # The package stub is metadata-only fixture evidence, never qualification.
        with tempfile.TemporaryDirectory(prefix='office-host6-unit-',dir=ROOT/'work') as directory,facade.source_epoch():
            root=Path(directory);root.chmod(0o700)
            baseline=root/'fixture.pptx';office.write_new(baseline,b'local fixture bytes')
            descriptor=root/'package.private.json';office.write_new(descriptor,office.canonical({'fixture':True}))
            package_sha=office.sha(descriptor.read_bytes())
            class MetadataPackage:
                def __init__(self,*args,**kwargs):
                    self.actor=SimpleNamespace(split='train',task_id='host6-local-fixture')
                    self.binding_sha256=package_sha;self.paths={'baseline':baseline}
                def strict_score(self,*args):return {'score':0}
            binding={'schema':office.SCHEMA,'single_account':True,'scope':'existing_account_dedicated_disposable_folder',
                     'max_wall_seconds':1200,'source_sha256s':office.source_hashes(),
                     'supplemental_source_sha256s':facade.supplemental_sources(ROOT),
                     'source_epoch':facade.SOURCE_EPOCH,'baseline_upload_transport':facade.BASELINE_UPLOAD_TRANSPORT,
                     'native_picker_app_id':facade.NATIVE_PICKER_APP_ID,'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64}
            profile={'schema':'office-owned-folder-native-ui-profile-v3','download_surface':'folder_toolbar',
                     'folder_inventory_proof':{'mode':'parent_card_count'},'upload_transport':'native_picker'}
            binding_path=root/'binding.private.json';profile_path=root/'profile.private.json'
            office.write_new(binding_path,office.canonical(binding));office.write_new(profile_path,office.canonical(profile))
            value=facade.neutral_module();value.runtime.Package=MetadataPackage;config=root/'config.private.json'
            result=value.prepare(repo_root=ROOT,package_descriptor=descriptor,package_root=root,binding_path=binding_path,
                                 profile_path=profile_path,output=root/'unused-native-output',config_path=config)
            checked=value.validate(config)
            self.assertEqual(result['status'],'neutral_pilot_prepared_no_native_call')
            self.assertEqual(checked[0]['schema'],'office-neutral-lifecycle-pilot-config-v6')
            self.assertEqual(checked[0]['source_sha256s'],facade.current_sources(ROOT))
            self.assertFalse(checked[0]['native_lifecycle_qualified']);self.assertEqual(checked[0]['official_final_credit'],0)
            self.assertFalse((root/'unused-native-output').exists())

    def test_actual_neutral_run_preserves_keyword_default_and_native_disabled_gate(self):
        original=facade.parent.neutral_module();value=facade.neutral_module()
        self.assertEqual(value.run.__kwdefaults__,original.run.__kwdefaults__)
        self.assertIsNot(value.run.__kwdefaults__,original.run.__kwdefaults__)
        with patch.object(value,'validate',side_effect=AssertionError('native preparation reached')):
            with self.assertRaisesRegex(ValueError,'Native neutral pilot disabled'):
                value.run(config_path=ROOT/'work/absent-fixture.private.json',permit_path=None)


if __name__=='__main__':unittest.main()
