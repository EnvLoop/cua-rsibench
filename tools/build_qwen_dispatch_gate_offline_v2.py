"""Fresh offline source evidence; preserve the published September receipt."""
from hashlib import sha256
import json,os
from pathlib import Path
try:
    from tools import build_qwen_dispatch_gate_offline_v1 as parent
except ModuleNotFoundError:
    import build_qwen_dispatch_gate_offline_v1 as parent

ROOT=parent.ROOT
OUTPUT=ROOT/'docs/evidence/qwen38-dispatch-gate-offline-2026-10-02.json'
BUILDER='tools/build_qwen_dispatch_gate_offline_v2.py'
SCHEMA='cua-qwen38-dispatch-gate-offline-evidence-v2'
EvidenceError=parent.EvidenceError
SOURCE_PATHS=parent.SOURCE_PATHS
FOCUSED_TEST_COUNT=parent.FOCUSED_TEST_COUNT

def expected_receipt(*,focused_test_count):
    value=parent.expected_receipt(focused_test_count=focused_test_count)
    return {**value,'schema':SCHEMA,'current_builder_sha256':parent._sha(BUILDER),
        'historical_receipt':{'path':parent.OUTPUT.relative_to(ROOT).as_posix(),
            'sha256':sha256(parent.OUTPUT.read_bytes()).hexdigest()},
        'historical_receipt_replaced':False,'historical_native_qualification_promoted':False}

def audit_receipt(receipt):
    parent._require(type(receipt) is dict and receipt==expected_receipt(focused_test_count=FOCUSED_TEST_COUNT),
        'offline_evidence_receipt_or_source_changed')
    return receipt

def main():
    parent._require(not OUTPUT.exists() and not OUTPUT.is_symlink(),'offline_evidence_output_exists')
    count=parent._network_blocked_focused_suite()
    receipt=expected_receipt(focused_test_count=count)
    raw=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()
    fd=os.open(OUTPUT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    audit_receipt(json.loads(OUTPUT.read_bytes()))
    print(json.dumps({'schema':SCHEMA,'focused_fake_provider_tests_passed':count,
        'real_provider_calls_by_builder':0,'historical_receipt_replaced':False},sort_keys=True))

if __name__=='__main__':main()
