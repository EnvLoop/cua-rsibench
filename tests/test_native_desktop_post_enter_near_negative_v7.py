"""Offline negative regressions; fake frames are never real GUI evidence."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageDraw
from native_desktop_factory import v066_post_enter_near_negative_v7 as runner
from native_desktop_factory import v066_post_enter_near_negative_audit_v7 as audit
from native_desktop_factory.verify import S, R, PR


FIXTURE = Path(__file__).resolve().parents[1]/'native_desktop_factory/dev-fixtures/wdi-native-mex-calc-growth'


def png(color='white', *, caret=False):
    picture = Image.new('RGB', (1280,800), 'white')
    draw = ImageDraw.Draw(picture)
    if caret: draw.line((300,350,300,373), fill='black')
    elif color != 'white': draw.rectangle((300,350,330,380), fill=color)
    stream=BytesIO(); picture.save(stream,'PNG'); return stream.getvalue()


def modified_xlsx(raw, oracle, *, address='B5', collateral=False):
    stream=BytesIO()
    with zipfile.ZipFile(BytesIO(raw)) as source, zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as target:
        workbook=ET.fromstring(source.read('xl/workbook.xml'))
        rid=next(s for s in workbook.findall(f'.//{{{S}}}sheet') if s.get('name')=='Review').get(f'{{{R}}}id')
        relationships=ET.fromstring(source.read('xl/_rels/workbook.xml.rels'))
        relative=next(r for r in relationships.findall(f'{{{PR}}}Relationship') if r.get('Id')==rid).get('Target').lstrip('/')
        review_path=relative if relative.startswith('xl/') else 'xl/'+relative
        for name in source.namelist():
            value=source.read(name)
            if name==review_path:
                tree=ET.fromstring(value)
                cells={cell.get('r'):cell for cell in tree.findall(f'.//{{{S}}}c')}
                if address in cells and 'A4' in cells and 'B4' in cells:
                    cell=cells[address]
                    for child in list(cell): cell.remove(child)
                    cell.attrib.pop('t',None)
                    rule=oracle['targets']['Review!B4']
                    ET.SubElement(cell,f'{{{S}}}f').text=rule['formula'].lstrip('=')
                    ET.SubElement(cell,f'{{{S}}}v').text=str(rule['expected_value'])
                    if collateral:
                        cells['A4'].find(f'{{{S}}}is/{{{S}}}t').text='collateral'
                    value=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
            target.writestr(name,value)
    return stream.getvalue()


class Guest:
    def __init__(self,frames,titles=None): self.frames=frames; self.titles=titles or ['train.xlsx - LibreOffice Calc']*len(frames); self.index=0; self.actions=[]
    def get_current_window_id(self): return 'document' if 'train.xlsx' in self.titles[min(self.index,len(self.titles)-1)] else 'modal'
    def get_window_title(self,_): return self.titles[min(self.index,len(self.titles)-1)]
    def screenshot(self): frame=self.frames[min(self.index,len(self.frames)-1)]; self.index+=1; return frame
    def press(self,key): self.actions.append(key)


class NearNegativeTests(unittest.TestCase):
    def sample(self,guest,root,*,capture_ms=0):
        out=root/'probe'; out.mkdir(mode=0o700)
        current=[0]
        def clock(): current[0]+=1_000_000; return current[0]
        def sleep(seconds): current[0]+=int(seconds*1e9)
        if capture_ms:
            original=guest.screenshot
            def screenshot(): current[0]+=capture_ms*1_000_000; return original()
            guest.screenshot=screenshot
        result=runner.probe_no_action(guest,root=root,out=out,filename='train.xlsx',document_id='document',clock=clock,sleep=sleep)
        return out,result

    def test_paid_entry_and_root_review_are_disabled_without_explicit_acceptance(self):
        with self.assertRaisesRegex(ValueError,'disabled'):
            runner.run(freeze_path=Path('/absent'),permit_path=Path('/absent'))
        with self.assertRaisesRegex(ValueError,'root review'):
            audit.review(freeze_path=Path('/absent'),review_path=Path('/absent-review'),permit_path=Path('/absent-permit'))

    def test_exact_independent_permit_refuses_review_and_source_binding_mutation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); freeze=root/'freeze.json'
            runner._write_new(freeze,{'frozen':'bytes'})
            value={'output_root':str(root/'new-output'),'source_sha256s':{'source.py':'a'*64},
                   'prior_full_lease_accounting':{'past_full_lease_seconds':1200}}
            reviewed=root/'review.json'; permit=root/'permit.json'
            with patch.object(audit,'validate_source',return_value=value),patch.object(audit,'storage_audit',return_value={'dispatch_storage_ready':True}):
                audit.review(freeze_path=freeze,review_path=reviewed,permit_path=permit,
                    independent_root_review_accepted=True,review_note='Independent offline test acceptance only',active_probe=lambda:(set(),0))
            audit.checked_permit(freeze_path=freeze,permit_path=permit,value=value)
            changed={**value,'source_sha256s':{'source.py':'b'*64}}
            with self.assertRaisesRegex(ValueError,'binding changed'):
                audit.checked_permit(freeze_path=freeze,permit_path=permit,value=changed)
            private=json.loads(reviewed.read_bytes()); private['guest_maximum']=7
            reviewed.write_bytes(runner.encode(private))
            with self.assertRaisesRegex(ValueError,'binding changed'):
                audit.checked_permit(freeze_path=freeze,permit_path=permit,value=value)

    def test_run_schedule_is_six_once_and_failure_never_launches_following_guest(self):
        for fail in [False,True]:
            with self.subTest(failure=fail),TemporaryDirectory() as directory:
                base=Path(directory); root=base/'new-output'; freeze=base/'freeze.json';permit=base/'permit.json'
                runner._write_new(freeze,{'frozen':'test'});runner._write_new(permit,{'permit':'test'})
                value={'output_root':str(root),'source_sha256s':{},'cases':[{'case':x[0]} for x in runner.CASES]}
                calls=[]
                def fake_one(**kwargs):
                    calls.append((kwargs['ordinal'],kwargs['attempt']))
                    out=root/f'{kwargs["ordinal"]:02d}-{kwargs["source"]["case"]}-{kwargs["attempt"]}'
                    out.mkdir(mode=0o700)
                    runner._write_new(out/'intent.json',{'lease_seconds':600})
                    receipt={'status':'stopped_for_reconciliation' if fail else 'cold_reset_observed'}
                    runner._write_new(out/'receipt.json',receipt);return receipt
                trap=SimpleNamespace(create=lambda **kwargs: self.fail('No real/fake provider create belongs to scheduler test'))
                with patch.object(runner,'validate_source',return_value=value),patch.object(audit,'checked_permit',return_value={}),patch.object(runner.importlib.metadata,'version',side_effect=lambda name:runner.SDK_VERSIONS[name]),patch.dict(runner.os.environ,{'E2B_API_KEY':'offline-test-placeholder'}),patch.object(runner,'active_hashes',return_value=(set(),0)),patch.object(runner,'_one',side_effect=fake_one),patch.dict('sys.modules',{'e2b_desktop':SimpleNamespace(Sandbox=trap)}),patch.object(audit,'audit',return_value={'status':'offline_scheduler_test_only'}):
                    result=runner.run(freeze_path=freeze,permit_path=permit,enable_paid_train_near_negative=True)
                    self.assertEqual(len(calls),1 if fail else 6)
                    self.assertEqual(result['full_lease_intents'],len(calls))
                    with self.assertRaisesRegex(ValueError,'replayed'):
                        runner.run(freeze_path=freeze,permit_path=permit,enable_paid_train_near_negative=True)

    def test_wrong_saved_target_is_zero_and_correct_target_or_collateral_is_rejected(self):
        baseline=(FIXTURE/'wdi-native-mex-calc-growth.xlsx').read_bytes()
        oracle=json.loads((FIXTURE/'oracle.json').read_bytes())
        saved=modified_xlsx(baseline,oracle)
        score=audit.wrong_target_score(baseline,saved,oracle)
        self.assertEqual(score['task_score'],0)
        self.assertTrue(score['intended_target_unchanged'])
        for invalid in [baseline,modified_xlsx(baseline,oracle,address='B4'),modified_xlsx(baseline,oracle,collateral=True)]:
            with self.assertRaises(ValueError): audit.wrong_target_score(baseline,invalid,oracle)

    def test_real_modal_boundary_stops_capture_and_dispatches_no_action(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); guest=Guest([png()]*8,['Save As']*8)
            out,result=self.sample(guest,root)
            self.assertEqual(result['raw_samples'],1)
            self.assertEqual(guest.actions,[])
            checked=audit.audit_samples(root=root,out=out,filename='train.xlsx',document_id='document')
            self.assertEqual(checked['classification'],'real_modal_stop')

    def test_material_oscillation_stops_but_caret_and_stability_stay_inconclusive(self):
        examples=[([png('red'),png('blue'),png('red')],'real_material_oscillation_stop',3),
                  ([png(),png(caret=True)]*4,'caret_only_probe_material_oscillation_inconclusive',8),
                  ([png()]*8,'no_material_oscillation_observed_inconclusive',8)]
        for frames,classification,count in examples:
            with self.subTest(classification=classification),TemporaryDirectory() as directory:
                root=Path(directory); guest=Guest(frames); out,result=self.sample(guest,root)
                checked=audit.audit_samples(root=root,out=out,filename='train.xlsx',document_id='document')
                self.assertEqual(checked['classification'],classification)
                self.assertEqual(result['raw_samples'],count)
                self.assertEqual(guest.actions,[])

    def test_raw_frame_window_hash_and_timing_tampering_are_rejected(self):
        for kind in ['raw','window','timing','order']:
            with self.subTest(kind=kind),TemporaryDirectory() as directory:
                root=Path(directory); out,_=self.sample(Guest([png()]*8),root)
                path=out/'samples.ndjson'; rows=[json.loads(x) for x in path.read_bytes().splitlines()]
                if kind=='raw': (out/'probe-07.png').write_bytes(png('red'))
                elif kind=='window': rows[0]['window_id_before_sha256']='f'*64
                elif kind=='timing': rows[2]['monotonic_before_ns']=0
                else: rows[0]['ordinal']=3
                if kind!='raw': path.write_bytes(b''.join(runner.encode(x) for x in rows))
                with self.assertRaises(ValueError): audit.audit_samples(root=root,out=out,filename='train.xlsx',document_id='document')

    def test_capture_latency_is_included_in_wall_stop_and_not_scored_as_oscillation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); out,result=self.sample(Guest([png()]*8),root,capture_ms=6500)
            self.assertLess(result['raw_samples'],8)
            self.assertEqual(audit.audit_samples(root=root,out=out,filename='train.xlsx',document_id='document')['classification'],'wall_bound_stop_infrastructure_invalid')

    def test_full_lease_metadata_pairs_once_and_lost_create_ack_is_charged(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for name,intent_only in [('ack',False),('no-ack',True)]:
                out=root/name; out.mkdir()
                intent={'schema':runner.INTENT_SCHEMA,'lease_seconds':600,'package_sha256':name}
                (out/'intent.json').write_bytes(runner.encode(intent))
                if not intent_only:
                    (out/'receipt.json').write_bytes(runner.encode({'schema':runner.RECEIPT_SCHEMA,'lease_seconds':600,'sandbox_id_sha256':'a'*64}))
            ledger=runner.lease_accounting([root,root])
            self.assertEqual(ledger['past_full_lease_intents'],2)
            self.assertEqual(ledger['past_full_lease_seconds'],1200)
            self.assertIsNone(ledger['lane_spending_cap_usd'])
            self.assertEqual(runner.lease_accounting([root],exclude=root/'no-ack')['past_full_lease_intents'],1)
            legacy=root/'legacy'; legacy.mkdir()
            (legacy/'batch-receipt.json').write_bytes(runner.encode({'schema':'cua-native-impress-batch-normalization-v1','lease_seconds':1000}))
            self.assertEqual(runner.lease_accounting([root])['past_full_lease_seconds'],2200)

    def test_consumed_lost_create_intent_never_retries(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); evidence=root/'evidence'; evidence.mkdir()
            row=json.loads((FIXTURE/'package.json').read_bytes())
            source={'case':'wrong-target','row':row,'filename':'train.xlsx'}
            value={'output_root':str(evidence),'candidate_root':str(root)}
            baseline=(FIXTURE/'wdi-native-mex-calc-growth.xlsx').read_bytes()
            oracle=json.loads((FIXTURE/'oracle.json').read_bytes())
            calls=[]
            def failed_create(**kwargs): calls.append(kwargs); raise ConnectionError('lost acknowledgement')
            with patch.object(runner,'active_hashes',return_value=(set(),0)),patch.object(runner,'host_power_snapshot',return_value={'source':'AC Power'}),patch.object(runner.admit,'_package',return_value=(FIXTURE,baseline,oracle)):
                result=runner._one(value=value,source=source,attempt='case',ordinal=0,freeze_sha='f'*64,permit_sha='e'*64,sandbox_factory=failed_create)
                self.assertEqual(result['status'],'cleanup_unverified')
                with self.assertRaisesRegex(ValueError,'replayed'):
                    runner._one(value=value,source=source,attempt='case',ordinal=0,freeze_sha='f'*64,permit_sha='e'*64,sandbox_factory=failed_create)
            self.assertEqual(len(calls),1)
            self.assertEqual(runner.lease_accounting([evidence])['past_full_lease_seconds'],600)


if __name__=='__main__': unittest.main()
