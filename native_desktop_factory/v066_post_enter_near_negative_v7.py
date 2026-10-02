"""One-use, source-disjoint public-TRAIN calibration; paid entry is locked.

Preparation reads inventory metadata and three TRAIN packages only. Execution
requires an independent exact permit and an explicit flag, consumes its run
root before any provider create, and never retries a consumed intent. No final
task, oracle, admission or model is available through this entry point.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import json
import os
from pathlib import Path
import time

from . import admit, qwen_v066_adapter as adapter, runtime_fingerprint_probe
from . import v066_scoped_profile_guard as profile_guard
from .gui_control_shell import wait_for_document_ready
from .qwen_v064_adapter import application_frame_digest
from .reconcile_interrupted_sweep import active_hashes
from .v066_post_enter_train_calibration_v1 import (
    SDK_VERSIONS, _now, _persist, _private, _write_new, digest,
)
from .v066_scoped_profile_reference import validate_reference
from .v066_scoped_calc_writer_train_demo import RecordingDesktop, actor_actions
from .v066_storage_budget import audit as storage_audit, reserve_and_write
from .v066_train20_worker import host_power_snapshot
from .source import EXPECTED_SHA256


SCHEMA = "cua-native-wdi-v066-post-enter-near-negative-freeze-private-v7"
PUBLIC_SCHEMA = "cua-native-wdi-v066-post-enter-near-negative-freeze-public-v7"
INTENT_SCHEMA = "cua-native-wdi-v066-post-enter-near-negative-intent-v7"
RECEIPT_SCHEMA = "cua-native-wdi-v066-post-enter-near-negative-receipt-v7"
RUN_SCHEMA = "cua-native-wdi-v066-post-enter-near-negative-run-v7"
LEASE_SECONDS = 600
MAX_GUESTS = 6
SAMPLE_DELAYS_MS = (0, 250, 250, 250, 250, 250, 250, 250)
MAX_PROBE_WALL_MS = 30_000
INVENTORY_SHA256 = "0e1f1800fa8a3a647a4215296afac020affd844b8e5f735aa27d02ef29592ac0"
TRAIN_PLAN_SHA256 = "63ba79fad62eedfb54a5bb1baaa0e64f6e56f4765b62c57cf0d7633c1866c0db"
CASES = (("wrong-target", "FIN"), ("modal-stop", "FRA"), ("no-action-probe", "SWE"))
TRUSTED_STIMULI = {'modal-stop': 'Control+Shift+S', 'no-action-probe': 'F2'}
SOURCE_FILES = (
    "native_desktop_factory/v066_post_enter_near_negative_v7.py",
    "native_desktop_factory/v066_post_enter_near_negative_audit_v7.py",
    "native_desktop_factory/v066_post_enter_train_calibration_v1.py",
    "native_desktop_factory/v066_train20_worker.py",
    "native_desktop_factory/v066_scoped_calc_writer_train_demo.py",
    "native_desktop_factory/v066_scoped_profile_guard.py",
    "native_desktop_factory/v066_scoped_profile_reference.py",
    "native_desktop_factory/v066_profile_scope_analysis.py",
    "native_desktop_factory/runtime_fingerprint_probe.py",
    "native_desktop_factory/qwen_v064_adapter.py",
    "native_desktop_factory/qwen_v066_adapter.py",
    "native_desktop_factory/gui_control_shell.py",
    "native_desktop_factory/reconcile_interrupted_sweep.py",
    "native_desktop_factory/v066_storage_budget.py",
    "native_desktop_factory/admit.py", "native_desktop_factory/verify.py",
    "native_desktop_factory/source.py", "native_desktop_factory/factory.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_action_output_v064.py",
    "tests/test_native_desktop_post_enter_near_negative_v7.py",
)


def encode(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def source_hashes() -> dict:
    repo = Path(__file__).resolve().parents[1]
    return {name: digest((repo / name).read_bytes()) for name in SOURCE_FILES}


def lease_accounting(roots: list[Path], *, exclude: Path | None = None) -> dict:
    """Read lease metadata only; pair same-directory intent/receipt once.

    No OOXML, oracle, actor instruction, screenshot or final scoring file is
    opened. Lost acknowledgements consume the full requested lease. Legacy
    acknowledged creates lacking a lease field reserve the historical 600 s.
    """
    candidates = set()
    for root in roots:
        for pattern in ("intent.json", "receipt.json", "batch-receipt.json", "health-probe*.json"):
            for path in root.rglob(pattern):
                if path.is_symlink():
                    raise ValueError("Lease metadata symlink is unsafe")
                if (exclude is None or not path.resolve().is_relative_to(exclude.resolve())):
                    candidates.add(path.resolve())
    records: dict[str, dict] = {}
    used_packages = set()
    for path in sorted(candidates):
        if path.is_symlink():
            raise ValueError("Lease metadata symlink is unsafe")
        raw = path.read_bytes()
        value = json.loads(raw)
        if not str(value.get("schema", "")).startswith("cua-native-"):
            continue
        is_intent = path.name == "intent.json"
        has_provider = (value.get("sandbox_id_sha256") or
                        value.get("sandbox_timeout_seconds") or
                        value.get("lease_seconds") or
                        value.get("stage") == "create_desktop")
        if not is_intent and not has_provider:
            continue
        lease = value.get("lease_seconds", value.get("sandbox_timeout_seconds", 600))
        if type(lease) is not int or not 1 <= lease <= 86_400:
            raise ValueError("Historical full server lease metadata is invalid")
        key = str(path.parent)
        # Health probes coexist with a task receipt but use a separate guest.
        if path.name.startswith("health-probe"):
            key = str(path)
        row = records.setdefault(key, {"lease_seconds": lease, "metadata_sha256s": [], "sandbox_id_sha256": None})
        if row["lease_seconds"] != lease:
            raise ValueError("Intent and receipt lease metadata disagree")
        row["metadata_sha256s"].append(digest(raw))
        sid = value.get('sandbox_id_sha256')
        if sid:
            if row['sandbox_id_sha256'] not in (None, sid):
                raise ValueError('A create directory names multiple provider guests')
            row['sandbox_id_sha256'] = sid
        if value.get("package_sha256"):
            used_packages.add(value["package_sha256"])
    # Profile/observer receipts can refer to an existing acknowledged guest.
    # Group that identity once using the longest full lease, retaining every
    # metadata digest. No-ID create attempts still reserve their own lease.
    grouped = {}
    for row in records.values():
        row['metadata_sha256s'] = sorted(set(row['metadata_sha256s']))
        identity = row['sandbox_id_sha256'] or digest(encode(row))
        item = grouped.setdefault(identity, {'lease_seconds': row['lease_seconds'], 'metadata_sha256s': []})
        item['lease_seconds'] = max(item['lease_seconds'], row['lease_seconds'])
        item['metadata_sha256s'] = sorted(set(item['metadata_sha256s']) | set(row['metadata_sha256s']))
    items = sorted(grouped.values(), key=lambda row: encode(row))
    seconds = sum(row["lease_seconds"] for row in items)
    return {"past_full_lease_intents": len(items), "past_full_lease_seconds": seconds,
            "past_full_lease_usd_planning_upper": str(Decimal(seconds) / Decimal(3600)),
            "metadata_ledger_sha256": digest(encode(items)),
            "used_package_sha256s": sorted(used_packages),
            "lane_spending_cap_usd": None, "actual_provider_billed_usd": None}


def train_sources(train_plan: Path) -> tuple[dict, list[dict]]:
    raw = _private(train_plan)
    plan = json.loads(raw)
    if (digest(raw) != TRAIN_PLAN_SHA256 or
            plan.get("schema") != "cua-native-wdi-v066-train20-source-plan-private-v1" or
            len(plan.get("train_rows", [])) != 20 or
            len(plan.get("sft_task_ids", [])) != 15 or
            len(plan.get("holdout_task_ids", [])) != 5 or
            set(plan["sft_task_ids"]) & set(plan["holdout_task_ids"])):
        raise ValueError("Original frozen TRAIN 15/5 source plan changed")
    candidate = Path(plan["candidate_root"])
    inventory_raw = (candidate / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    rows = inventory.get("tasks", [])
    if (digest(inventory_raw) != INVENTORY_SHA256 or
            plan["candidate_inventory_sha256"] != INVENTORY_SHA256 or
            inventory.get("source_sha256") != EXPECTED_SHA256 or
            inventory.get("design_revision") != "v2-distinct-structures" or
            inventory.get("counts") != {"train": 20, "selection": 20, "final_candidate": 100} or
            len(rows) != 140 or len({r["task_id"] for r in rows}) != 140):
        raise ValueError("Pinned 20/20/100 inventory metadata changed")
    owners = {}
    for row in rows:
        for family in ([('source', x) for x in row['source_groups']] +
                       [('template', row['template_group']), ('instance', row['instance_group'])]):
            if owners.setdefault(family, row['split']) != row['split']:
                raise ValueError("Inventory source/template/instance split leakage")
    selected = []
    for case, country in CASES:
        matches = [r for r in rows if r['split'] == 'train' and
                   r['workflow'] == 'calc-growth' and r['source_groups'] == [f'wdi-country:{country}']]
        if len(matches) != 1:
            raise ValueError("Distinct pinned TRAIN Calc-growth source absent")
        row = matches[0]
        if row['task_id'] not in plan['sft_task_ids'] or row['task_id'] in plan['holdout_task_ids']:
            raise ValueError("Diagnostic heldout TRAIN source cannot be read")
        # This is the only task-package read. No selection/final package opens.
        directory, baseline, oracle = admit._package(candidate, row)
        if list(oracle.get('targets', {})) != ['Review!B4']:
            raise ValueError("TRAIN single-target Calc structure changed")
        source = next((r for r in plan['train_rows'] if r['task_id'] == row['task_id']), {})
        if any(source.get(k) != row[v] for k, v in (
                ('package_sha256', 'package_sha256'), ('input_sha256', 'input_sha256'),
                ('oracle_sha256', 'oracle_sha256'), ('instruction_sha256', 'actor_task_sha256'))):
            raise ValueError("TRAIN package differs from diagnostic frozen plan")
        selected.append({"case": case, "row": row, "filename": directory.name + '.xlsx',
                         "trusted_calibration_stimulus": TRUSTED_STIMULI.get(case),
                         "actions_sha256": digest(encode(actions_for(case, oracle)))})
    if len({s['row']['package_sha256'] for s in selected}) != 3:
        raise ValueError("TRAIN cases reused a package")
    return plan, selected


def actions_for(case: str, oracle: dict) -> list[dict]:
    navigation = actor_actions('calc', oracle)[:6]
    if case == 'wrong-target':
        actions = actor_actions('calc', oracle)
        actions[4] = {"type": "type", "text": "B5", "mode": "insert"}
        return actions
    if case in TRUSTED_STIMULI:
        return navigation
    raise ValueError("Only three source-frozen TRAIN cases are supported")


def prepare(*, train_plan: Path, work_root: Path, accounting_roots: list[Path],
            output_root: Path, guest_public: Path, scoped_reference: Path,
            freeze_path: Path, public_path: Path) -> dict:
    paths = [train_plan, work_root, output_root, guest_public, scoped_reference,
             freeze_path, public_path, *accounting_roots]
    if (not all(p.is_absolute() for p in paths) or
            any(p.exists() or p.is_symlink() for p in [output_root, freeze_path, public_path]) or
            output_root.parent.resolve() != (work_root / 'gui-diagnostics').resolve()):
        raise ValueError("Exclusive absolute source/launch paths required")
    plan, selected = train_sources(train_plan)
    ledger = lease_accounting(accounting_roots)
    if set(s['row']['package_sha256'] for s in selected) & set(ledger['used_package_sha256s']):
        raise ValueError("A proposed TRAIN source already has a paid create intent or receipt")
    reference, reference_sha = validate_reference(scoped_reference)
    guest = json.loads(guest_public.read_bytes())
    if ('calc' not in reference['applications'] or
            guest.get('scoped_guest_content_identity_passed') is not True):
        raise ValueError("Reviewed Calc profile and guest identity required")
    value = {"schema": SCHEMA, "status": "source_frozen_no_dispatch", "created_utc": _now(),
             "train_plan": str(train_plan), "train_plan_sha256": digest(_private(train_plan)),
             "candidate_root": plan['candidate_root'], "inventory_sha256": INVENTORY_SHA256,
             "work_root": str(work_root), "accounting_roots": [str(p) for p in accounting_roots],
             "output_root": str(output_root), "public_path": str(public_path),
             "guest_public": str(guest_public), "guest_public_sha256": digest(guest_public.read_bytes()),
             "scoped_reference": str(scoped_reference), "scoped_reference_sha256": reference_sha,
             "source_sha256s": source_hashes(), "cases": selected, "prior_full_lease_accounting": ledger,
             "maximum_new_full_lease_intents": MAX_GUESTS, "lease_seconds_each": LEASE_SECONDS,
             "new_full_lease_usd_planning_upper": '1', "lane_spending_cap_usd": None,
             "sample_delays_ms": list(SAMPLE_DELAYS_MS), "max_probe_wall_ms": MAX_PROBE_WALL_MS,
             "dispatch_authorized": False, "same_intent_replay_authorized": False,
             "official_final_admissions": 0, "official_model_results": 0}
    freeze_sha = _write_new(freeze_path, value)
    public = {"schema": PUBLIC_SCHEMA, "status": "train_only_source_frozen_pending_root_review",
              "private_freeze_sha256": freeze_sha, "source_sha256s": value['source_sha256s'],
              "source_scope": "three_unused_distinct_visible_train_calc_growth_families",
              "candidate_inventory_sha256": INVENTORY_SHA256, "train_plan_sha256": TRAIN_PLAN_SHA256,
              "selected_train_packages": 3, "heldout_packages_read": 0, "selection_final_packages_read": 0,
              "new_guest_maximum": MAX_GUESTS, "lease_seconds_each": LEASE_SECONDS,
              "full_lease_reservation_usd_planning_upper": '1', "lane_spending_cap_usd": None,
              "prior_full_lease_intents": ledger['past_full_lease_intents'],
              "prior_full_lease_seconds": ledger['past_full_lease_seconds'],
              "private_lease_metadata_ledger_sha256": ledger['metadata_ledger_sha256'],
              "independent_saved_wrong_target_score_zero_required": True,
              "real_modal_stop_required": True, "three_fresh_original_byte_resets_required": True,
              "real_oscillation_claim_requires_raw_evidence": True,
              "no_observed_material_oscillation_is_inconclusive": True,
              "restricted_train_calibration_stimuli_outside_model_contract": True,
              "shared_final_action_contract_changed": False,
              "sample_delays_ms": list(SAMPLE_DELAYS_MS), "max_probe_wall_ms": MAX_PROBE_WALL_MS,
              "dispatch_authorized": False, "same_intent_replay_authorized": False,
              "official_final_admissions": 0, "official_model_results": 0}
    _write_new(public_path, public, public=True)
    return public


def validate_source(freeze_path: Path, *, require_unused: bool = True) -> dict:
    raw = _private(freeze_path)
    value = json.loads(raw)
    if (value.get('schema') != SCHEMA or value.get('status') != 'source_frozen_no_dispatch' or
            value.get('source_sha256s') != source_hashes() or
            value.get('maximum_new_full_lease_intents') != MAX_GUESTS or
            value.get('lease_seconds_each') != LEASE_SECONDS or
            value.get('lane_spending_cap_usd') is not None or
            value.get('dispatch_authorized') is not False or
            value.get('same_intent_replay_authorized') is not False or
            value.get('official_final_admissions') != 0 or value.get('official_model_results') != 0 or
            value.get('sample_delays_ms') != list(SAMPLE_DELAYS_MS) or
            value.get('max_probe_wall_ms') != MAX_PROBE_WALL_MS):
        raise ValueError("Source epoch or TRAIN-only six-guest protocol changed")
    plan, selected = train_sources(Path(value['train_plan']))
    if (selected != value['cases'] or plan['candidate_root'] != value['candidate_root'] or
            value['train_plan_sha256'] != digest(_private(Path(value['train_plan']))) or
            digest(Path(value['guest_public']).read_bytes()) != value['guest_public_sha256'] or
            digest(_private(Path(value['scoped_reference']))) != value['scoped_reference_sha256']):
        raise ValueError("Pinned TRAIN or runtime reference bytes changed")
    public = json.loads(Path(value['public_path']).read_bytes())
    if (public.get('schema') != PUBLIC_SCHEMA or public.get('private_freeze_sha256') != digest(raw) or
            public.get('source_sha256s') != value['source_sha256s'] or
            public.get('dispatch_authorized') is not False or public.get('new_guest_maximum') != MAX_GUESTS):
        raise ValueError("Public source freeze binding changed")
    if require_unused:
        ledger = lease_accounting([Path(p) for p in value['accounting_roots']], exclude=Path(value['output_root']))
        if (ledger != value['prior_full_lease_accounting'] or
                set(s['row']['package_sha256'] for s in selected) & set(ledger['used_package_sha256s'])):
            raise ValueError("Full-lease ledger or unused TRAIN source boundary changed")
    return value


def _append(path: Path, row: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encode(row)); stream.flush(); os.fsync(stream.fileno())


def probe_no_action(sandbox, *, root: Path, out: Path, filename: str,
                    document_id: str, clock=time.monotonic_ns, sleep=time.sleep) -> dict:
    """Capture only; no GUI action, repair, model call or successful settle credit."""
    start = clock()
    frames = []
    stop = 'bounded_probe_completed'
    for ordinal, delay in enumerate(SAMPLE_DELAYS_MS):
        if delay:
            sleep(delay / 1000)
        before = clock()
        first_id = sandbox.get_current_window_id()
        first_title = sandbox.get_window_title(first_id)
        frame = bytes(sandbox.screenshot())
        second_id = sandbox.get_current_window_id()
        second_title = sandbox.get_window_title(second_id)
        after = clock()
        ref = reserve_and_write(root, out / f'probe-{ordinal:02d}.png', frame)
        row = {"schema": 'cua-native-wdi-v066-near-negative-no-action-sample-v7',
               "ordinal": ordinal, "requested_delay_ms": delay, "captured_utc": _now(),
               "probe_start_monotonic_ns": start, "monotonic_before_ns": before,
               "monotonic_after_ns": after, "elapsed_ns": after - start, "frame": ref,
               "full_frame_sha256": digest(frame), "application_frame_sha256": application_frame_digest(frame),
               "window_id_before": first_id, "window_id_after": second_id,
               "window_title_before": first_title, "window_title_after": second_title,
               "window_id_before_sha256": digest(first_id.encode()), "window_id_after_sha256": digest(second_id.encode()),
               "window_title_before_sha256": digest(first_title.encode()), "window_title_after_sha256": digest(second_title.encode()),
               "document_window_stable": first_id == second_id == document_id and filename in first_title and filename in second_title}
        _append(out / 'samples.ndjson', row)
        frames.append(frame)
        if before < start or after < before or after - start > MAX_PROBE_WALL_MS * 1_000_000:
            stop = 'wall_bound_or_clock_stop'; break
        if not row['document_window_stable']:
            stop = 'window_boundary_stop'; break
        if len(frames) >= 3:
            hashes = [application_frame_digest(x) for x in frames]
            if (hashes[-1] == hashes[-3] != hashes[-2] and
                    not adapter._single_caret_column(frames[-3], frames[-2])):
                stop = 'material_oscillation_stop'; break
    return {"stop": stop, "raw_samples": len(frames),
            "sample_ledger_sha256": digest(_private(out / 'samples.ndjson')),
            "actor_actions_during_or_after_probe": 0}


def _execute_actions(sandbox, *, source: dict, oracle: dict, instruction: str,
                     root: Path, out: Path, receipt: dict, persist) -> None:
    recorder = RecordingDesktop(sandbox)
    previous = None
    actions = actions_for(source['case'], oracle)
    for step, minimal in enumerate(actions):
        for attempt in range(5):
            observation = adapter.observe(recorder, task_id=source['row']['task_id'],
                task_binding_sha256=source['row']['package_sha256'], instruction=instruction,
                step=step, previous_action_result=previous, max_actions=32)
            observed_ref = reserve_and_write(root, out / f'frame-{step:02d}-{attempt}.png', observation.screenshot_bytes)
            try:
                action = adapter.parse_current_action(json.dumps(minimal), observation, recorder)
                break
            except adapter.PhysicalFrameDrift:
                changed = reserve_and_write(root, out / f'drift-{step:02d}-{attempt}.png', recorder.last_screenshot)
                receipt['physical_frame_resamples'].append({'step': step, 'attempt': attempt, 'observation': observed_ref, 'changed': changed})
                persist(); time.sleep(1)
        else:
            raise ValueError("TRAIN action frame never stabilized")
        predispatch = reserve_and_write(root, out / f'predispatch-{step:02d}-{attempt}.png', recorder.last_screenshot)
        row = {'step': step, 'observation': observed_ref, 'predispatch': predispatch,
               'normalized_action': action, 'minimal_action': minimal,
               'status': 'validated_before_dispatch', 'dispatch_before_monotonic_ns': time.monotonic_ns()}
        receipt['actor_steps'].append(row); persist()
        row['dispatch_type'] = adapter.dispatch(sandbox, action)
        row['dispatch_after_monotonic_ns'] = time.monotonic_ns()
        row['status'] = 'applied'; persist()
        previous = {'status': 'applied', 'code': 'ok'}


def _setup(sandbox, *, value: dict, baseline: bytes, filename: str,
           root: Path, out: Path, receipt: dict, persist) -> str:
    guest = json.loads(Path(value['guest_public']).read_bytes())
    info = sandbox.get_info(request_timeout=12)
    if (info.template_id != guest['provider_template_id'] or
            info.envd_version != guest['provider_envd_version'] or
            info.cpu_count != guest['provider_shape']['vcpu'] or info.memory_mb != guest['provider_shape']['memory_mb']):
        raise ValueError("Provider Desktop shape/template changed")
    sandbox.files.write('/tmp/near-negative-content-probe.py', runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
    observed = sandbox.commands.run('sudo -n python3 /tmp/near-negative-content-probe.py', timeout=450, request_timeout=480)
    content = json.loads(observed.stdout) if observed.exit_code == 0 else {}
    if (content.get('content_tree_sha256') != guest['static_content_sha256'] or
            content.get('counts') != guest['static_content_counts'] or content.get('kernel') != guest['kernel_identity'] or
            content.get('excluded_paths') != guest['static_content_excluded_paths']):
        raise ValueError("Guest content attestation changed")
    receipt['guest_content_attested'] = True
    if sandbox.commands.run('test ! -e /home/user/.config/libreoffice/4/user').exit_code != 0:
        raise ValueError("Fresh guest LibreOffice profile already exists")
    receipt['fresh_profile_absent'] = True
    remote = '/home/user/' + filename
    sandbox.files.write(remote, baseline)
    if bytes(sandbox.files.read(remote, format='bytes')) != baseline:
        raise ValueError("Trusted TRAIN staging bytes changed")
    sandbox.open(remote)
    receipt['trusted_setup_ready'] = wait_for_document_ready(sandbox, filename)
    time.sleep(7); sandbox.press('esc'); time.sleep(1)
    profile_guard.attest(sandbox=sandbox, attempts_root=root, out=out,
                        app_kind='calc', reference_path=Path(value['scoped_reference']),
                        receipt=receipt, persist=persist)
    return remote


def _one(*, value: dict, source: dict, attempt: str, ordinal: int,
         freeze_sha: str, permit_sha: str, sandbox_factory) -> dict:
    root = Path(value['output_root']); out = root / f'{ordinal:02d}-{source["case"]}-{attempt}'
    if out.exists() or out.is_symlink() or ordinal >= MAX_GUESTS:
        raise ValueError("Consumed TRAIN intent cannot be replayed")
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before each intent")
    if storage_audit(root)['dispatch_storage_ready'] is not True:
        raise ValueError("Raw evidence storage blocked before intent")
    package_dir, baseline, oracle = admit._package(Path(value['candidate_root']), source['row'])
    out.mkdir(mode=0o700)
    intent = {'schema': INTENT_SCHEMA, 'status': 'recorded_before_provider_create',
              'created_utc': _now(), 'split': 'train', 'ordinal': ordinal, 'case': source['case'],
              'attempt': attempt, 'package_sha256': source['row']['package_sha256'],
              'input_sha256': digest(baseline), 'freeze_sha256': freeze_sha, 'permit_sha256': permit_sha,
              'lease_seconds': LEASE_SECONDS, 'same_intent_replay_authorized': False,
              'host_power_before_intent': host_power_snapshot(), 'official_final_admissions': 0}
    intent_sha = _write_new(out / 'intent.json', intent)
    receipt = {'schema': RECEIPT_SCHEMA, 'status': 'started', 'stage': 'pre_provider',
               'provider_kind': 'e2b_desktop', 'split': 'train', 'case': source['case'], 'attempt': attempt,
               'ordinal': ordinal, 'package_sha256': source['row']['package_sha256'], 'input_sha256': digest(baseline),
               'intent_sha256': intent_sha, 'lease_seconds': LEASE_SECONDS, 'actor_steps': [],
               'physical_frame_resamples': [], 'official_final_admissions': 0, 'official_model_results': 0,
               'actual_provider_billed_usd': None}
    path = out / 'receipt.json'; _write_new(path, receipt)
    def persist(): _persist(path, receipt)
    sandbox = None
    try:
        receipt['stage'] = 'create_desktop'; persist()
        # The intent is fsynced before this sole create. Exceptions do not retry.
        sandbox = sandbox_factory(template='desktop', resolution=(1280, 800), timeout=LEASE_SECONDS,
                                  allow_internet_access=False, metadata={'envloop_purpose': 'v066-train-near-negative-v7'})
        receipt['sandbox_id_sha256'] = digest(sandbox.sandbox_id.encode()); persist()
        remote = _setup(sandbox, value=value, baseline=baseline, filename=source['filename'],
                        root=root, out=out, receipt=receipt, persist=persist)
        document_id = sandbox.get_current_window_id()
        if source['filename'] not in sandbox.get_window_title(document_id):
            raise ValueError("TRAIN document window absent before actor")
        receipt['document_window_id'] = document_id
        if attempt == 'cold-reset':
            receipt['cold_observation'] = reserve_and_write(root, out / 'cold-neutral-open.png', bytes(sandbox.screenshot()))
            restored = bytes(sandbox.files.read(remote, format='bytes'))
            receipt['restored_artifact'] = reserve_and_write(root, out / 'restored-original.xlsx', restored)
            if restored != baseline: raise ValueError("Fresh reset source bytes changed")
            receipt['status'] = 'cold_reset_observed'
        else:
            _execute_actions(sandbox, source=source, oracle=oracle,
                             instruction=(package_dir / 'actor_task.txt').read_text(),
                             root=root, out=out, receipt=receipt, persist=persist)
            if source['case'] == 'wrong-target':
                saved = bytes(sandbox.files.read(remote, format='bytes'))
                receipt['saved_artifact'] = reserve_and_write(root, out / 'saved.xlsx', saved)
                from .v066_post_enter_near_negative_audit_v7 import wrong_target_score
                receipt['independent_saved_score'] = wrong_target_score(baseline, saved, oracle)
                receipt['status'] = 'wrong_target_saved_score_zero'
            else:
                # Evaluator stimulus is restricted to this TRAIN protocol. It
                # does not widen the model/final action contract.
                key = TRUSTED_STIMULI[source['case']]
                receipt['trusted_negative_stimulus'] = {
                    'key': key, 'actor_step_count_before': len(receipt['actor_steps']),
                    'before_frame': reserve_and_write(root, out / 'stimulus-before.png', bytes(sandbox.screenshot())),
                    'dispatch_before_monotonic_ns': time.monotonic_ns(), 'status': 'recorded_before_dispatch'}
                persist()
                sandbox.press(key)
                receipt['trusted_negative_stimulus']['dispatch_after_monotonic_ns'] = time.monotonic_ns()
                receipt['trusted_negative_stimulus']['status'] = 'applied'
                persist()
                receipt['probe'] = probe_no_action(sandbox, root=root, out=out,
                    filename=source['filename'], document_id=document_id)
                from .v066_post_enter_near_negative_audit_v7 import audit_samples
                receipt['probe_classification'] = audit_samples(root=root, out=out,
                    filename=source['filename'], document_id=document_id)
                if source['case'] == 'modal-stop' and receipt['probe_classification']['classification'] != 'real_modal_stop':
                    raise ValueError("Real Save As modal stop was not observed")
                if source['case'] == 'no-action-probe' and receipt['probe_classification']['classification'] not in (
                        'real_material_oscillation_stop', 'caret_only_probe_material_oscillation_inconclusive',
                        'no_material_oscillation_observed_inconclusive'):
                    raise ValueError("No-action probe reached an unexpected window or infrastructure boundary")
                receipt['status'] = 'modal_stop_observed' if source['case'] == 'modal-stop' else 'no_action_probe_audited'
    except Exception as exc:
        receipt['status'] = 'stopped_for_reconciliation'; receipt['error_type'] = type(exc).__name__
        receipt['error_private'] = str(exc)[:240]
    finally:
        if sandbox is not None:
            try:
                receipt['kill_returned'] = bool(sandbox.kill())
                receipt['is_running_after_kill'] = bool(sandbox.is_running(request_timeout=12))
            except Exception as exc: receipt['kill_error_type'] = type(exc).__name__
        if receipt.get('is_running_after_kill') is not False:
            receipt['status'] = 'cleanup_unverified'
        receipt['finished_utc'] = _now(); persist()
    return receipt


def run(*, freeze_path: Path, permit_path: Path, enable_paid_train_near_negative: bool = False) -> dict:
    if enable_paid_train_near_negative is not True:
        raise ValueError("Paid TRAIN near-negative entry is disabled")
    value = validate_source(freeze_path)
    from .v066_post_enter_near_negative_audit_v7 import checked_permit, audit
    checked_permit(freeze_path=freeze_path, permit_path=permit_path, value=value)
    root = Path(value['output_root'])
    if root.exists() or root.is_symlink(): raise ValueError("Consumed TRAIN run root cannot be replayed")
    if {k: importlib.metadata.version(k) for k in SDK_VERSIONS} != SDK_VERSIONS or not os.environ.get('E2B_API_KEY'):
        raise ValueError("Pinned SDK/credential unavailable")
    active, count = active_hashes()
    if active or count: raise ValueError("Provider not active-zero before root consumption")
    root.mkdir(mode=0o700)
    journal = {'schema': RUN_SCHEMA, 'status': 'started', 'created_utc': _now(),
               'freeze_sha256': digest(_private(freeze_path)), 'permit_sha256': digest(_private(permit_path)),
               'permit_path': str(permit_path),
               'source_sha256s': value['source_sha256s'], 'guest_count_maximum': MAX_GUESTS,
               'attempts': [], 'same_intent_replay_authorized': False, 'official_final_admissions': 0}
    _write_new(root / 'run-receipt.json', journal)
    try:
        from e2b_desktop import Sandbox
        for source in value['cases']:
            for attempt in ('case', 'cold-reset'):
                ordinal = len(journal['attempts'])
                receipt = _one(value=value, source=source, attempt=attempt, ordinal=ordinal,
                               freeze_sha=journal['freeze_sha256'], permit_sha=journal['permit_sha256'],
                               sandbox_factory=Sandbox.create)
                journal['attempts'].append({'ordinal': ordinal, 'case': source['case'], 'attempt': attempt,
                    'status': receipt['status'], 'receipt_sha256': digest(_private(root / f'{ordinal:02d}-{source["case"]}-{attempt}' / 'receipt.json'))})
                _persist(root / 'run-receipt.json', journal)
                if receipt['status'] not in ('cold_reset_observed', 'wrong_target_saved_score_zero', 'modal_stop_observed', 'no_action_probe_audited'):
                    raise ValueError("TRAIN guest failed; no further create or replay")
        result = audit(freeze_path=freeze_path, run_path=root / 'run-receipt.json')
        journal['status'] = result['status']; journal['audit'] = result
    except Exception as exc:
        journal['status'] = 'stopped_for_reconciliation'; journal['error_type'] = type(exc).__name__
    journal['finished_utc'] = _now(); _persist(root / 'run-receipt.json', journal)
    return {'status': journal['status'], 'run_sha256': digest(_private(root / 'run-receipt.json')),
            'full_lease_intents': len(list(root.glob('*/intent.json'))), 'official_final_admissions': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'validate', 'run'))
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--train-plan', type=Path); parser.add_argument('--work-root', type=Path)
    parser.add_argument('--accounting-root', type=Path, action='append')
    parser.add_argument('--output-root', type=Path); parser.add_argument('--guest-public', type=Path)
    parser.add_argument('--scoped-reference', type=Path); parser.add_argument('--public-out', type=Path)
    parser.add_argument('--permit', type=Path)
    parser.add_argument('--enable-paid-train-near-negative', action='store_true')
    args = parser.parse_args()
    if args.mode == 'prepare':
        required = (args.train_plan, args.work_root, args.accounting_root, args.output_root,
                    args.guest_public, args.scoped_reference, args.public_out)
        if not all(required): raise ValueError("Exact source-only preparation paths required")
        result = prepare(train_plan=args.train_plan, work_root=args.work_root, accounting_roots=args.accounting_root,
            output_root=args.output_root, guest_public=args.guest_public, scoped_reference=args.scoped_reference,
            freeze_path=args.freeze, public_path=args.public_out)
    elif args.mode == 'validate':
        value = validate_source(args.freeze)
        result = {'status': 'source_frozen_no_dispatch', 'private_freeze_sha256': digest(_private(args.freeze)),
                  'maximum_new_full_lease_intents': value['maximum_new_full_lease_intents'], 'official_final_admissions': 0}
    else:
        if args.permit is None: raise ValueError("Exact independently reviewed permit required")
        result = run(freeze_path=args.freeze, permit_path=args.permit,
                     enable_paid_train_near_negative=args.enable_paid_train_near_negative)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
