"""Actual episode/RPC proof with synthetic native guest and model future."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cursibench import scale_vision_proxy as vision
from native_desktop_factory import deadline_model_transport_v21 as transport
from native_desktop_factory import qwen_sampler_process_v21 as rpc
from native_desktop_factory import prospective_model_worker_v21 as worker
from native_desktop_factory import model_transport_integration_v21 as integration
from native_desktop_factory import train_weak_base_pilot_v21 as pilot
from native_desktop_factory.factory import digest
from tests.test_native_desktop_deadline_runtime_v21 import Clock,sampler_path
from tests.test_native_desktop_uniform_model_transport_v11 import FakeModelGuest
from tests.test_native_desktop_selection_worker_v066 import source_case
from tests.test_structural_guest_attestation_v16 import fixture
from cursibench import full_study_runtime_v2 as runtime


def create(study,owner_slot,root,identity,*,attempt_id=None,checkpoint_path=None,session=None):
    root=Path(root).resolve();root.mkdir(mode=0o700,parents=True)
    source,_neutral,positive,oracle,extension=source_case('calc-growth');clock=Clock()
    def save(path,value):
        runtime.campaign._private_write_new(path,runtime.policy.canonical(value))
        return {'path':str(path),'sha256':digest(path.read_bytes())}
    guest_ref=root/'guest.json';save(guest_ref,fixture()[2])
    map_path=root/'map.json';salt_ref=save(map_path,{'variant_salt':'offline-only-'*4})
    admitted={'guest_public':str(guest_ref),'scoped_reference':str(root/'profile'),'private_map':str(map_path)}
    package={'identity':identity,'source':source,'oracle':oracle,'filename':'train'+extension,
        'instruction':'synthetic public TRAIN task','guest_reference_path':str(guest_ref)}
    sampler,child,clean,backend,service=sampler_path(root,clock)
    sampler.process.plan=study.manifest_sha256
    actual_serve=rpc.serve
    def serve_with_policy(root,journal,old_plan,**kwargs):
        return actual_serve(root,journal,study.manifest_sha256,**kwargs)
    checkpoint=None if owner_slot=='shared-base' else (checkpoint_path or 'tinker://synthetic/sampler_weights/'+owner_slot)
    checkpoint_sha=vision.digest(vision.MODEL) if checkpoint is None else digest(checkpoint.encode())
    backend.identity.update(sampling_kind='base' if checkpoint is None else 'checkpoint',checkpoint_sha256=checkpoint_sha)
    clean.checkpoint_sha256=checkpoint_sha
    streams=SimpleNamespace(stdin=child.stdin,stdout=child.stdout,stderr=io.StringIO())
    if session is None:
        paid=pilot.PilotPaidCalls({'source_sha256s':integration.proposal()['source_sha256s']},root/'paid',sampler)
        if attempt_id is not None:paid.attempt_id=attempt_id
    else:
        paid=worker.PaidCalls(attempt_id=attempt_id,checkpoint=checkpoint_sha,identities=session.views['selection'],
            output_dir=root,runtime=integration.proposal()['worker_runtime_sha256'],quote='1',session=session)
    made=[]
    def create_guest(**kw):
        guest=FakeModelGuest(kw['root'],kw['out'],kw['filename'],source,positive,kw['out'].name,identity)
        if kw['out'].name=='actor':
            observe=guest.observe
            def near_deadline(**arguments):
                clock.now=730-3.57152125;return observe(**arguments)
            guest.observe=near_deadline
        made.append(guest);return guest
    model=worker.DesktopProspectiveModelWorker(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'))
    with patch.object(rpc,'sys',streams),patch.object(rpc,'serve',serve_with_policy),patch('cursibench.full_study_qwen_runtime_gate_v1.pre_dispatch',return_value={'runtime_spec_sha256':'d'*64,'toy_public_receipt_sha256':'e'*64,'runtime_gate_source_sha256':'f'*64}),\
        patch.object(rpc.select,'select',return_value=([child.stdout],[],[])),patch.object(transport.time,'monotonic',clock),\
        patch.object(transport,'create_guest',side_effect=create_guest),\
        patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes',return_value=([],0)):
        child.thread.start()
        paid.invoke(suffix='sampler-setup',category='tinker',request={'sampling_kind':'base' if checkpoint is None else 'checkpoint'},
            provider=lambda _:sampler.start(checkpoint_path=checkpoint,checkpoint_sha256=checkpoint_sha,
                seed=23,max_output_tokens=128,attempt_id=owner_slot))
        result,out,trace,elapsed,outcome=model._episode(admitted=admitted,package=package,ordinal=0,batch=root,paid=paid,sampler=sampler)
        sampler.close(False)
    original=root/('source'+extension);runtime.campaign._private_write_new(original,source)
    description={k:v for k,v in package.items() if k!='source'}
    description['source_ref']={'path':str(original),'sha256':digest(source)}
    descriptor={'batch':str(root),'evaluator':str(out),'package_ref':save(root/'package.json',description),
        'salt_ref':salt_ref,'checkpoint_sha256':checkpoint_sha}
    receipt=runtime.verify_budget_artifacts(study,owner_slot,descriptor)
    return descriptor,receipt,made
