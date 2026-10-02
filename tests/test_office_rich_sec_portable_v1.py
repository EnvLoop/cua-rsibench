"""Current rich SEC replay, frozen graph integrity and distinct local reset."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from zipfile import ZipFile

from sec_excel_factory.rich_private_replay_v1 import _metadata, prepare
from tools.office_current_package_v5 import Package, _worker

PRIVATE_ROOT = Path(__file__).resolve().parents[1].parent.parent / '2026-09-25/excel-real-100/work/private-excel'


class RichPortableGuards(unittest.TestCase):
    def test_current_inventory_rejects_legacy_excel_before_any_package_read(self):
        from tools.office_rich_package_inventory_v6 import combine
        from tools.office_owned_folder_runtime_v2 import write_new,canonical
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ppt=root/'ppt.json';rich=root/'legacy.json'
            write_new(ppt,canonical([]));write_new(rich,canonical([{'cell_id':'excel-web'}]))
            with self.assertRaisesRegex(ValueError,'legacy SEC is excluded'):
                combine(ppt_metadata_index=ppt,rich_metadata_index=rich,output_index=root/'must-not-exist.json')
            self.assertFalse((root/'must-not-exist.json').exists())

    def test_all_four_roles_bind_rich_adapter_and_restore_original_globals(self):
        from tools.office_current_facade_v5 import source_epoch,neutral_module,current_sources
        from tools import office_current_authority_v4 as authority
        original_package=authority.Package
        with source_epoch() as modules:
            for name in ('authority','workers','budget_performance'):
                self.assertIs(modules[f'tools/office_current_{name}_v4.py'].Package,Package)
            execution=modules['tools/office_current_execution_v4.py']
            teacher=modules['tools/office_current_teacher_v4.py']
            workers=modules['tools/office_current_workers_v4.py']
            self.assertIs(execution.Authority,authority.Authority)
            self.assertIs(teacher.Authority,authority.Authority)
            self.assertIs(workers.Authority,authority.Authority)
            self.assertIs(teacher.TaskWorker,execution.TaskWorker)
            self.assertIs(workers.TaskWorker,execution.TaskWorker)
            self.assertIs(neutral_module().runtime.Package,Package)
            protocol=modules['tools/office_current_protocol_v4.py']
            manifest=protocol.source_manifest(Path(__file__).resolve().parents[1])
            self.assertEqual(manifest['office_current_source_epoch'],'original-office-current-rich-v5')
            self.assertIn('tools/office_current_facade_v5.py',manifest['source_sha256s'])
            self.assertIn('tools/office_current_package_v4.py',manifest['source_sha256s'])
            self.assertFalse(manifest['office_native_qualification_claimed'])
        self.assertIs(authority.Package,original_package)

    def test_current_source_pin_rejects_old_or_modified_auditor_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'audit_integrated_private_split.py').write_text('raise AssertionError("must not execute")')
            with self.assertRaisesRegex(ValueError, 'source epoch changed'):
                _metadata(root)

    def test_archive_root_escape_is_rejected_before_graph_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); archive=root/'oracle.zip'
            with ZipFile(archive,'w') as out: out.writestr('../escaped.py', 'raise AssertionError("must not execute")')
            request=root/'request.json';request.write_text(json.dumps({'archive':str(archive)}))
            with self.assertRaisesRegex(ValueError, 'archive path invalid'):
                _worker(request)
            self.assertFalse((root.parent/'escaped.py').exists())


@unittest.skipUnless(PRIVATE_ROOT.is_dir(), 'Evaluator-private current SEC corpus is not distributed publicly')
class RichOriginalGraphControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.output=cls.root/'replay'
        cls.receipt=prepare(private_root=PRIVATE_ROOT,output_root=cls.output,case_ordinals=[0,20,40,139])
        cls.rows=json.loads((cls.output/'execution-metadata-index.private.json').read_bytes())

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def package(self,index=0):
        row=self.rows[index];return Package(row['descriptor'],package_root=row['package_root'])

    def test_actual_graph_controls_are_not_full_or_native_admission(self):
        self.assertEqual(self.receipt['scope'],'explicit-development-subset')
        self.assertEqual(self.receipt['packages'],4)
        self.assertEqual(self.receipt['isolated_fault_rejections'],36)
        self.assertEqual(self.receipt['positive_reference_passes'],4)
        self.assertEqual(self.receipt['native_calls'],0)
        self.assertEqual(self.receipt['model_calls'],0)
        self.assertEqual(self.receipt['gui_admitted_final_count'],0)
        self.assertIsNone(self.receipt['original_final_graph_count'])
        for index in range(4):
            package=self.package(index)
            self.assertEqual(package.strict_score(package.root/'reference.private.xlsx')['score'],1)
            self.assertEqual(package.strict_score(package.paths['baseline'])['score'],0)
            projection=package.actor_projection()
            self.assertNotIn('private_oracle',projection);self.assertNotIn('case_manifest',projection)
            self.assertNotIn('reference',projection);self.assertNotIn('source_excerpt_path',projection)
            controls=json.loads((package.root/'offline-controls.private.json').read_bytes())
            self.assertEqual(len(controls['scored_artifact_refs']),11)
            from hashlib import sha256
            for ref in controls['scored_artifact_refs']:
                self.assertEqual(sha256((package.root/ref['path']).read_bytes()).hexdigest(),ref['sha256'])

    def test_source_archive_and_excerpt_corruption_are_fail_closed(self):
        package=self.package();isolated=self.root/'corrupt';shutil.copytree(package.root,isolated)
        changed=Package(isolated/'package.private.json',package_root=isolated)
        (isolated/'source-excerpt.private.json').write_bytes(b'{}');(isolated/'source-excerpt.private.json').chmod(0o600)
        with self.assertRaisesRegex(ValueError,'artifact changed'):
            changed.strict_score(isolated/'reference.private.xlsx')
        (isolated/'source-excerpt.private.json').write_bytes(package.paths['source_excerpt'].read_bytes())
        (isolated/'original-graph-source.private.zip').write_bytes(b'bad archive')
        with self.assertRaisesRegex(ValueError,'artifact changed'):
            changed.strict_score(isolated/'reference.private.xlsx')

    def test_reset_copy_distinct_equal_and_never_native(self):
        package=self.package();target=self.root/'reset.xlsx'
        result=package.fresh_copy_reset(target)
        self.assertFalse(result['native_reset_verified'])
        self.assertEqual(result['official_final_credit'],0)
        self.assertNotEqual(target.resolve(),package.paths['baseline'].resolve())
        self.assertEqual(target.read_bytes(),package.paths['baseline'].read_bytes())
        with self.assertRaisesRegex(ValueError,'Distinct reset'):
            package.fresh_copy_reset(package.paths['baseline'])

    def test_wrong_structure_is_task_failure_not_source_failure(self):
        package=self.package();candidate=self.root/'wrong-structure.xlsx'
        # Preserve OOXML validity but change one native worksheet identity.
        with ZipFile(package.root/'reference.private.xlsx') as original, ZipFile(candidate,'w') as out:
            for item in original.infolist():
                raw=original.read(item.filename)
                if item.filename=='xl/workbook.xml':
                    from xml.etree import ElementTree as ET
                    root=ET.fromstring(raw);ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    root.find('m:sheets/m:sheet',ns).set('name','Unexpected sheet');raw=ET.tostring(root)
                out.writestr(item,raw)
        result=package.strict_score(candidate)
        self.assertEqual(result['score'],0)
        self.assertEqual(result['raw_strict']['counterfactual_profiles'],0)

    def test_duplicate_or_out_of_range_source_subsets_rejected(self):
        for indices in ([0,0],[-1],[140]):
            with self.subTest(indices=indices), self.assertRaisesRegex(ValueError,'subset ordinal invalid'):
                prepare(private_root=PRIVATE_ROOT,output_root=self.root/('bad-'+str(indices)),case_ordinals=indices)


if __name__=='__main__':unittest.main()
