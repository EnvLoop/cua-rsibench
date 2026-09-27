"""Original Excel-for-the-web SEC train teacher episode worker.

The actor receives screenshots and v0.6.6 GUI actions only. A separately
authenticated owner double-downloads exact cloud items. An independent SEC
oracle process scores formulas, numeric dependencies, and non-target state.
The worker refuses missing six-cell ratification, private train source, one-
file ACL, paid E2B lease, or fresh reset evidence before writing an admitted
episode receipt. No final task, gold workbook, or Graph token reaches a model.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from tools import excel_web_e2b_train_runner_v1 as excel_runner
from tools import excel_web_e2b_v066_train_adapter as excel_gui_v066
from tools import office_web_ppt_teacher_worker_v1 as ppt_worker
from tools.office_web_excel_graph_readback_v1 import ExcelGraphOwnerReadback


CELL = 'excel-web'
PROFILE = 'scale-action-profile-v0.6.6'
SCHEMA = 'cua-office-excel-teacher-binding-v1'
ROOT = Path(__file__).resolve().parents[1]
ORACLE_SCRIPT = ROOT / 'tools/sec_excel_web_train_oracle_v1.py'
VERIFIER_SCRIPT = ROOT / 'sec_excel_factory/verify_integrated_candidate.py'
OOXML_SCRIPT = ROOT / 'sec_excel_factory/verify_ooxml.py'
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9!._:-]{4,180}\Z')


class OfficeExcelTeacherError(ValueError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise OfficeExcelTeacherError(code)


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
                   maximum: int = 50_000_000) -> bytes:
    return ppt_worker._private_bytes(path, root, label, maximum)


def _private_json(path: Path, root: Path, label: str) -> tuple[dict, bytes]:
    return ppt_worker._private_json(path, root, label)


def _item(value: object, label: str) -> dict:
    _require(type(value) is dict and set(value) == {
        'owner_user_id', 'drive_id', 'item_id', 'file_name', 'edit_url'},
        label + '_excel_item_shape_invalid')
    url = excel_runner.validate_train_workbook_url(value['edit_url'])
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    _require(all(type(value[key]) is str and _ID.fullmatch(value[key])
                 for key in ('owner_user_id', 'drive_id', 'item_id')) and
             type(value['file_name']) is str and
             re.fullmatch(r'EL-Excel-Train-[A-Za-z0-9._-]{1,100}\.xlsx',
                          value['file_name']) is not None and
             query.get('file') == [value['file_name']],
             label + '_excel_item_identity_invalid')
    return value


def source_bundle_sha256s() -> dict[str, str]:
    files = {
        'excel_teacher_worker': Path(__file__),
        'office_gui_base': Path(ppt_worker.__file__),
        'excel_graph_readback': ROOT / 'tools/office_web_excel_graph_readback_v1.py',
        'ppt_graph_permission_dependency':
            ROOT / 'tools/office_web_ppt_graph_readback_v1.py',
        'excel_e2b_train_runner': Path(excel_runner.__file__),
        'excel_v066_gui_adapter': Path(excel_gui_v066.__file__),
        'sec_train_oracle': ORACLE_SCRIPT,
        'sec_integrated_verifier': VERIFIER_SCRIPT,
        'sec_ooxml_reader': OOXML_SCRIPT,
    }
    return {name: _sha(path.read_bytes()) for name, path in files.items()}


def adapter_bundle_sha256() -> str:
    return _sha(_canonical(source_bundle_sha256s()))


class SecOracleSubprocess:
    """Run the evaluator in a separate process, never inside the actor."""

    def _run(self, args: list[str], *, may_fail: bool = False) -> dict:
        completed = subprocess.run(
            [sys.executable, str(ORACLE_SCRIPT), *args],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
            check=False)
        _require(completed.returncode in ((0, 1) if may_fail else (0,)) and
                 len(completed.stdout.encode()) <= 1_000_000,
                 'sec_train_oracle_process_failed')
        try:
            result = json.loads(completed.stdout)
        except (UnicodeError, json.JSONDecodeError):
            raise OfficeExcelTeacherError('sec_train_oracle_output_invalid') from None
        _require(type(result) is dict,
                 'sec_train_oracle_output_invalid')
        return result

    def calibrate(self, seed: Path, reference: Path,
                  cases: Path, case_id: str) -> dict:
        return self._run(['--mode', 'calibrate', '--seed', str(seed),
                          '--reference', str(reference),
                          '--cases', str(cases), '--case-id', case_id])

    def score(self, candidate: Path, seed: Path,
              cases: Path, case_id: str) -> dict:
        return self._run(['--mode', 'score', '--seed', str(seed),
                          '--candidate', str(candidate),
                          '--cases', str(cases), '--case-id', case_id],
                         may_fail=True)

    def neutral(self, seed: Path, candidate: Path) -> dict:
        return self._run(['--mode', 'neutral', '--seed', str(seed),
                          '--candidate', str(candidate)], may_fail=True)


class OfficeExcelTeacherWorker(ppt_worker.OfficePptTeacherWorker):
    cell_id = CELL
    action_profile = PROFILE
    original_software_gui = True
    original_surface = 'web'
    requires_e2b = True
    requires_fresh_e2b_reset = True

    def __init__(self, session, binding_path: Path, *,
                 lease_factory=None, graph_reader=None,
                 oracle_runner=None, operator_wait: Callable | None = None,
                 operator_wait_revocation: Callable | None = None,
                 clock: Callable[[], float] = time.time):
        super().__init__(
            session, binding_path,
            lease_factory=lease_factory or ppt_worker.OfficeBridgeLeases(),
            graph_reader=graph_reader or ExcelGraphOwnerReadback(),
            operator_wait=operator_wait,
            operator_wait_revocation=operator_wait_revocation,
            clock=clock)
        self.oracle_runner = oracle_runner or SecOracleSubprocess()
        self.adapter_sha256 = adapter_bundle_sha256()

    def _binding(self, task: dict) -> tuple[dict, Path, Path, Path, Path]:
        from native_desktop_factory.v066_final_freeze import validate_ratification
        study = self.session.study
        root = Path(study.repo_root).resolve() / 'work'
        rat_path = getattr(study, 'ratification_path', None)
        _require(rat_path is not None and Path(rat_path).is_file() and
                 not Path(rat_path).is_symlink() and
                 Path(rat_path).stat().st_mode & 0o077 == 0,
                 'excel_six_cell_ratification_missing')
        try:
            ratification, rat_sha = validate_ratification(Path(rat_path))
        except (ValueError, OSError, TypeError, KeyError):
            raise OfficeExcelTeacherError(
                'excel_six_cell_ratification_invalid') from None
        _require(rat_sha == getattr(study, 'ratification_sha256', None) and
                 ratification == getattr(study, 'ratification', None) and
                 ratification['cell_profiles'][CELL]['adapter_sha256'] ==
                 self.adapter_sha256,
                 'excel_ratification_not_bound_to_worker')
        binding, _ = _private_json(self.binding_path, root, 'excel_binding')
        fields = {'schema', 'cell_id', 'task_id', 'package_sha256',
                  'task_path', 'task_file_sha256', 'actor_seed_sha256',
                  'cases_path', 'cases_sha256', 'case_id',
                  'reference_path', 'reference_sha256',
                  'actor_item', 'reset_item', 'owner_email_sha256',
                  'actor_email_sha256', 'ratification_sha256',
                  'runtime_sha256', 'verifier_sha256',
                  'adapter_sha256', 'adapter_source_sha256s',
                  'lease_seconds', 'max_steps', 'wall_seconds',
                  'manual_wait_seconds', 'post_finish_wait_seconds',
                  'e2b_reserve_usd', 'graph_read_reserve_usd'}
        _require(set(binding) == fields and binding['schema'] == SCHEMA and
                 binding['cell_id'] == CELL and type(task) is dict and
                 set(task) == {'task_id', 'package_sha256',
                               'visible_instruction'} and
                 binding['task_id'] == task['task_id'] and
                 binding['package_sha256'] == task['package_sha256'] and
                 all(type(binding[name]) is str and
                     _HEX64.fullmatch(binding[name])
                     for name in ('task_file_sha256', 'actor_seed_sha256',
                                  'cases_sha256', 'reference_sha256',
                                  'owner_email_sha256', 'actor_email_sha256',
                                  'ratification_sha256', 'runtime_sha256',
                                  'verifier_sha256', 'adapter_sha256')),
                 'excel_binding_not_frozen_train_task')
        _require(binding['ratification_sha256'] ==
                 study.ratification_sha256 and
                 binding['adapter_sha256'] == self.adapter_sha256 and
                 binding['adapter_source_sha256s'] ==
                 source_bundle_sha256s(),
                 'excel_action_or_verifier_source_changed')
        cell = next(row for row in study.plan['cells'] if
                    row['cell_id'] == CELL)
        _require(binding['runtime_sha256'] ==
                 cell['matched_bindings']['runtime'] and
                 binding['verifier_sha256'] ==
                 cell['matched_bindings']['verifier'] and
                 binding['package_sha256'] in {
                     row['package_sha256'] for row in
                     self.session.views['train']},
                 'excel_runtime_or_package_not_in_frozen_train_split')
        task_path = Path(binding['task_path'])
        seed_path = task_path.parent / 'actor.xlsx'
        cases_path = Path(binding['cases_path'])
        reference_path = Path(binding['reference_path'])
        _require(task_path.name == 'task.private.json' and
                 task_path.parent.name == task['task_id'] and
                 ('packages', 'train') in tuple(zip(
                     task_path.parts, task_path.parts[1:])) and
                 not any(part.lower() in {'selection', 'final', 'official'}
                         for part in task_path.parts) and
                 reference_path.suffix == '.xlsx',
                 'excel_train_source_path_invalid')
        task_raw = _private_bytes(task_path, root, 'excel_task', 2_000_000)
        seed_raw = _private_bytes(seed_path, root, 'excel_seed')
        cases_raw = _private_bytes(cases_path, root, 'excel_cases', 8_000_000)
        reference_raw = _private_bytes(reference_path, root, 'excel_reference')
        _require(_sha(task_raw) == binding['task_file_sha256'] and
                 _sha(seed_raw) == binding['actor_seed_sha256'] and
                 _sha(cases_raw) == binding['cases_sha256'] and
                 _sha(reference_raw) == binding['reference_sha256'],
                 'excel_train_source_bytes_changed')
        original = excel_runner.validate_train_package(task_path)
        _require(original.task_id == task['task_id'] and
                 original.instruction == task['visible_instruction'] and
                 original.task_sha256 == binding['task_file_sha256'] and
                 original.actor_sha256 == binding['actor_seed_sha256'],
                 'excel_actor_source_does_not_match_train_instruction')
        try:
            cases = json.loads(cases_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OfficeExcelTeacherError('excel_train_case_invalid_json') from None
        _require(type(cases) is list and len(cases) == 1 and
                 type(cases[0]) is dict and
                 cases[0].get('split') == 'train_candidate' and
                 cases[0].get('case_id') == binding['case_id'] and
                 type(cases[0].get('source_package')) is dict and
                 cases[0]['source_package'].get('schema') ==
                 'sec-integrated-source-package-v1',
                 'excel_case_not_single_sec_train_candidate')
        actor = _item(binding['actor_item'], 'actor')
        reset = _item(binding['reset_item'], 'reset')
        _require(actor['owner_user_id'] == reset['owner_user_id'] and
                 actor['drive_id'] == reset['drive_id'] and
                 actor['item_id'] != reset['item_id'] and
                 actor['file_name'] != reset['file_name'] and
                 actor['edit_url'] != reset['edit_url'],
                 'excel_reset_copy_not_distinct')
        for key, upper in (('lease_seconds', 3600),
                           ('max_steps', excel_runner.MAX_STEPS),
                           ('wall_seconds', excel_runner.MAX_WALL_SECONDS),
                           ('manual_wait_seconds', 1800),
                           ('post_finish_wait_seconds', 30)):
            _require(type(binding[key]) is int and
                     0 <= binding[key] <= upper and
                     (key == 'post_finish_wait_seconds' or
                      binding[key] > 0),
                     'excel_worker_bound_invalid')
        _require(binding['lease_seconds'] >= 300 and
                 binding['wall_seconds'] + 60 <=
                 binding['lease_seconds'] and
                 binding['manual_wait_seconds'] +
                 binding['wall_seconds'] + 60 <=
                 binding['lease_seconds'],
                 'excel_lease_cannot_cover_manual_login_and_actor')
        from decimal import Decimal
        for key in ('e2b_reserve_usd', 'graph_read_reserve_usd'):
            try:
                amount = Decimal(binding[key])
            except Exception:
                raise OfficeExcelTeacherError('excel_cost_reserve_invalid') from None
            _require(type(binding[key]) is str and amount.is_finite() and
                     amount > 0 and -amount.as_tuple().exponent <= 9,
                     'excel_cost_reserve_invalid')
        calibration = self.oracle_runner.calibrate(
            seed_path, reference_path, cases_path, binding['case_id'])
        _require(type(calibration) is dict and
                 calibration.get('schema') ==
                 'cua-sec-integrated-train-oracle-calibration-v1' and
                 calibration.get('unsolved_seed_rejected') is True and
                 calibration.get('positive_reference_passed') is True and
                 type(calibration.get('checked_formula_targets')) is int and
                 calibration['checked_formula_targets'] >= 20 and
                 calibration.get('source_counterfactual_profiles') == 2 and
                 calibration.get('seed_sha256') == _sha(seed_raw) and
                 calibration.get('reference_sha256') ==
                 _sha(reference_raw),
                 'excel_sec_oracle_calibration_not_bound')
        return binding, task_path, seed_path, cases_path, reference_path

    def _admit_created_lease(self, *, paid: dict, phase: str,
                             item: dict, binding: dict, directory: Path,
                             episode_dir: Path, task_path: Path):
        session_path = directory / 'session.private.json'
        session, _ = _private_json(
            session_path, Path(self.session.study.repo_root) / 'work',
            phase + '_excel_login')
        _require(session.get('sandbox_id') == paid['result']['sandbox_id'] and
                 session.get('observed_template_id') ==
                 ppt_worker.bridge.EXPECTED_TEMPLATE_ID and
                 session.get('sdk_version') == '2.2.0',
                 'excel_e2b_lease_or_template_changed')
        self.operator_wait(session_path, item, phase,
                           binding['manual_wait_seconds'])
        run_path = directory / 'run.private.json'
        admission = excel_runner.admit(
            session_path, task_path, run_path,
            episode_dir / f'{phase}-admit-unused',
            now=int(self.clock()))
        _require(admission.sandbox_id == paid['result']['sandbox_id'] and
                 admission.workbook_url == item['edit_url'] and
                 admission.task_id == binding['task_id'] and
                 admission.task_sha256 == binding['task_file_sha256'] and
                 admission.actor_sha256 == binding['actor_seed_sha256'] and
                 admission.max_steps == binding['max_steps'] and
                 admission.wall_seconds == binding['wall_seconds'],
                 'excel_actor_scope_or_source_binding_failed')
        scope, _ = _private_json(
            directory / 'actor-scope.private.json',
            Path(self.session.study.repo_root) / 'work',
            phase + '_excel_one_file_scope')
        _require(scope.get('assigned_item_id') == item['item_id'] and
                 scope.get('owner_principal_sha256') ==
                 binding['owner_email_sha256'] and
                 scope.get('actor_principal_sha256') ==
                 binding['actor_email_sha256'] and
                 scope.get('actor_seed_sha256') ==
                 binding['actor_seed_sha256'],
                 'excel_scope_not_exact_actor_or_reset_item')
        sandbox = self.lease_factory.connect(admission.sandbox_id)
        _require(sandbox.sandbox_id == admission.sandbox_id and
                 sandbox.get_info(request_timeout=12).template_id ==
                 ppt_worker.bridge.EXPECTED_TEMPLATE_ID,
                 'excel_connected_desktop_identity_changed')
        sandbox.launch('google-chrome', uri=admission.workbook_url)
        expected_title = item['file_name'].removesuffix('.xlsx')
        title = None
        for _ in range(6):
            window = sandbox.get_current_window_id()
            current = sandbox.get_window_title(window)
            if type(current) is str and expected_title in current:
                title = current
                break
            time.sleep(2)
        _require(title is not None,
                 'excel_native_editor_window_not_ready')
        _write_new(episode_dir / f'{phase}-editor.private.json',
                   _canonical({
                       'schema': 'cua-office-excel-native-editor-window-v1',
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
        attempt_id = ('graph-excel-' +
                      _sha(str(episode_dir.resolve()))[:16] + '-' + phase)
        request = {
            'schema': 'cua-office-excel-exact-owner-readback-v1',
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
        persisted, _ = _private_json(
            location / 'readback.private.json',
            Path(self.session.study.repo_root) / 'work',
            phase + '_excel_graph_receipt')
        _require(type(receipt) is dict and persisted == receipt and
                 receipt.get('schema') ==
                 'cua-office-excel-owner-double-download-v1' and
                 receipt.get('item_id_sha256') == _sha(item['item_id']) and
                 receipt.get('first_sha256') ==
                 receipt.get('second_sha256'),
                 'excel_owner_double_download_not_bound')
        first = location / 'first.private.xlsx'
        second = location / 'second.private.xlsx'
        root = Path(self.session.study.repo_root) / 'work'
        first_raw = _private_bytes(first, root, phase + '_excel_download')
        second_raw = _private_bytes(second, root, phase + '_excel_download')
        _require(first_raw == second_raw and
                 _sha(first_raw) == receipt['first_sha256'],
                 'excel_owner_download_bytes_changed')
        excel_runner.readback_xlsx(first_raw)
        return first, receipt

    def _graph_actor_revoked(self, *, phase: str, item: dict,
                             binding: dict, episode_dir: Path,
                             lease_session_path: Path) -> dict:
        self.graph_reader.preflight()
        root = Path(self.session.study.repo_root) / 'work'
        scope, _ = _private_json(
            lease_session_path.parent / 'actor-scope.private.json',
            root, phase + '_excel_scope_for_revocation')
        snapshot, _ = _private_json(
            lease_session_path.parent / 'assigned-permissions.private.json',
            root, phase + '_excel_permission_for_revocation')
        permissions = snapshot.get('response', {}).get('value')
        _require(type(permissions) is list and len(permissions) == 1 and
                 type(permissions[0]) is dict and
                 type(permissions[0].get('id')) is str and
                 permissions[0]['id'] and
                 type(scope.get('actor_email')) is str and
                 _sha(scope['actor_email'].casefold()) ==
                 binding['actor_email_sha256'],
                 'excel_prior_actor_permission_identity_missing')
        prior_id = permissions[0]['id']
        actor_email = scope['actor_email']
        attempt_id = ('graph-excel-' +
                      _sha(str(episode_dir.resolve()))[:16] +
                      '-' + phase + '-revoked')
        request = {
            'schema': 'cua-office-excel-owner-permission-readback-v1',
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
                 'cua-office-excel-owner-revocation-readback-v1' and
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
                 'excel_prior_actor_file_permission_not_revoked')
        return result

    def _actor_loop(self, *, sandbox, admission, task: dict,
                    out_dir: Path, sample_teacher: Callable,
                    max_steps: int) -> tuple[list[dict], str]:
        traces, status = super()._actor_loop(
            sandbox=sandbox, admission=admission, task=task,
            out_dir=out_dir, sample_teacher=sample_teacher,
            max_steps=max_steps)
        _require(status == 'finished' and len(traces) >= 2,
                 'excel_teacher_no_gui_edit_before_finish')
        return traces, status

    @staticmethod
    def _neutral(result: object, seed_sha: str) -> bool:
        return (type(result) is dict and
                result.get('schema') ==
                'cua-sec-integrated-train-neutral-v1' and
                result.get('equivalent') is True and
                result.get('structure_pass') is True and
                result.get('changed_cell_count') == 0 and
                type(result.get('cell_count')) is int and
                result['cell_count'] > 0 and
                result.get('source_sha256') == seed_sha)

    @staticmethod
    def _positive(result: object, seed_sha: str) -> bool:
        return (type(result) is dict and
                result.get('schema') ==
                'cua-sec-integrated-train-saved-score-v1' and
                result.get('artifact_pass') is True and
                type(result.get('checked_formula_targets')) is int and
                result['checked_formula_targets'] >= 20 and
                result.get('source_counterfactual_profiles') == 2 and
                result.get('error_count') == 0 and
                result.get('seed_sha256') == seed_sha and
                result.get('native_recalculation_verified') is False)

    def run_episode(self, *, task: dict, out_dir: Path,
                    sample_teacher: Callable,
                    dispatch_e2b: Callable) -> dict:
        _require(callable(sample_teacher) and callable(dispatch_e2b),
                 'excel_teacher_callbacks_required')
        from cursibench.full_study_teacher_adapter_v1 import _frozen_session
        _frozen_session(self.session)
        out_dir = Path(out_dir)
        root = Path(self.session.study.repo_root).resolve() / 'work'
        _require(Path.cwd().resolve() ==
                 Path(self.session.study.repo_root).resolve(),
                 'excel_worker_requires_repository_cwd')
        _require(out_dir.is_dir() and not out_dir.is_symlink() and
                 out_dir.resolve().is_relative_to(root.resolve()) and
                 (out_dir / 'frames').is_dir() and
                 not (out_dir / 'episode.private.json').exists(),
                 'excel_episode_private_fresh_directory_required')
        binding, task_path, seed_path, cases_path, _reference_path = \
            self._binding(task)
        artifacts = out_dir / 'artifacts'
        artifacts.mkdir(mode=0o700)
        seed_sha = binding['actor_seed_sha256']
        actor_item = binding['actor_item']
        reset_item = binding['reset_item']
        preflight_path, _ = self._graph_capture(
            phase='actor-preflight', item=actor_item,
            binding=binding, episode_dir=out_dir)
        preflight = self.oracle_runner.neutral(seed_path, preflight_path)
        _require(self._neutral(preflight, seed_sha),
                 'excel_actor_cloud_item_not_neutral_seed')
        actor_session = reset_session = None
        actor_stopped = reset_stopped = False
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
            actor_stopped = self.lease_factory.stop(actor_session) == 'killed'
            _require(actor_stopped,
                     'excel_actor_sandbox_termination_unconfirmed')
            if binding['post_finish_wait_seconds']:
                time.sleep(binding['post_finish_wait_seconds'])
            saved_path, saved_download = self._graph_capture(
                phase='saved', item=actor_item,
                binding=binding, episode_dir=out_dir)
            saved_score = self.oracle_runner.score(
                saved_path, seed_path, cases_path, binding['case_id'])
            _require(self._positive(saved_score, seed_sha) and
                     saved_score.get('candidate_sha256') ==
                     _sha(saved_path.read_bytes()),
                     'excel_teacher_saved_formula_or_numeric_state_failed')
            saved_bytes = saved_path.read_bytes()
            _write_new(artifacts / 'saved.private.xlsx', saved_bytes)
            saved_receipt = {
                'schema': 'cua-full-study-teacher-saved-state-v1',
                'cell_id': CELL, 'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'independent_of_actor': True,
                'native_save_observed': True,
                'target_state_pass': True,
                'no_regression_pass': True,
                'saved_artifact_sha256': _sha(saved_bytes),
                'saved_artifact_ref': {
                    'path': 'artifacts/saved.private.xlsx',
                    'sha256': _sha(saved_bytes)},
                'verifier_sha256': binding['verifier_sha256'],
                'evaluator_result': 'pass',
                'owner_double_download_sha256':
                    _sha(_canonical(saved_download)),
                'sec_formula_target_count':
                    saved_score['checked_formula_targets'],
                'sec_counterfactual_profiles': 2,
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
                     'excel_fresh_reset_gui_not_observed')
            _write_new(artifacts / 'reset-open.private.png', reset_frame)
            reset_stopped = self.lease_factory.stop(reset_session) == 'killed'
            _require(reset_stopped and
                     actor_paid['result']['sandbox_id'] !=
                     reset_paid['result']['sandbox_id'],
                     'excel_reset_sandbox_not_fresh_or_terminated')
            reset_path, reset_download = self._graph_capture(
                phase='reset', item=reset_item,
                binding=binding, episode_dir=out_dir)
            reset_score = self.oracle_runner.neutral(seed_path, reset_path)
            _require(self._neutral(reset_score, seed_sha),
                     'excel_fresh_copy_reset_state_changed')
            self.operator_wait_revocation(
                out_dir, reset_item, 'reset',
                binding['manual_wait_seconds'])
            reset_revoked = self._graph_actor_revoked(
                phase='reset', item=reset_item,
                binding=binding, episode_dir=out_dir,
                lease_session_path=reset_session)
            baseline_score = self.oracle_runner.neutral(seed_path, seed_path)
            _require(self._neutral(baseline_score, seed_sha) and
                     baseline_score['cell_count'] == reset_score['cell_count'],
                     'excel_reset_baseline_semantic_scope_changed')
            baseline_state = {
                'schema': 'cua-office-excel-neutral-semantic-state-v1',
                'actor_seed_sha256': seed_sha,
                'task_package_sha256': task['package_sha256'],
                'sheet_structure_pass': True,
                'cell_count': baseline_score['cell_count'],
                'changed_cell_count': 0,
            }
            restored_state = {**baseline_state,
                              'cell_count': reset_score['cell_count'],
                              'changed_cell_count':
                                  reset_score['changed_cell_count']}
            _require(baseline_state == restored_state,
                     'excel_reset_semantic_fingerprint_differs')
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
                'reset_double_download_sha256':
                    _sha(_canonical(reset_download)),
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
                'action_trace_ref': {
                    'path': 'actions.private.json',
                    'sha256': _sha(action_raw)},
                'saved_state_ref': {
                    'path': 'saved-state.private.json',
                    'sha256': _sha((out_dir /
                                   'saved-state.private.json').read_bytes())},
                'reset_ref': {
                    'path': 'reset.private.json',
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
                            cases_path: Path, case_id: str,
                            reference_path: Path,
                            actor_item: dict, reset_item: dict,
                            owner_email: str, actor_email: str,
                            out_path: Path, lease_seconds: int = 900,
                            max_steps: int = 20,
                            wall_seconds: int = 600,
                            manual_wait_seconds: int = 180,
                            post_finish_wait_seconds: int = 5,
                            e2b_reserve_usd: str = '1',
                            graph_read_reserve_usd: str = '0.01',
                            oracle_runner=None) -> dict:
    """Hash-bind one private SEC train source; no provider or GUI call."""
    from cursibench.full_study_teacher_adapter_v1 import _frozen_session
    _frozen_session(session)
    root = Path(session.study.repo_root).resolve() / 'work'
    _require(Path.cwd().resolve() ==
             Path(session.study.repo_root).resolve(),
             'excel_worker_requires_repository_cwd')
    target = Path(out_path).absolute()
    _require(not root.is_symlink() and not target.is_symlink() and
             target.parent.resolve().is_relative_to(root.resolve()) and
             not target.exists(),
             'excel_binding_requires_new_private_work_path')
    _require(type(owner_email) is str and type(actor_email) is str and
             re.fullmatch(r'[^@\s]{1,128}@[^@\s]{1,255}', owner_email) and
             re.fullmatch(r'[^@\s]{1,128}@[^@\s]{1,255}', actor_email) and
             owner_email.casefold() != actor_email.casefold(),
             'excel_owner_and_actor_must_be_distinct')
    task_raw = _private_bytes(Path(task_path), root,
                              'excel_task', 2_000_000)
    seed_path = Path(task_path).parent / 'actor.xlsx'
    seed_raw = _private_bytes(seed_path, root, 'excel_seed')
    cases_raw = _private_bytes(Path(cases_path), root,
                               'excel_cases', 8_000_000)
    reference_raw = _private_bytes(Path(reference_path), root,
                                   'excel_reference')
    cell = next(row for row in session.study.plan['cells']
                if row['cell_id'] == CELL)
    binding = {
        'schema': SCHEMA, 'cell_id': CELL,
        'task_id': task['task_id'],
        'package_sha256': task['package_sha256'],
        'task_path': str(Path(task_path).resolve()),
        'task_file_sha256': _sha(task_raw),
        'actor_seed_sha256': _sha(seed_raw),
        'cases_path': str(Path(cases_path).resolve()),
        'cases_sha256': _sha(cases_raw),
        'case_id': case_id,
        'reference_path': str(Path(reference_path).resolve()),
        'reference_sha256': _sha(reference_raw),
        'actor_item': actor_item, 'reset_item': reset_item,
        'owner_email_sha256': _sha(owner_email.casefold()),
        'actor_email_sha256': _sha(actor_email.casefold()),
        'ratification_sha256': session.study.ratification_sha256,
        'runtime_sha256': cell['matched_bindings']['runtime'],
        'verifier_sha256': cell['matched_bindings']['verifier'],
        'adapter_sha256': adapter_bundle_sha256(),
        'adapter_source_sha256s': source_bundle_sha256s(),
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
    worker = OfficeExcelTeacherWorker(
        session, target, oracle_runner=oracle_runner)
    worker._binding(task)
    return {'schema': 'cua-office-excel-teacher-binding-prepared-v1',
            'binding_sha256': _sha(target.read_bytes()),
            'task_package_sha256': task['package_sha256'],
            'provider_calls': 0,
            'official_final_admitted': 0}
