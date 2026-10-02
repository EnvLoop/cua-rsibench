"""PowerPoint-for-the-web train-only E2B worker for the shared teacher adapter.

The teacher sees current screenshots and moves through the original Office
GUI. An evaluator with a separate delegated owner identity double-downloads
the exact OneDrive item and applies the frozen WDI PPTX scorer. A second E2B
lease opens a distinct neutral copy after the actor lease has terminated.

This worker cannot run from a guessed URL or a local candidate pool. It needs
the real 24-intent campaign session, six-cell action ratification, a private
task/cloud/source binding, bounded paid leases, and freshly reviewed one-file
actor ACL evidence. No credential or cloud locator is emitted publicly.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from cursibench.scale_action_contract import ContractLimits, make_observation
from ppt_wdi_factory import verify as ppt_verify
from tools import office_web_e2b_login_bridge_v1 as bridge
from tools import office_web_e2b_train_runner_v1 as old_runner
from tools import office_web_e2b_v066_train_adapter as gui_v066
from tools.office_web_ppt_graph_readback_v1 import GraphOwnerReadback


CELL = 'powerpoint-web'
PROFILE = 'scale-action-profile-v0.6.6'
SCHEMA = 'cua-office-ppt-teacher-binding-v1'
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9!._:-]{4,180}\Z')


class OfficePptTeacherError(ValueError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise OfficePptTeacherError(code)


def _sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _private_bytes(path: Path, root: Path, label: str,
                   max_bytes: int = 50_000_000) -> bytes:
    original = Path(path)
    _require(not original.is_symlink(), label + '_private_file_required')
    target = original.resolve()
    _require(target.is_file() and target.is_relative_to(root.resolve()) and
             target.stat().st_mode & 0o077 == 0 and
             0 < target.stat().st_size <= max_bytes,
             label + '_private_file_required')
    return target.read_bytes()


def _private_json(path: Path, root: Path, label: str) -> tuple[dict, bytes]:
    raw = _private_bytes(path, root, label, max_bytes=2_000_000)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OfficePptTeacherError(label + '_invalid_json') from None
    _require(type(value) is dict, label + '_object_required')
    return value, raw


def _item(value: object, label: str) -> dict:
    _require(type(value) is dict and set(value) == {
        'owner_user_id', 'drive_id', 'item_id', 'file_name', 'edit_url'},
        label + '_item_shape_invalid')
    url = old_runner.validate_train_deck_url(value['edit_url'])
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    _require(all(type(value[key]) is str and _ID.fullmatch(value[key])
                 for key in ('owner_user_id', 'drive_id', 'item_id')) and
             type(value['file_name']) is str and
             re.fullmatch(r'EL-PPT-Train-[A-Za-z0-9._-]+\.pptx',
                          value['file_name']) is not None and
             query.get('file') == [value['file_name']],
             label + '_item_identity_invalid')
    return value


def _neutral(result: dict) -> bool:
    return (result.get('status') == 'scored' and result.get('score') == 0 and
            result.get('preservation_pass') is True and
            result.get('unexpected_parts') == [] and
            type(result.get('per_target')) is dict and
            result['per_target'] and
            all(row.get('changed') is False for row in
                result['per_target'].values()))


def _positive(result: dict) -> bool:
    return (result.get('status') == 'scored' and result.get('score') == 1 and
            result.get('target_correct') is True and
            result.get('preservation_pass') is True and
            result.get('unexpected_parts') == [] and
            type(result.get('per_target')) is dict and
            result['per_target'] and
            all(row.get('changed') is True and row.get('correct') is True
                for row in result['per_target'].values()))


class OfficeBridgeLeases:
    """Actual e2b-desktop 2.2.0 path; imported only after the paid gate."""

    def preflight(self) -> None:
        _require(bool(os.environ.get('E2B_API_KEY')),
                 'e2b_api_key_missing_before_lease_reservation')

    def create(self, out_dir: Path, lease_seconds: int) -> str:
        from e2b_desktop import Sandbox
        bridge.start(out_dir, lease_seconds,
                     bridge.EXPECTED_TEMPLATE_ID, Sandbox)
        session = json.loads((out_dir / 'session.private.json').read_bytes())
        return session['sandbox_id']

    def connect(self, sandbox_id: str):
        from e2b_desktop import Sandbox
        return Sandbox.connect(sandbox_id)

    def stop(self, session_path: Path) -> str:
        from e2b_desktop import Sandbox
        return bridge.stop(session_path, Sandbox)['status']


def wait_for_manual_scope(session_path: Path, _item: dict, _phase: str,
                          timeout_seconds: int) -> None:
    """The operator signs in and places mode-0600 ACL evidence, then resumes."""
    end = time.monotonic() + timeout_seconds
    directory = session_path.parent
    while time.monotonic() < end:
        if ((directory / 'run.private.json').is_file() and
                (directory / 'actor-scope.private.json').is_file()):
            return
        time.sleep(1)
    raise OfficePptTeacherError('manual_office_login_or_acl_evidence_missing')


def wait_for_revocation(episode_dir: Path, item: dict, phase: str,
                        timeout_seconds: int) -> None:
    """Operator signals a removed share; Graph verifies the actual state."""
    path = episode_dir / f'{phase}-revoked.private.json'
    end = time.monotonic() + timeout_seconds
    while time.monotonic() < end:
        if (path.is_file() and not path.is_symlink() and
                path.stat().st_mode & 0o077 == 0):
            try:
                value = json.loads(path.read_bytes())
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise OfficePptTeacherError('office_revocation_signal_invalid') from None
            _require(value == {
                'schema': 'cua-office-ppt-revocation-operator-signal-v1',
                'item_id_sha256': _sha(item['item_id']),
                'phase': phase,
            }, 'office_revocation_signal_invalid')
            return
        time.sleep(1)
    raise OfficePptTeacherError('office_actor_share_revocation_not_signaled')


class OfficePptTeacherWorker:
    cell_id = CELL
    action_profile = PROFILE
    original_software_gui = True
    original_surface = 'web'
    requires_e2b = True
    requires_fresh_e2b_reset = True

    def __init__(self, session, binding_path: Path, *,
                 lease_factory=None, graph_reader=None,
                 operator_wait: Callable | None = None,
                 operator_wait_revocation: Callable | None = None,
                 clock: Callable[[], float] = time.time):
        self.session = session
        self.binding_path = Path(binding_path)
        self.lease_factory = lease_factory or OfficeBridgeLeases()
        self.graph_reader = graph_reader or GraphOwnerReadback()
        self.operator_wait = operator_wait or wait_for_manual_scope
        self.operator_wait_revocation = (operator_wait_revocation or
                                         wait_for_revocation)
        self.clock = clock
        self.adapter_sha256 = _sha(Path(__file__).read_bytes())

    def _binding(self, task: dict) -> tuple[dict, Path, Path, dict]:
        study = self.session.study
        root = Path(study.repo_root).resolve() / 'work'
        from native_desktop_factory.v066_final_freeze import validate_ratification
        ratification_path = getattr(study, 'ratification_path', None)
        _require(ratification_path is not None and
                 Path(ratification_path).is_file() and
                 not Path(ratification_path).is_symlink() and
                 Path(ratification_path).stat().st_mode & 0o077 == 0,
                 'office_six_cell_ratification_missing')
        try:
            ratification, ratification_sha = validate_ratification(
                Path(ratification_path))
        except (ValueError, OSError, TypeError, KeyError):
            raise OfficePptTeacherError(
                'office_six_cell_ratification_invalid') from None
        _require(ratification_sha ==
                 getattr(study, 'ratification_sha256', None) and
                 ratification == getattr(study, 'ratification', None) and
                 ratification['cell_profiles'][CELL]['adapter_sha256'] ==
                 self.adapter_sha256,
                 'office_six_cell_ratification_not_bound_to_worker')
        binding, _ = _private_json(self.binding_path, root, 'office_binding')
        fields = {'schema', 'cell_id', 'task_id', 'package_sha256',
                  'task_path', 'task_file_sha256', 'normalized_baseline_path',
                  'normalized_baseline_sha256', 'actor_item', 'reset_item',
                  'owner_email_sha256', 'actor_email_sha256',
                  'ratification_sha256', 'runtime_sha256',
                  'verifier_sha256', 'verifier_module_sha256',
                  'adapter_sha256', 'lease_seconds', 'max_steps',
                  'wall_seconds', 'manual_wait_seconds',
                  'post_finish_wait_seconds', 'e2b_reserve_usd',
                  'graph_read_reserve_usd'}
        _require(set(binding) == fields and binding['schema'] == SCHEMA and
                 binding['cell_id'] == CELL and
                 type(task) is dict and
                 set(task) == {'task_id', 'package_sha256',
                               'visible_instruction'} and
                 binding['task_id'] == task['task_id'] and
                 binding['package_sha256'] == task['package_sha256'] and
                 all(type(binding[name]) is str and
                     _HEX64.fullmatch(binding[name])
                     for name in ('task_file_sha256',
                                  'normalized_baseline_sha256',
                                  'owner_email_sha256', 'actor_email_sha256',
                                  'ratification_sha256', 'runtime_sha256',
                                  'verifier_sha256', 'verifier_module_sha256',
                                  'adapter_sha256')),
                 'office_binding_not_frozen_train_task')
        _require(binding['ratification_sha256'] ==
                 study.ratification_sha256 and
                 binding['adapter_sha256'] == self.adapter_sha256 and
                 binding['verifier_module_sha256'] ==
                 _sha(Path(ppt_verify.__file__).read_bytes()),
                 'office_action_or_verifier_source_changed')
        cell = next(row for row in study.plan['cells'] if
                    row['cell_id'] == CELL)
        _require(binding['runtime_sha256'] ==
                 cell['matched_bindings']['runtime'] and
                 binding['verifier_sha256'] ==
                 cell['matched_bindings']['verifier'] and
                 binding['package_sha256'] in {
                     row['package_sha256'] for row in
                     self.session.views['train']},
                 'office_runtime_or_package_not_in_frozen_train_split')
        task_path = Path(binding['task_path'])
        baseline_path = Path(binding['normalized_baseline_path'])
        _require(task_path.name == 'task.private.json' and
                 task_path.parent.name == task['task_id'] and
                 ('packages', 'train') in tuple(zip(
                     task_path.parts, task_path.parts[1:])) and
                 not any(part.lower() in {'selection', 'final', 'official'}
                         for part in task_path.parts) and
                 baseline_path.suffix == '.pptx',
                 'office_train_source_path_invalid')
        task_raw = _private_bytes(task_path, root, 'office_task', 2_000_000)
        baseline_raw = _private_bytes(baseline_path, root, 'office_baseline')
        _require(_sha(task_raw) == binding['task_file_sha256'] and
                 _sha(baseline_raw) ==
                 binding['normalized_baseline_sha256'],
                 'office_train_source_bytes_changed')
        try:
            task_spec = json.loads(task_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OfficePptTeacherError('office_train_task_invalid_json') from None
        _require(type(task_spec) is dict and
                 task_spec.get('schema') == old_runner.TASK_SCHEMA and
                 task_spec.get('split') == 'train' and
                 task_spec.get('task_id') == task['task_id'] and
                 task_spec.get('actor_task') ==
                 task['visible_instruction'] and
                 task_spec.get('official_final_credit') == 0,
                 'office_train_task_instruction_changed')
        actor = _item(binding['actor_item'], 'actor')
        reset = _item(binding['reset_item'], 'reset')
        _require(actor['owner_user_id'] == reset['owner_user_id'] and
                 actor['drive_id'] == reset['drive_id'] and
                 actor['item_id'] != reset['item_id'] and
                 actor['file_name'] != reset['file_name'] and
                 actor['edit_url'] != reset['edit_url'],
                 'office_reset_copy_not_distinct')
        for key, upper in (('lease_seconds', 3600), ('max_steps',
                                                   old_runner.MAX_STEPS),
                           ('wall_seconds', 600),
                           ('manual_wait_seconds', 1800),
                           ('post_finish_wait_seconds', 30)):
            _require(type(binding[key]) is int and
                     0 <= binding[key] <= upper and
                     (key == 'post_finish_wait_seconds' or
                      binding[key] > 0),
                     'office_worker_bound_invalid')
        _require(binding['lease_seconds'] >= 300 and
                 binding['wall_seconds'] + 60 <=
                 binding['lease_seconds'] and
                 binding['manual_wait_seconds'] +
                 binding['wall_seconds'] + 60 <=
                 binding['lease_seconds'],
                 'office_lease_cannot_cover_manual_login_and_actor')
        for key in ('e2b_reserve_usd', 'graph_read_reserve_usd'):
            from decimal import Decimal
            try:
                amount = Decimal(binding[key])
            except Exception:
                raise OfficePptTeacherError('office_cost_reserve_invalid') from None
            _require(type(binding[key]) is str and
                     amount.is_finite() and amount > 0 and
                     -amount.as_tuple().exponent <= 9,
                     'office_cost_reserve_invalid')
        # The scorer validates the WDI source facts, slide count, chart and
        # every target against the evaluator-owned normalized baseline.
        ppt_verify.freeze(baseline_path, task_spec,
                          office_web_normalized=True)
        return binding, task_path, baseline_path, task_spec

    def _lease(self, *, phase: str, item: dict, binding: dict,
               episode_dir: Path, task_path: Path,
               dispatch_e2b: Callable):
        directory = episode_dir / f'{phase}-login'
        self.lease_factory.preflight()
        def create(_request: dict) -> dict:
            sandbox_id = self.lease_factory.create(
                directory, binding['lease_seconds'])
            return {'schema':
                    'cua-full-study-teacher-e2b-lease-result-v1',
                    'sandbox_id': sandbox_id,
                    'lease_seconds': binding['lease_seconds'],
                    'created': True}
        session_path = directory / 'session.private.json'
        try:
            paid = dispatch_e2b(
                lease_seconds=binding['lease_seconds'],
                reserve_usd=binding['e2b_reserve_usd'],
                provider=create, phase=phase)
            return self._admit_created_lease(
                paid=paid, phase=phase, item=item, binding=binding,
                directory=directory, episode_dir=episode_dir,
                task_path=task_path)
        except BaseException:
            # A paid lease may exist even when login/ACL admission fails.
            # Preserve its ledger attempt, but terminate the exact sandbox.
            if session_path.is_file() and not (
                    directory / 'stop.private.json').exists():
                try:
                    self.lease_factory.stop(session_path)
                except Exception:
                    pass
            raise

    def _admit_created_lease(self, *, paid: dict, phase: str,
                             item: dict, binding: dict, directory: Path,
                             episode_dir: Path, task_path: Path):
        session_path = directory / 'session.private.json'
        session, _ = _private_json(session_path,
                                   Path(self.session.study.repo_root) / 'work',
                                   phase + '_office_login')
        _require(session.get('sandbox_id') == paid['result']['sandbox_id'] and
                 session.get('observed_template_id') ==
                 bridge.EXPECTED_TEMPLATE_ID and
                 session.get('sdk_version') == '2.2.0',
                 'office_e2b_lease_or_template_changed')
        self.operator_wait(session_path, item, phase,
                           binding['manual_wait_seconds'])
        run_path = directory / 'run.private.json'
        admission = old_runner.admit(session_path, task_path, run_path,
                                     episode_dir / f'{phase}-admit-unused',
                                     now=int(self.clock()))
        _require(admission.sandbox_id == paid['result']['sandbox_id'] and
                 admission.deck_url == item['edit_url'] and
                 admission.task_id == binding['task_id'] and
                 admission.task_sha256 == binding['task_file_sha256'] and
                 admission.max_steps == binding['max_steps'] and
                 admission.wall_seconds == binding['wall_seconds'],
                 'office_actor_scope_or_task_binding_failed')
        scope, _ = _private_json(directory / 'actor-scope.private.json',
                                  Path(self.session.study.repo_root) / 'work',
                                  phase + '_one_file_scope')
        _require(scope.get('assigned_item_id') == item['item_id'] and
                 scope.get('owner_principal_sha256') ==
                 binding['owner_email_sha256'] and
                 scope.get('actor_principal_sha256') ==
                 binding['actor_email_sha256'] and
                 scope.get('actor_seed_sha256') ==
                 binding['normalized_baseline_sha256'],
                 'office_scope_not_exact_actor_or_reset_item')
        sandbox = self.lease_factory.connect(admission.sandbox_id)
        _require(sandbox.sandbox_id == admission.sandbox_id and
                 sandbox.get_info(request_timeout=12).template_id ==
                 bridge.EXPECTED_TEMPLATE_ID,
                 'office_connected_desktop_identity_changed')
        sandbox.launch('google-chrome', uri=admission.deck_url)
        expected_title = item['file_name'].removesuffix('.pptx')
        title = None
        for _ in range(6):
            window = sandbox.get_current_window_id()
            current = sandbox.get_window_title(window)
            if type(current) is str and expected_title in current:
                title = current
                break
            time.sleep(2)
        _require(title is not None,
                 'office_native_editor_window_not_ready')
        _write_new(episode_dir / f'{phase}-editor.private.json',
                   _canonical({
                       'schema': 'cua-office-ppt-native-editor-window-v1',
                       'phase': phase,
                       'file_name_sha256': _sha(item['file_name']),
                       'window_title_sha256': _sha(title),
                       'edit_url_sha256': _sha(item['edit_url']),
                       'sandbox_id_sha256': _sha(admission.sandbox_id),
                   }))
        return paid, session_path, admission, sandbox

    def _graph_capture(self, *, phase: str, item: dict,
                       binding: dict, episode_dir: Path) -> tuple[Path, dict]:
        self.graph_reader.preflight()
        location = episode_dir / 'artifacts' / f'{phase}-graph'
        location.mkdir(mode=0o700)
        attempt_id = ('graph-ppt-' + _sha(str(episode_dir.resolve()))[:16] +
                      '-' + phase)
        request = {
            'schema': 'cua-office-ppt-exact-owner-readback-v1',
            'phase': phase, 'cell_id': CELL,
            'task_package_sha256': binding['package_sha256'],
            'owner_user_id_sha256': _sha(item['owner_user_id']),
            'drive_id_sha256': _sha(item['drive_id']),
            'item_id_sha256': _sha(item['item_id']),
            'file_name_sha256': _sha(item['file_name']),
        }
        def read(_request: dict) -> dict:
            return self.graph_reader.capture(
                owner_user_id=item['owner_user_id'],
                drive_id=item['drive_id'], item_id=item['item_id'],
                expected_name=item['file_name'], out_dir=location)
        paid = self.session.dispatch_paid(
            attempt_id=attempt_id, category='storage_application',
            work=request, request=request,
            reserve_usd=binding['graph_read_reserve_usd'],
            resource_reservation={}, provider=read)
        receipt = paid['result']
        persisted_receipt, _ = _private_json(
            location / 'readback.private.json',
            Path(self.session.study.repo_root) / 'work',
            phase + '_graph_receipt')
        _require(type(receipt) is dict and
                 persisted_receipt == receipt and
                 receipt.get('schema') ==
                 'cua-office-ppt-owner-double-download-v1' and
                 receipt.get('item_id_sha256') == _sha(item['item_id']) and
                 receipt.get('first_sha256') ==
                 receipt.get('second_sha256'),
                 'office_owner_double_download_not_bound')
        first = location / 'first.private.pptx'
        second = location / 'second.private.pptx'
        first_raw = _private_bytes(first,
                                   Path(self.session.study.repo_root) / 'work',
                                   phase + '_download')
        second_raw = _private_bytes(second,
                                    Path(self.session.study.repo_root) / 'work',
                                    phase + '_download')
        _require(first_raw == second_raw and
                 _sha(first_raw) == receipt['first_sha256'],
                 'office_owner_download_bytes_changed')
        old_runner.readback_pptx(first_raw)
        return first, receipt

    def _graph_actor_revoked(self, *, phase: str, item: dict,
                             binding: dict, episode_dir: Path,
                             lease_session_path: Path) -> dict:
        self.graph_reader.preflight()
        scope, _ = _private_json(
            lease_session_path.parent / 'actor-scope.private.json',
            Path(self.session.study.repo_root) / 'work',
            phase + '_scope_for_revocation')
        snapshot, _ = _private_json(
            lease_session_path.parent / 'assigned-permissions.private.json',
            Path(self.session.study.repo_root) / 'work',
            phase + '_permission_for_revocation')
        permissions = snapshot.get('response', {}).get('value')
        _require(type(permissions) is list and len(permissions) == 1 and
                 type(permissions[0]) is dict and
                 type(permissions[0].get('id')) is str and
                 permissions[0]['id'] and
                 type(scope.get('actor_email')) is str and
                 _sha(scope['actor_email'].casefold()) ==
                 binding['actor_email_sha256'],
                 'office_prior_actor_permission_identity_missing')
        prior_id = permissions[0]['id']
        actor_email = scope['actor_email']
        attempt_id = ('graph-ppt-' + _sha(str(episode_dir.resolve()))[:16] +
                      '-' + phase + '-revoked')
        request = {
            'schema': 'cua-office-ppt-owner-permission-readback-v1',
            'phase': phase, 'cell_id': CELL,
            'task_package_sha256': binding['package_sha256'],
            'owner_user_id_sha256': _sha(item['owner_user_id']),
            'drive_id_sha256': _sha(item['drive_id']),
            'item_id_sha256': _sha(item['item_id']),
            'actor_email_sha256': _sha(actor_email.casefold()),
            'prior_permission_id_sha256': _sha(prior_id),
        }
        def read(_request: dict) -> dict:
            return self.graph_reader.verify_actor_revoked(
                owner_user_id=item['owner_user_id'],
                drive_id=item['drive_id'], item_id=item['item_id'],
                actor_email=actor_email,
                prior_permission_id=prior_id)
        paid = self.session.dispatch_paid(
            attempt_id=attempt_id, category='storage_application',
            work=request, request=request,
            reserve_usd=binding['graph_read_reserve_usd'],
            resource_reservation={}, provider=read)
        result = paid['result']
        _require(type(result) is dict and
                 result.get('schema') ==
                 'cua-office-ppt-owner-revocation-readback-v1' and
                 result.get('owner_user_id_sha256') ==
                 _sha(item['owner_user_id']) and
                 result.get('drive_id_sha256') ==
                 _sha(item['drive_id']) and
                 result.get('item_id_sha256') ==
                 _sha(item['item_id']) and
                 result.get('actor_email_sha256') ==
                 _sha(actor_email.casefold()) and
                 result.get('prior_permission_id_sha256') ==
                 _sha(prior_id) and
                 result.get('actor_grants_remaining') == 0 and
                 result.get('broad_links_remaining') == 0 and
                 all(type(result.get(name)) is int and result[name] >= 0
                     for name in ('remaining_permission_count',
                                  'owner_permission_count',
                                  'inherited_permission_count',
                                  'existing_access_link_count')),
                 'office_prior_actor_file_permission_not_revoked')
        return result

    def _actor_loop(self, *, sandbox, admission, task: dict,
                    out_dir: Path, sample_teacher: Callable,
                    max_steps: int) -> tuple[list[dict], str]:
        traces = []
        shas = []
        started = time.monotonic()
        memory = ''
        previous = None
        for step in range(max_steps):
            _require(time.monotonic() - started <= admission.wall_seconds and
                     int(self.clock()) < admission.lease_end_unix,
                     'office_actor_wall_or_lease_expired')
            frame = bytes(sandbox.screenshot())
            observation = make_observation(
                task_id=task['task_id'],
                task_binding_sha256=task['package_sha256'],
                instruction=task['visible_instruction'], step=step,
                screenshot_bytes=frame, memory=memory,
                previous_action_result=previous,
                limits=ContractLimits(max_step=max_steps,
                                      frame_ttl_seconds=150))
            _write_new(out_dir / 'frames' / f'step-{step:03d}.png', frame)
            def current_frame_id() -> str:
                latest = bytes(sandbox.screenshot())
                return (observation.frame_id if _sha(latest) ==
                        observation.screenshot['sha256'] else
                        'changed-current-frame')
            sampled = sample_teacher(observation, current_frame_id)
            _require(type(sampled) is dict and set(sampled) == {
                'action', 'trace_row', 'teacher_result_sha256'},
                'teacher_action_sample_unbound')
            action = sampled['action']
            shas.append(sampled['teacher_result_sha256'])
            traces.append(sampled['trace_row'])
            _require(current_frame_id() == observation.frame_id and
                     int(self.clock()) < admission.lease_end_unix,
                     'office_frame_changed_before_gui_dispatch')
            if action['type'] == 'finish':
                _write_new(out_dir / 'actions.private.json',
                           _canonical(traces))
                return traces, 'finished'
            gui_v066.dispatch_current_action(sandbox, action, observation)
            memory = action.get('memory', memory)
            previous = {'status': 'applied', 'code': 'ok'}
        raise OfficePptTeacherError('office_actor_action_limit_without_finish')

    def run_episode(self, *, task: dict, out_dir: Path,
                    sample_teacher: Callable,
                    dispatch_e2b: Callable) -> dict:
        _require(callable(sample_teacher) and callable(dispatch_e2b),
                 'teacher_callbacks_required')
        from cursibench.full_study_teacher_adapter_v1 import _frozen_session
        _frozen_session(self.session)
        out_dir = Path(out_dir)
        root = Path(self.session.study.repo_root).resolve() / 'work'
        _require(Path.cwd().resolve() ==
                 Path(self.session.study.repo_root).resolve(),
                 'office_worker_requires_repository_cwd')
        _require(out_dir.is_dir() and not out_dir.is_symlink() and
                 out_dir.resolve().is_relative_to(root.resolve()) and
                 (out_dir / 'frames').is_dir() and
                 not (out_dir / 'episode.private.json').exists(),
                 'office_episode_private_fresh_directory_required')
        binding, task_path, baseline_path, task_spec = self._binding(task)
        artifacts = out_dir / 'artifacts'
        artifacts.mkdir(mode=0o700)
        oracle = ppt_verify.freeze(baseline_path, task_spec,
                                   office_web_normalized=True)
        actor_item = binding['actor_item']
        reset_item = binding['reset_item']
        preflight_path, _ = self._graph_capture(
            phase='actor-preflight', item=actor_item,
            binding=binding, episode_dir=out_dir)
        _require(_neutral(ppt_verify.verify(baseline_path,
                                             preflight_path, oracle)),
                 'office_actor_cloud_item_not_neutral_baseline')
        actor_session = None
        reset_session = None
        actor_stopped = False
        reset_stopped = False
        actor_paid = reset_paid = None
        traces = []
        try:
            actor_paid, actor_session, actor_admission, actor_sandbox = self._lease(
                phase='actor', item=actor_item, binding=binding,
                episode_dir=out_dir, task_path=task_path,
                dispatch_e2b=dispatch_e2b)
            traces, _ = self._actor_loop(
                sandbox=actor_sandbox, admission=actor_admission,
                task=task, out_dir=out_dir,
                sample_teacher=sample_teacher,
                max_steps=binding['max_steps'])
            actor_stop = self.lease_factory.stop(actor_session)
            actor_stopped = actor_stop == 'killed'
            _require(actor_stopped, 'office_actor_sandbox_termination_unconfirmed')
            if binding['post_finish_wait_seconds']:
                time.sleep(binding['post_finish_wait_seconds'])
            saved_path, saved_download = self._graph_capture(
                phase='saved', item=actor_item,
                binding=binding, episode_dir=out_dir)
            saved_score = ppt_verify.verify(baseline_path, saved_path, oracle)
            _require(_positive(saved_score),
                     'office_teacher_saved_state_not_positive')
            saved_bytes = saved_path.read_bytes()
            _write_new(artifacts / 'saved.private.pptx', saved_bytes)
            saved_receipt = {
                'schema': 'cua-full-study-teacher-saved-state-v1',
                'cell_id': CELL, 'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'independent_of_actor': True,
                'native_save_observed': True,
                'target_state_pass': True,
                'no_regression_pass': True,
                'saved_artifact_sha256': _sha(saved_bytes),
                'saved_artifact_ref': {'path': 'artifacts/saved.private.pptx',
                                       'sha256': _sha(saved_bytes)},
                'verifier_sha256': binding['verifier_sha256'],
                'evaluator_result': 'pass',
                'owner_double_download_sha256': _sha(_canonical(saved_download)),
            }
            _write_new(out_dir / 'saved-state.private.json',
                       _canonical(saved_receipt))
            self.operator_wait_revocation(
                out_dir, actor_item, 'actor',
                binding['manual_wait_seconds'])
            actor_revoked = self._graph_actor_revoked(
                phase='actor', item=actor_item,
                binding=binding, episode_dir=out_dir,
                lease_session_path=actor_session)
            reset_paid, reset_session, reset_admission, reset_sandbox = self._lease(
                phase='reset', item=reset_item, binding=binding,
                episode_dir=out_dir, task_path=task_path,
                dispatch_e2b=dispatch_e2b)
            reset_frame = bytes(reset_sandbox.screenshot())
            _require(reset_frame.startswith(b'\x89PNG\r\n\x1a\n') and
                     len(reset_frame) > 100,
                     'office_fresh_reset_gui_not_observed')
            _write_new(artifacts / 'reset-open.private.png', reset_frame)
            reset_stop = self.lease_factory.stop(reset_session)
            reset_stopped = reset_stop == 'killed'
            _require(reset_stopped and
                     actor_paid['result']['sandbox_id'] !=
                     reset_paid['result']['sandbox_id'],
                     'office_reset_sandbox_not_fresh_or_terminated')
            reset_path, reset_download = self._graph_capture(
                phase='reset', item=reset_item,
                binding=binding, episode_dir=out_dir)
            reset_score = ppt_verify.verify(baseline_path, reset_path, oracle)
            _require(_neutral(reset_score),
                     'office_fresh_copy_reset_state_changed')
            self.operator_wait_revocation(
                out_dir, reset_item, 'reset',
                binding['manual_wait_seconds'])
            reset_revoked = self._graph_actor_revoked(
                phase='reset', item=reset_item,
                binding=binding, episode_dir=out_dir,
                lease_session_path=reset_session)
            baseline_state = {
                'schema': 'cua-office-ppt-neutral-semantic-state-v1',
                'baseline_sha256': _sha(baseline_path.read_bytes()),
                'task_package_sha256': task['package_sha256'],
                'target_state': ppt_verify.verify(
                    baseline_path, baseline_path, oracle)['per_target'],
                'preservation_pass': True,
                'unexpected_parts': [],
            }
            restored_state = {
                **baseline_state,
                'target_state': reset_score['per_target'],
                'preservation_pass': reset_score['preservation_pass'],
                'unexpected_parts': reset_score['unexpected_parts'],
            }
            _require(baseline_state == restored_state,
                     'office_reset_semantic_fingerprint_differs')
            baseline_raw = _canonical(baseline_state)
            restored_raw = _canonical(restored_state)
            _write_new(artifacts / 'baseline-state.private.json', baseline_raw)
            _write_new(artifacts / 'restored-state.private.json', restored_raw)
            reset_receipt = {
                'schema': 'cua-full-study-teacher-reset-v1',
                'cell_id': CELL, 'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'independent_of_actor': True,
                'fresh_environment': True,
                'state_equivalence_pass': True,
                'baseline_semantic_sha256': _sha(baseline_raw),
                'restored_semantic_sha256': _sha(restored_raw),
                'baseline_state_ref': {
                    'path': 'artifacts/baseline-state.private.json',
                    'sha256': _sha(baseline_raw)},
                'restored_state_ref': {
                    'path': 'artifacts/restored-state.private.json',
                    'sha256': _sha(restored_raw)},
                'sandbox_terminated': True,
                'reset_open_screenshot_sha256': _sha(reset_frame),
                'reset_double_download_sha256': _sha(_canonical(reset_download)),
                'actor_permission_revoked_sha256':
                    _sha(_canonical(actor_revoked)),
                'reset_permission_revoked_sha256':
                    _sha(_canonical(reset_revoked)),
            }
            _write_new(out_dir / 'reset.private.json',
                       _canonical(reset_receipt))
            frame_refs = []
            for index in range(len(traces)):
                frame = out_dir / 'frames' / f'step-{index:03d}.png'
                frame_refs.append({'path': f'frames/step-{index:03d}.png',
                                   'sha256': _sha(frame.read_bytes())})
            action_raw = (out_dir / 'actions.private.json').read_bytes()
            episode = {
                'schema': 'cua-full-study-teacher-gui-episode-v1',
                'status': 'admitted', 'split': 'train',
                'cell_id': CELL, 'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'action_profile': PROFILE,
                'teacher_model': 'gpt-5.6-sol',
                'original_software_gui': True,
                'original_surface': 'web',
                'runtime_sha256': binding['runtime_sha256'],
                'adapter_sha256': self.adapter_sha256,
                'frame_refs': frame_refs,
                'action_trace_ref': {'path': 'actions.private.json',
                                      'sha256': _sha(action_raw)},
                'saved_state_ref': {'path': 'saved-state.private.json',
                                    'sha256': _sha((out_dir /
                                                   'saved-state.private.json').read_bytes())},
                'reset_ref': {'path': 'reset.private.json',
                              'sha256': _sha((out_dir /
                                             'reset.private.json').read_bytes())},
                'teacher_result_sha256s': [row['teacher_result_sha256']
                                           for row in traces],
                'e2b_attempt_ids': [actor_paid['attempt_id'],
                                    reset_paid['attempt_id']],
            }
            episode_path = out_dir / 'episode.private.json'
            raw = _canonical(episode)
            _write_new(episode_path, raw)
            return {'episode_receipt_path': str(episode_path),
                    'episode_receipt_sha256': _sha(raw)}
        finally:
            for path, stopped in ((actor_session, actor_stopped),
                                  (reset_session, reset_stopped)):
                if path is not None and not stopped:
                    try:
                        self.lease_factory.stop(path)
                    except Exception:
                        pass


def prepare_private_binding(session, *, task: dict, task_path: Path,
                            normalized_baseline_path: Path,
                            actor_item: dict, reset_item: dict,
                            owner_email: str, actor_email: str,
                            out_path: Path, lease_seconds: int = 900,
                            max_steps: int = 20,
                            wall_seconds: int = 600,
                            manual_wait_seconds: int = 180,
                            post_finish_wait_seconds: int = 5,
                            e2b_reserve_usd: str = '1',
                            graph_read_reserve_usd: str = '0.01') -> dict:
    """Create one immutable private train binding; no provider or GUI call."""
    from cursibench.full_study_teacher_adapter_v1 import _frozen_session
    _frozen_session(session)
    root = Path(session.study.repo_root).resolve() / 'work'
    _require(Path.cwd().resolve() ==
             Path(session.study.repo_root).resolve(),
             'office_worker_requires_repository_cwd')
    target = Path(out_path).absolute()
    _require(not root.is_symlink() and not target.is_symlink() and
             target.parent.resolve().is_relative_to(root.resolve()) and
             not target.exists(),
             'office_binding_requires_new_private_work_path')
    _require(type(owner_email) is str and type(actor_email) is str and
             re.fullmatch(r'[^@\s]{1,128}@[^@\s]{1,255}', owner_email) and
             re.fullmatch(r'[^@\s]{1,128}@[^@\s]{1,255}', actor_email) and
             owner_email.casefold() != actor_email.casefold(),
             'office_owner_and_actor_must_be_distinct')
    task_bytes = _private_bytes(Path(task_path), root, 'office_task', 2_000_000)
    baseline_bytes = _private_bytes(
        Path(normalized_baseline_path), root, 'office_baseline')
    cell = next(row for row in session.study.plan['cells']
                if row['cell_id'] == CELL)
    binding = {
        'schema': SCHEMA, 'cell_id': CELL,
        'task_id': task['task_id'],
        'package_sha256': task['package_sha256'],
        'task_path': str(Path(task_path).resolve()),
        'task_file_sha256': _sha(task_bytes),
        'normalized_baseline_path': str(
            Path(normalized_baseline_path).resolve()),
        'normalized_baseline_sha256': _sha(baseline_bytes),
        'actor_item': actor_item, 'reset_item': reset_item,
        'owner_email_sha256': _sha(owner_email.casefold()),
        'actor_email_sha256': _sha(actor_email.casefold()),
        'ratification_sha256': session.study.ratification_sha256,
        'runtime_sha256': cell['matched_bindings']['runtime'],
        'verifier_sha256': cell['matched_bindings']['verifier'],
        'verifier_module_sha256': _sha(Path(ppt_verify.__file__).read_bytes()),
        'adapter_sha256': _sha(Path(__file__).read_bytes()),
        'lease_seconds': lease_seconds,
        'max_steps': max_steps,
        'wall_seconds': wall_seconds,
        'manual_wait_seconds': manual_wait_seconds,
        'post_finish_wait_seconds': post_finish_wait_seconds,
        'e2b_reserve_usd': e2b_reserve_usd,
        'graph_read_reserve_usd': graph_read_reserve_usd,
    }
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_new(target, _canonical(binding))
    worker = OfficePptTeacherWorker(session, target)
    worker._binding(task)
    return {'schema': 'cua-office-ppt-teacher-binding-prepared-v1',
            'binding_sha256': _sha(target.read_bytes()),
            'task_package_sha256': task['package_sha256'],
            'provider_calls': 0,
            'official_final_admitted': 0}
