"""Twenty-task original Excel-web Qwen v0.6.6 selection executor.

Only the exact CampaignSession selection-start view and checkpoint path enter.
The student samples once per current screenshot through a distinct paid Tinker
attempt; E2B actor/reset leases are task-bound paid environment attempts.
Independent owner `.xlsx` downloads and SEC formula/numeric/no-regression
scoring produce a 20-row receipt for `record_selection_scored`. The current
real Office account/Graph selection lease is not yet qualified, so live use
fails before provider dispatch. Fake providers exercise the full contract.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
import fcntl
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

from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import scale_action_output_v066 as output_v066
from cursibench.scale_action_contract import Observation
from cursibench.scale_action_contract_v066 import ACTION_PROFILE_VERSION
from cursibench.scale_vision_proxy import MODEL, QwenVisionRenderer, digest as vision_digest
from tools import office_web_excel_selection_boundary_v1 as boundary
from tools import office_web_excel_selection_graph_v1 as graph_module
from tools import office_web_excel_teacher_worker_v1 as train_worker
from tools import office_web_ppt_teacher_worker_v1 as ppt_worker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'cua-office-excel-v066-selection-worker-v1'
TASK_SCHEMA = 'cua-office-excel-v066-selection-task-receipt-v1'
BATCH_SCHEMA = 'cua-office-excel-v066-selection-batch-v1'
BINDING_SCHEMA = 'cua-office-excel-v066-selection-binding-v1'
TASK_LEDGER_SCHEMA = 'cua-office-excel-v066-selection-task-ledger-v1'
MAX_TASKS = 20
MAX_ACTIONS = 90
MAX_INPUT_TOKENS = 32_768
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_TASK_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
SOURCE_FILES = (
    'tools/office_web_excel_selection_worker_v1.py',
    'tools/office_web_excel_selection_boundary_v1.py',
    'tools/office_web_excel_selection_graph_v1.py',
    'tools/sec_excel_web_selection_oracle_v1.py',
    'tools/sec_excel_web_train_oracle_v1.py',
    'sec_excel_factory/verify_integrated_candidate.py',
    'sec_excel_factory/verify_ooxml.py',
    'tools/office_web_excel_teacher_worker_v1.py',
    'tools/office_web_ppt_teacher_worker_v1.py',
    'tools/office_web_excel_graph_readback_v1.py',
    'tools/office_web_ppt_graph_readback_v1.py',
    'tools/excel_web_e2b_v066_train_adapter.py',
    'src/cursibench/scale_action_output_v066.py',
    'src/cursibench/scale_action_contract_v066.py',
    'src/cursibench/scale_vision_proxy.py',
    'src/cursibench/full_study_selection_paid_coverage_v1.py',
)


class ExcelSelectionError(ValueError):
    pass


class ExcelSelectionProviderUncertain(ExcelSelectionError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise ExcelSelectionError(code)


def _sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _write_new(path: Path, raw: bytes) -> str:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(raw)


def source_hashes() -> dict[str, str]:
    return {relative: _sha((ROOT / relative).read_bytes())
            for relative in SOURCE_FILES}


def runtime_sha256() -> str:
    return _sha(_canonical(source_hashes()))


def _private_json(path: Path, root: Path, label: str) -> tuple[dict, bytes]:
    return train_worker._private_json(path, root, label)


def _private_bytes(path: Path, root: Path, label: str,
                   maximum: int = 50_000_000) -> bytes:
    return train_worker._private_bytes(path, root, label, maximum)


def _item(value: object, label: str) -> dict:
    _require(type(value) is dict and set(value) == {
        'owner_user_id', 'drive_id', 'item_id', 'file_name', 'edit_url'},
        label + '_selection_item_shape_invalid')
    url = boundary.validate_selection_url(value['edit_url'])
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    _require(all(type(value[key]) is str and
                 train_worker._ID.fullmatch(value[key])
                 for key in ('owner_user_id', 'drive_id', 'item_id')) and
             query.get('file') == [value['file_name']],
             label + '_selection_item_identity_invalid')
    return value


class SelectionOracleSubprocess(train_worker.SecOracleSubprocess):
    """SEC selection scorer in an evaluator process, outside the GUI actor."""

    def _run(self, args: list[str], *, may_fail: bool = False) -> dict:
        completed = subprocess.run(
            [sys.executable, str(ROOT / 'tools/sec_excel_web_selection_oracle_v1.py'),
             *args], cwd=ROOT, capture_output=True, text=True,
            timeout=180, check=False)
        _require(completed.returncode in ((0, 1) if may_fail else (0,)) and
                 len(completed.stdout.encode()) <= 1_000_000,
                 'excel_selection_oracle_process_failed')
        try:
            result = json.loads(completed.stdout)
        except (UnicodeError, json.JSONDecodeError):
            raise ExcelSelectionError(
                'excel_selection_oracle_output_invalid') from None
        _require(type(result) is dict,
                 'excel_selection_oracle_output_invalid')
        return result


def _started(session, started: dict, checkpoint_path: str) -> dict:
    _require(type(started) is dict and set(started) == {
        'attempt_id', 'checkpoint_path_sha256',
        'selection_tasks', 'selection_identities_sha256',
        'task_count'} and
        type(started['attempt_id']) is str and
        campaign.dollars.ATTEMPT.fullmatch(started['attempt_id']) and
        type(checkpoint_path) is str and
        campaign.TINKER_PATH.fullmatch(checkpoint_path) is not None and
        _sha(checkpoint_path) == started['checkpoint_path_sha256'] and
        type(started['selection_tasks']) is list and
        len(started['selection_tasks']) == MAX_TASKS and
        started['task_count'] == MAX_TASKS and
        _sha(_canonical(started['selection_tasks'])) ==
        started['selection_identities_sha256'] and
        session.intent['cell_id'] == 'excel-web' and
        list(session.views['selection']) == started['selection_tasks'],
        'excel_selection_start_or_checkpoint_unbound')
    seen = set()
    for row in started['selection_tasks']:
        _require(type(row) is dict and
                 set(row) == {'task_id', 'package_sha256'} and
                 type(row['task_id']) is str and
                 _TASK_ID.fullmatch(row['task_id']) and
                 row['task_id'] not in seen and
                 type(row['package_sha256']) is str and
                 _HEX.fullmatch(row['package_sha256']),
                 'excel_selection_roster_invalid')
        seen.add(row['task_id'])
    events = [row for row in session._events('selection_started')
              if row['data']['attempt_id'] == started['attempt_id']]
    _require(len(events) == 1 and
             events[0]['data']['checkpoint_path_sha256'] ==
             started['checkpoint_path_sha256'] and
             events[0]['data']['selection_identities_sha256'] ==
             started['selection_identities_sha256'],
             'excel_selection_start_not_in_campaign_journal')
    return started


def _student_config(session) -> tuple[dict, str]:
    config, sha = session.study.student_training_configuration()
    _require(type(config) is dict and
             config.get('model') == MODEL and
             config.get('action_profile') == ACTION_PROFILE_VERSION and
             type(config.get('sample_max_tokens')) is int and
             0 < config['sample_max_tokens'] <= 4096 and
             type(config.get('seed')) is int and
             type(sha) is str and _HEX.fullmatch(sha),
             'excel_selection_student_config_unbound')
    for key in ('prefill_usd_per_million_tokens',
                'sample_usd_per_million_tokens',
                'billing_multiplier_upper'):
        try:
            value = Decimal(config[key])
        except Exception:
            raise ExcelSelectionError(
                'excel_selection_student_rate_invalid') from None
        _require(value.is_finite() and value > 0 and
                 (key != 'billing_multiplier_upper' or value >= 1),
                 'excel_selection_student_rate_invalid')
    return config, sha


def sample_reserve_usd(config: dict) -> str:
    amount = ((Decimal(MAX_INPUT_TOKENS) *
               Decimal(config['prefill_usd_per_million_tokens']) +
               Decimal(config['sample_max_tokens']) *
               Decimal(config['sample_usd_per_million_tokens'])) /
              Decimal(1_000_000) *
              Decimal(config['billing_multiplier_upper']))
    return str(amount.quantize(Decimal('0.000000001'),
                               rounding=ROUND_CEILING))


class RealTinkerSelectionSampler:
    """Creates one checkpoint-bound sampler; no base or text-only fallback."""

    def __init__(self, checkpoint_path: str, config: dict,
                 attempt_id: str, out_dir: Path):
        self.checkpoint_path = checkpoint_path
        self.config = config
        self.attempt_id = attempt_id
        self.out_dir = out_dir
        self.service = None
        self.backend = None
        self.renderer = None
        self.adapters = {}

    def setup(self) -> dict:
        import tinker
        from cursibench.scale_vision_proxy import (
            TinkerVisionBackend, campaign_metadata,
        )
        self.renderer = QwenVisionRenderer.load()
        self.service = tinker.ServiceClient(user_metadata=campaign_metadata(
            'excel-selection-' + _sha(self.attempt_id)[:12]))
        try:
            self.backend = TinkerVisionBackend.from_service(
                self.service, self.renderer,
                checkpoint=self.checkpoint_path,
                seed=self.config['seed'])
            _require(self.backend.identity.get('sampling_kind') ==
                     'checkpoint' and
                     self.backend.identity.get('checkpoint_sha256') ==
                     vision_digest(self.checkpoint_path),
                     'excel_selection_sampler_checkpoint_changed')
        except Exception:
            self.close(success=False)
            raise ExcelSelectionProviderUncertain(
                'excel_selection_sampler_setup_uncertain') from None
        return {'status': 'completed',
                'model': MODEL,
                'checkpoint_path_sha256': _sha(self.checkpoint_path),
                'renderer_identity_sha256':
                    _sha(_canonical(self.renderer.identity))}

    def sample(self, observation: Observation, *,
               task_index: int, step: int) -> dict:
        from cursibench.scale_vision_proxy import (
            Limits, VisionSamplingAdapter,
        )
        adapter = self.adapters.get(task_index)
        if adapter is None:
            path = self.out_dir / f'task-{task_index:02d}' / 'sampling-journal'
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            adapter = VisionSamplingAdapter(
                self.backend, path,
                limits=Limits(max_actions=MAX_ACTIONS,
                              input_tokens=MAX_INPUT_TOKENS,
                              output_tokens=self.config['sample_max_tokens'],
                              request_timeout_seconds=120))
            self.adapters[task_index] = adapter
        rendered = output_v066.render_for_model(observation)
        request_id = ('excel-sel-' + _sha(self.attempt_id)[:10] +
                      f'-{task_index:02d}-{step:03d}')
        return adapter.sample(request_id=request_id, **rendered)

    def close(self, *, success: bool) -> None:
        if self.service is not None:
            service = self.service
            self.service = None
            service.close('success' if success else 'errored').result(
                timeout=30)


class PaidSelectionSampler:
    def __init__(self, *, session, started: dict,
                 config: dict, config_sha256: str,
                 delegate, paid_ids: list[str], out_dir: Path):
        self.session = session
        self.started = started
        self.config = config
        self.config_sha256 = config_sha256
        self.delegate = delegate
        self.paid_ids = paid_ids
        self.out_dir = Path(out_dir)

    def setup(self, paid_id: str) -> None:
        _require(paid_id.startswith(
            self.started['attempt_id'] + '-sampler-setup-'),
            'excel_selection_setup_attempt_id_invalid')
        request = {
            'schema': 'cua-full-study-selection-sampling-request-v1',
            'cell_id': 'excel-web',
            'selection_attempt': self.started['attempt_id'],
            'selection_identities_sha256':
                self.started['selection_identities_sha256'],
            'checkpoint_path_sha256':
                self.started['checkpoint_path_sha256'],
            'worker_runtime_sha256': runtime_sha256(),
            'student_config_sha256': self.config_sha256,
            'operation': 'sampler_setup',
            'sampler_setup_attempt_id': paid_id,
        }
        def call(_request):
            result = self.delegate.setup()
            _require(type(result) is dict and
                     result.get('status') == 'completed' and
                     result.get('model') == MODEL and
                     result.get('checkpoint_path_sha256') ==
                     self.started['checkpoint_path_sha256'],
                     'excel_selection_sampler_setup_ambiguous')
            return result
        paid = self.session.dispatch_paid(
            attempt_id=paid_id, category='tinker',
            work=request, request=request,
            reserve_usd=sample_reserve_usd(self.config),
            resource_reservation={}, provider=call)
        _require(paid.get('attempt_id') == paid_id,
                 'excel_selection_sampler_setup_not_paid')
        self.paid_ids.append(paid_id)

    def sample(self, observation: Observation, *,
               task_index: int, step: int) -> dict:
        _require(type(observation) is Observation and
                 1 <= task_index <= MAX_TASKS and
                 0 <= step < MAX_ACTIONS and
                 observation.task_id ==
                 self.started['selection_tasks'][task_index - 1]['task_id'] and
                 observation.task_binding_sha256 ==
                 self.started['selection_tasks'][task_index - 1]
                 ['package_sha256'] and
                 len(observation.screenshot_bytes) <= 4_000_000,
                 'excel_selection_paid_sample_frame_unbound')
        rendered = output_v066.render_for_model(observation)
        frame_path = (self.out_dir / f'task-{task_index:02d}' /
                      'frames' / f'step-{step:03d}.png')
        frame_raw = _private_bytes(
            frame_path,
            Path(self.session.study.repo_root).resolve() / 'work',
            'excel_selection_current_frame', 4_000_000)
        _require(frame_raw == observation.screenshot_bytes,
                 'excel_selection_current_frame_file_changed')
        paid_id = (self.started['attempt_id'] +
                   f'-sample-{task_index:02d}-{step:03d}')
        request = {
            'schema': 'cua-full-study-selection-sampling-request-v1',
            'cell_id': 'excel-web',
            'selection_attempt': self.started['attempt_id'],
            'selection_identities_sha256':
                self.started['selection_identities_sha256'],
            'checkpoint_path_sha256':
                self.started['checkpoint_path_sha256'],
            'student_config_sha256': self.config_sha256,
            'worker_runtime_sha256': runtime_sha256(),
            'task_id': observation.task_id,
            'package_sha256': observation.task_binding_sha256,
            'task_index': task_index, 'step': step,
            'frame_id': observation.frame_id,
            'frame_sha256': _sha(observation.screenshot_bytes),
            'frame_ref': {
                'path': str(frame_path.relative_to(self.out_dir)),
                'sha256': _sha(frame_raw)},
            'instruction': rendered['instruction'],
            'visible_text': rendered['visible_text'],
            'max_input_tokens': MAX_INPUT_TOKENS,
            'max_output_tokens': self.config['sample_max_tokens'],
        }
        def call(_request):
            result = self.delegate.sample(
                observation, task_index=task_index, step=step)
            usage = result.get('usage') if type(result) is dict else None
            _require(type(result) is dict and
                     result.get('status') == 'completed' and
                     result.get('new_dispatch') is True and
                     result.get('reused') is False and
                     type(result.get('text')) is str and
                     type(usage) is dict and
                     type(usage.get('input_tokens')) is int and
                     type(usage.get('output_tokens')) is int and
                     0 < usage['input_tokens'] <= MAX_INPUT_TOKENS and
                     0 <= usage['output_tokens'] <=
                     self.config['sample_max_tokens'],
                     'excel_selection_tinker_result_or_usage_ambiguous')
            return {'status': 'completed', 'text': result['text'],
                    'usage': usage,
                    'rendered_usage': usage,
                    'sampler_result_sha256': _sha(_canonical(result)),
                    'new_dispatch': True, 'reused': False}
        paid = self.session.dispatch_paid(
            attempt_id=paid_id, category='tinker',
            work={'selection_attempt': self.started['attempt_id'],
                  'task_id': observation.task_id,
                  'package_sha256': observation.task_binding_sha256,
                  'checkpoint_path_sha256':
                      self.started['checkpoint_path_sha256'],
                  'task_index': task_index, 'step': step,
                  'frame_sha256': request['frame_sha256']},
            request=request, reserve_usd=sample_reserve_usd(self.config),
            resource_reservation={}, provider=call)
        _require(paid.get('attempt_id') == paid_id and
                 type(paid.get('result')) is dict and
                 paid['result'].get('status') == 'completed',
                 'excel_selection_paid_sample_ambiguous')
        self.paid_ids.append(paid_id)
        return {**paid['result'], 'paid_attempt_id': paid_id,
                'paid_result_sha256': paid['result_sha256']}


def wait_selection_revocation(episode_dir: Path, item: dict, phase: str,
                              timeout_seconds: int) -> None:
    """Wait for an operator signal, then independently check Graph state."""
    signal = episode_dir / f'{phase}-revoked.private.json'
    end = time.monotonic() + timeout_seconds
    while time.monotonic() < end:
        if signal.is_file() and not signal.is_symlink() and \
                signal.stat().st_mode & 0o077 == 0:
            value = json.loads(signal.read_bytes())
            _require(value == {
                'schema': 'cua-office-excel-selection-revocation-signal-v1',
                'phase': phase, 'item_id_sha256': _sha(item['item_id']),
            }, 'excel_selection_revocation_signal_invalid')
            return
        time.sleep(1)
    raise ExcelSelectionError('excel_selection_revocation_not_signaled')


class SelectionExcelTaskWorker(train_worker.OfficeExcelTeacherWorker):
    """One source-bound SEC selection task, with independent saved/reset reads."""

    def __init__(self, session, binding_path: Path, *,
                 lease_factory=None, graph_reader=None,
                 oracle_runner=None, operator_wait=None,
                 operator_wait_revocation=None,
                 clock: Callable[[], float] = time.time):
        super().__init__(
            session, binding_path,
            lease_factory=lease_factory or boundary.SelectionBridgeLeases(),
            graph_reader=graph_reader or
                graph_module.SelectionExcelGraphOwnerReadback(),
            oracle_runner=oracle_runner or SelectionOracleSubprocess(),
            operator_wait=operator_wait,
            operator_wait_revocation=operator_wait_revocation or
                wait_selection_revocation,
            clock=clock)

    def _binding(self, task: dict) -> tuple[dict, Path, Path, Path]:
        from native_desktop_factory.v066_final_freeze import validate_ratification
        study = self.session.study
        root = Path(study.repo_root).resolve() / 'work'
        rat_path = getattr(study, 'ratification_path', None)
        _require(rat_path is not None and Path(rat_path).is_file() and
                 not Path(rat_path).is_symlink() and
                 Path(rat_path).stat().st_mode & 0o077 == 0,
                 'excel_selection_ratification_missing')
        rat, rat_sha = validate_ratification(Path(rat_path))
        _require(rat_sha == getattr(study, 'ratification_sha256', None) and
                 rat == getattr(study, 'ratification', None) and
                 rat['cell_profiles']['excel-web']['adapter_sha256'] ==
                 train_worker.adapter_bundle_sha256(),
                 'excel_selection_action_ratification_changed')
        binding, _ = _private_json(self.binding_path, root,
                                   'excel_selection_binding')
        fields = {'schema', 'split', 'workflow', 'cell_id', 'task_id',
                  'package_sha256', 'visible_instruction', 'task_path',
                  'task_file_sha256', 'actor_seed_sha256', 'cases_path',
                  'cases_sha256', 'case_id', 'reference_path',
                  'reference_sha256', 'actor_item', 'reset_item',
                  'owner_email_sha256', 'actor_email_sha256',
                  'ratification_sha256', 'frozen_adapter_sha256',
                  'worker_runtime_sha256', 'verifier_sha256',
                  'lease_seconds', 'max_steps', 'wall_seconds',
                  'manual_wait_seconds', 'post_finish_wait_seconds',
                  'e2b_reserve_usd', 'graph_read_reserve_usd'}
        _require(type(binding) is dict and set(binding) == fields and
                 binding['schema'] == BINDING_SCHEMA and
                 binding['split'] == 'selection' and
                 binding['workflow'] == 'sec-integrated' and
                 binding['cell_id'] == 'excel-web' and
                 type(task) is dict and set(task) == {
                     'task_id', 'package_sha256'} and
                 binding['task_id'] == task['task_id'] and
                 binding['package_sha256'] == task['package_sha256'] and
                 type(binding['visible_instruction']) is str and
                 0 < len(binding['visible_instruction'].encode()) <= 16_384 and
                 all(type(binding[key]) is str and _HEX.fullmatch(binding[key])
                     for key in ('task_file_sha256', 'actor_seed_sha256',
                                 'cases_sha256', 'reference_sha256',
                                 'owner_email_sha256', 'actor_email_sha256',
                                 'ratification_sha256',
                                 'frozen_adapter_sha256',
                                 'worker_runtime_sha256', 'verifier_sha256')),
                 'excel_selection_binding_shape_or_task_changed')
        _require(binding['ratification_sha256'] == rat_sha and
                 binding['frozen_adapter_sha256'] ==
                 train_worker.adapter_bundle_sha256() and
                 binding['worker_runtime_sha256'] == runtime_sha256(),
                 'excel_selection_runtime_or_action_source_changed')
        cell = next((row for row in study.plan['cells'] if
                     row['cell_id'] == 'excel-web'), None)
        _require(cell is not None and
                 binding['verifier_sha256'] ==
                 cell['matched_bindings']['verifier'] and
                 task in list(self.session.views['selection']),
                 'excel_selection_verifier_or_roster_changed')
        task_path = Path(binding['task_path'])
        source = boundary.validate_package(task_path, root, {
            **task, 'visible_instruction': binding['visible_instruction']})
        seed_path = task_path.parent / 'actor.xlsx'
        cases_path = Path(binding['cases_path'])
        reference_path = Path(binding['reference_path'])
        _require(reference_path.suffix == '.xlsx' and
                 source['task_sha256'] == binding['task_file_sha256'] and
                 source['actor_sha256'] == binding['actor_seed_sha256'] and
                 _sha(_private_bytes(cases_path, root, 'selection_case',
                                     8_000_000)) == binding['cases_sha256'] and
                 _sha(_private_bytes(reference_path, root,
                                     'selection_reference')) ==
                 binding['reference_sha256'],
                 'excel_selection_source_bytes_changed')
        from tools.sec_excel_web_selection_oracle_v1 import one_selection_case
        one_selection_case(cases_path, binding['case_id'])
        actor = _item(binding['actor_item'], 'actor')
        reset = _item(binding['reset_item'], 'reset')
        _require(actor['owner_user_id'] == reset['owner_user_id'] and
                 actor['drive_id'] == reset['drive_id'] and
                 actor['item_id'] != reset['item_id'] and
                 actor['file_name'] != reset['file_name'] and
                 actor['edit_url'] != reset['edit_url'],
                 'excel_selection_reset_item_not_distinct')
        for key, upper in (('lease_seconds', 3600),
                           ('max_steps', MAX_ACTIONS),
                           ('wall_seconds', 1800),
                           ('manual_wait_seconds', 1800),
                           ('post_finish_wait_seconds', 30)):
            _require(type(binding[key]) is int and
                     0 <= binding[key] <= upper and
                     (key == 'post_finish_wait_seconds' or
                      binding[key] > 0),
                     'excel_selection_time_bound_invalid')
        _require(binding['lease_seconds'] >= 300 and
                 binding['manual_wait_seconds'] +
                 binding['wall_seconds'] + 60 <=
                 binding['lease_seconds'],
                 'excel_selection_lease_cannot_cover_login_and_actor')
        for key in ('e2b_reserve_usd', 'graph_read_reserve_usd'):
            try:
                amount = Decimal(binding[key])
            except Exception:
                raise ExcelSelectionError(
                    'excel_selection_cost_reserve_invalid') from None
            _require(type(binding[key]) is str and amount.is_finite() and
                     amount > 0 and -amount.as_tuple().exponent <= 9,
                     'excel_selection_cost_reserve_invalid')
        calibration = self.oracle_runner.calibrate(
            seed_path, reference_path, cases_path, binding['case_id'])
        _require(type(calibration) is dict and
                 calibration.get('schema') ==
                 'cua-sec-integrated-selection-oracle-calibration-v1' and
                 calibration.get('unsolved_seed_rejected') is True and
                 calibration.get('positive_reference_passed') is True and
                 calibration.get('checked_formula_targets', 0) >= 30 and
                 calibration.get('source_counterfactual_profiles') == 2 and
                 calibration.get('seed_sha256') ==
                 binding['actor_seed_sha256'] and
                 calibration.get('reference_sha256') ==
                 binding['reference_sha256'],
                 'excel_selection_sec_oracle_calibration_failed')
        return binding, task_path, seed_path, cases_path

    def _admit_created_lease(self, *, paid: dict, phase: str,
                             item: dict, binding: dict, directory: Path,
                             episode_dir: Path, task_path: Path):
        root = Path(self.session.study.repo_root).resolve() / 'work'
        session_path = directory / 'session.private.json'
        session, _ = _private_json(session_path, root,
                                   phase + '_selection_login')
        _require(session.get('sandbox_id') == paid['result']['sandbox_id'] and
                 session.get('observed_template_id') ==
                 boundary.EXPECTED_TEMPLATE_ID and
                 session.get('sdk_version') == '2.2.0',
                 'excel_selection_e2b_lease_or_template_changed')
        self.operator_wait(session_path, item, phase,
                           binding['manual_wait_seconds'])
        admission = boundary.admit(
            session_path, task_path, directory / 'run.private.json',
            episode_dir / f'{phase}-admit-unused', work_root=root,
            expected_task={
                'task_id': binding['task_id'],
                'package_sha256': binding['package_sha256'],
                'visible_instruction': binding['visible_instruction']},
            now=int(self.clock()))
        _require(admission.sandbox_id == paid['result']['sandbox_id'] and
                 admission.workbook_url == item['edit_url'] and
                 admission.task_sha256 == binding['task_file_sha256'] and
                 admission.actor_sha256 == binding['actor_seed_sha256'] and
                 admission.max_steps == binding['max_steps'] and
                 admission.wall_seconds == binding['wall_seconds'] and
                 admission.assigned_item_id == item['item_id'] and
                 _sha(admission.actor_email.casefold()) ==
                 binding['actor_email_sha256'],
                 'excel_selection_actor_scope_or_source_changed')
        scope, _ = _private_json(directory / 'actor-scope.private.json',
                                  root, phase + '_selection_scope')
        _require(scope.get('owner_principal_sha256') ==
                 binding['owner_email_sha256'],
                 'excel_selection_owner_scope_changed')
        sandbox = self.lease_factory.connect(admission.sandbox_id)
        _require(sandbox.sandbox_id == admission.sandbox_id and
                 sandbox.get_info(request_timeout=12).template_id ==
                 boundary.EXPECTED_TEMPLATE_ID,
                 'excel_selection_connected_desktop_changed')
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
                 'excel_selection_native_editor_window_not_ready')
        _write_new(episode_dir / f'{phase}-editor.private.json',
                   _canonical({
                       'schema':
                           'cua-office-excel-selection-native-editor-v1',
                       'phase': phase,
                       'file_name_sha256': _sha(item['file_name']),
                       'window_title_sha256': _sha(title),
                       'edit_url_sha256': _sha(item['edit_url']),
                       'sandbox_id_sha256': _sha(admission.sandbox_id),
                   }))
        return paid, session_path, admission, sandbox

    def _graph_actor_revoked(self, *, phase: str, item: dict,
                             binding: dict, episode_dir: Path,
                             lease_session_path: Path) -> dict:
        root = Path(self.session.study.repo_root).resolve() / 'work'
        scope, _ = _private_json(
            lease_session_path.parent / 'actor-scope.private.json',
            root, phase + '_selection_scope_for_revocation')
        snapshot, _ = _private_json(
            lease_session_path.parent /
                'assigned-permissions.private.json',
            root, phase + '_selection_permissions_for_revocation')
        rows = snapshot.get('response', {}).get('value')
        _require(type(rows) is list and
                 type(scope.get('actor_email')) is str and
                 _sha(scope['actor_email'].casefold()) ==
                 binding['actor_email_sha256'],
                 'excel_selection_actor_permission_identity_missing')
        matching = [row for row in rows if type(row) is dict and
                    type(row.get('invitation')) is dict and
                    type(row['invitation'].get('email')) is str and
                    row['invitation']['email'].casefold() ==
                    scope['actor_email'].casefold()]
        _require(len(matching) == 1 and
                 type(matching[0].get('id')) is str and
                 matching[0].get('link') is None and
                 matching[0].get('inheritedFrom') is None,
                 'excel_selection_exact_actor_permission_missing')
        prior_id = matching[0]['id']
        graph_lease, _ = _private_json(
            lease_session_path.parent /
                'selection-graph-lease.private.json',
            root, phase + '_selection_graph_lease_for_revocation')
        _require(graph_lease.get('permission_id_sha256') == _sha(prior_id),
                 'excel_selection_graph_permission_id_changed')
        self.graph_reader.preflight()
        attempt_id = ('graph-excel-selection-' +
                      _sha(str(episode_dir.resolve()))[:16] +
                      '-' + phase + '-revoked')
        request = {
            'schema': 'cua-office-excel-selection-revocation-readback-v1',
            'cell_id': 'excel-web', 'phase': phase,
            'task_package_sha256': binding['package_sha256'],
            'owner_user_id_sha256': _sha(item['owner_user_id']),
            'drive_id_sha256': _sha(item['drive_id']),
            'item_id_sha256': _sha(item['item_id']),
            'actor_email_sha256': _sha(scope['actor_email'].casefold()),
            'prior_permission_id_sha256': _sha(prior_id),
        }
        def verify(_request):
            return self.graph_reader.verify_actor_revoked(
                owner_user_id=item['owner_user_id'],
                drive_id=item['drive_id'], item_id=item['item_id'],
                actor_email=scope['actor_email'],
                prior_permission_id=prior_id)
        paid = self.session.dispatch_paid(
            attempt_id=attempt_id, category='storage_application',
            work=request, request=request,
            reserve_usd=binding['graph_read_reserve_usd'],
            resource_reservation={}, provider=verify)
        result = paid['result']
        _require(type(result) is dict and
                 result.get('schema') ==
                 'cua-office-excel-owner-revocation-readback-v1' and
                 result.get('owner_user_id_sha256') ==
                 _sha(item['owner_user_id']) and
                 result.get('drive_id_sha256') ==
                 _sha(item['drive_id']) and
                 result.get('item_id_sha256') == _sha(item['item_id']) and
                 result.get('actor_email_sha256') ==
                 _sha(scope['actor_email'].casefold()) and
                 result.get('prior_permission_id_sha256') ==
                 _sha(prior_id) and
                 result.get('actor_grants_remaining') == 0 and
                 result.get('broad_links_remaining') == 0 and
                 all(type(result.get(name)) is int and
                     result[name] >= 0 for name in (
                         'remaining_permission_count',
                         'owner_permission_count',
                         'inherited_permission_count',
                         'existing_access_link_count')),
                 'excel_selection_actor_permission_not_revoked')
        return result

    def run_task(self, *, task: dict, out_dir: Path,
                 sample_student: Callable,
                 dispatch_e2b: Callable) -> dict:
        """Return a verified 0/1 row only after exact saved/reset evidence."""
        _require(callable(sample_student) and callable(dispatch_e2b),
                 'excel_selection_callbacks_required')
        root = Path(self.session.study.repo_root).resolve() / 'work'
        out_dir = Path(out_dir).absolute()
        _require(Path.cwd().resolve() ==
                 Path(self.session.study.repo_root).resolve() and
                 out_dir.is_dir() and not out_dir.is_symlink() and
                 out_dir.resolve().is_relative_to(root) and
                 (out_dir / 'frames').is_dir() and
                 not (out_dir / 'task-receipt.private.json').exists(),
                 'excel_selection_task_directory_not_fresh')
        binding, task_path, seed_path, cases_path = self._binding({
            'task_id': task['task_id'],
            'package_sha256': task['package_sha256']})
        _require(task['visible_instruction'] ==
                 binding['visible_instruction'],
                 'excel_selection_actor_instruction_changed')
        artifacts = out_dir / 'artifacts'
        artifacts.mkdir(mode=0o700)
        preflight_path, preflight_graph = self._graph_capture(
            phase='actor-preflight', item=binding['actor_item'],
            binding=binding, episode_dir=out_dir)
        preflight = self.oracle_runner.neutral(seed_path, preflight_path)
        _require(self._neutral_selection(preflight,
                                         binding['actor_seed_sha256']),
                 'excel_selection_actor_item_not_neutral_seed')
        actor_session = reset_session = None
        actor_stopped = reset_stopped = False
        actor_paid = reset_paid = None
        sample_ids: list[str] = []
        try:
            actor_paid, actor_session, admission, sandbox = self._lease(
                phase='actor', item=binding['actor_item'],
                binding=binding, episode_dir=out_dir,
                task_path=task_path, dispatch_e2b=dispatch_e2b)

            def sample_current(observation, current_frame_id):
                paid = sample_student(observation)
                _require(paid.get('status') == 'completed' and
                         type(paid.get('paid_attempt_id')) is str and
                         type(paid.get('paid_result_sha256')) is str and
                         _HEX.fullmatch(paid['paid_result_sha256']),
                         'excel_selection_current_sample_not_paid')
                action = output_v066.normalize_model_action(
                    paid['text'], observation,
                    current_frame_id=current_frame_id())
                sample_ids.append(paid['paid_attempt_id'])
                return {
                    'action': action,
                    'teacher_result_sha256': paid['paid_result_sha256'],
                    'trace_row': {
                        'schema': 'cua-office-excel-selection-action-v1',
                        'step': observation.step,
                        'frame_sha256':
                            observation.screenshot['sha256'],
                        'paid_attempt_id': paid['paid_attempt_id'],
                        'paid_result_sha256':
                            paid['paid_result_sha256'],
                        'action_sha256': _sha(_canonical(action)),
                    },
                }

            traces, status = ppt_worker.OfficePptTeacherWorker._actor_loop(
                self, sandbox=sandbox, admission=admission,
                task=task, out_dir=out_dir,
                sample_teacher=sample_current,
                max_steps=binding['max_steps'])
            _require(status == 'finished' and
                     len(traces) == len(sample_ids) >= 1,
                     'excel_selection_gui_trace_incomplete')
            actor_stopped = self.lease_factory.stop(actor_session) == 'killed'
            _require(actor_stopped,
                     'excel_selection_actor_sandbox_not_terminated')
            if binding['post_finish_wait_seconds']:
                time.sleep(binding['post_finish_wait_seconds'])
            saved_path, saved_graph = self._graph_capture(
                phase='saved', item=binding['actor_item'],
                binding=binding, episode_dir=out_dir)
            scored = self.oracle_runner.score(
                saved_path, seed_path, cases_path, binding['case_id'])
            saved_sha = _sha(_private_bytes(
                saved_path, root, 'excel_selection_saved_download'))
            _require(type(scored) is dict and
                     scored.get('schema') ==
                     'cua-sec-integrated-selection-saved-score-v1' and
                     scored.get('status') == 'scored' and
                     type(scored.get('score')) is int and
                     scored['score'] in (0, 1) and
                     scored.get('candidate_sha256') == saved_sha and
                     scored.get('seed_sha256') ==
                     binding['actor_seed_sha256'] and
                     type(scored.get('preservation_pass')) is bool and
                     type(scored.get('checked_formula_targets')) is int and
                     scored['checked_formula_targets'] >= 30 and
                     (scored['score'] == 0 or
                      (scored['preservation_pass'] is True and
                       scored.get('source_counterfactual_profiles') == 2 and
                       scored.get('error_count') == 0)),
                     'excel_selection_saved_verifier_invalid')
            verifier_receipt = {
                'schema': 'cua-office-excel-selection-verifier-v1',
                'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'score': scored['score'],
                'saved_state_sha256': saved_sha,
                'owner_double_download_sha256':
                    _sha(_canonical(saved_graph)),
                'oracle_result': scored,
                'evaluator_isolated': True,
                'original_software_gui': True,
            }
            verifier_sha = _write_new(
                out_dir / 'verifier.private.json',
                _canonical(verifier_receipt))
            self.operator_wait_revocation(
                out_dir, binding['actor_item'], 'actor',
                binding['manual_wait_seconds'])
            actor_revoked = self._graph_actor_revoked(
                phase='actor', item=binding['actor_item'],
                binding=binding, episode_dir=out_dir,
                lease_session_path=actor_session)

            reset_paid, reset_session, reset_admission, reset_sandbox = \
                self._lease(
                    phase='reset', item=binding['reset_item'],
                    binding=binding, episode_dir=out_dir,
                    task_path=task_path, dispatch_e2b=dispatch_e2b)
            reset_frame = bytes(reset_sandbox.screenshot())
            _require(reset_frame.startswith(b'\x89PNG\r\n\x1a\n') and
                     len(reset_frame) > 100,
                     'excel_selection_fresh_reset_gui_not_observed')
            _write_new(artifacts / 'reset-open.private.png', reset_frame)
            reset_stopped = self.lease_factory.stop(reset_session) == 'killed'
            _require(reset_stopped and
                     actor_paid['result']['sandbox_id'] !=
                     reset_paid['result']['sandbox_id'],
                     'excel_selection_reset_lease_not_fresh_or_terminated')
            reset_path, reset_graph = self._graph_capture(
                phase='reset', item=binding['reset_item'],
                binding=binding, episode_dir=out_dir)
            neutral = self.oracle_runner.neutral(seed_path, reset_path)
            _require(self._neutral_selection(
                neutral, binding['actor_seed_sha256']),
                'excel_selection_fresh_copy_reset_changed')
            self.operator_wait_revocation(
                out_dir, binding['reset_item'], 'reset',
                binding['manual_wait_seconds'])
            reset_revoked = self._graph_actor_revoked(
                phase='reset', item=binding['reset_item'],
                binding=binding, episode_dir=out_dir,
                lease_session_path=reset_session)
            reset_receipt = {
                'schema': 'cua-office-excel-selection-reset-v1',
                'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'fresh_sandbox': True,
                'actor_sandbox_id_sha256':
                    _sha(actor_paid['result']['sandbox_id']),
                'reset_sandbox_id_sha256':
                    _sha(reset_paid['result']['sandbox_id']),
                'reset_open_screenshot_sha256': _sha(reset_frame),
                'reset_double_download_sha256':
                    _sha(_canonical(reset_graph)),
                'neutral_result': neutral,
                'actor_permission_revoked_sha256':
                    _sha(_canonical(actor_revoked)),
                'reset_permission_revoked_sha256':
                    _sha(_canonical(reset_revoked)),
            }
            reset_sha = _write_new(out_dir / 'reset.private.json',
                                   _canonical(reset_receipt))
            task_receipt = {
                'schema': TASK_SCHEMA,
                'cell_id': 'excel-web', 'split': 'selection',
                'workflow': 'sec-integrated',
                'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'binding_sha256': _sha(self.binding_path.read_bytes()),
                'worker_runtime_sha256': runtime_sha256(),
                'score': scored['score'],
                'saved_state_sha256': saved_sha,
                'verifier_receipt_sha256': verifier_sha,
                'reset_receipt_sha256': reset_sha,
                'sample_paid_attempt_ids': sample_ids,
                'e2b_paid_attempt_ids': [actor_paid['attempt_id'],
                                          reset_paid['attempt_id']],
                'action_trace_sha256':
                    _sha((out_dir / 'actions.private.json').read_bytes()),
                'actor_preflight_sha256':
                    _sha(_canonical(preflight_graph)),
                'evaluator_isolated': True,
            }
            receipt_sha = _write_new(
                out_dir / 'task-receipt.private.json',
                _canonical(task_receipt))
            return {'task_receipt_path': str(out_dir /
                                               'task-receipt.private.json'),
                    'task_receipt_sha256': receipt_sha,
                    'result_row': {
                        key: task_receipt[key] for key in (
                            'task_id', 'package_sha256', 'score',
                            'saved_state_sha256',
                            'verifier_receipt_sha256',
                            'reset_receipt_sha256')},
                    'paid_attempt_ids': sample_ids + [
                        actor_paid['attempt_id'],
                        reset_paid['attempt_id']]}
        finally:
            for path, stopped in ((actor_session, actor_stopped),
                                  (reset_session, reset_stopped)):
                if path is not None and not stopped:
                    try:
                        self.lease_factory.stop(path)
                    except Exception:
                        pass

    @staticmethod
    def _neutral_selection(value: object, seed_sha: str) -> bool:
        return (type(value) is dict and
                value.get('schema') ==
                'cua-sec-integrated-selection-neutral-v1' and
                value.get('equivalent') is True and
                value.get('structure_pass') is True and
                value.get('changed_cell_count') == 0 and
                type(value.get('cell_count')) is int and
                value['cell_count'] > 0 and
                value.get('source_sha256') == seed_sha)


class SelectionTaskLedger:
    """Append-only private hash chain; an interrupted task cannot be replayed."""

    def __init__(self, path: Path, header: dict):
        self.path = Path(path)
        self.header = header
        if not self.path.exists():
            _write_new(self.path, _canonical({
                'schema': TASK_LEDGER_SCHEMA, 'sequence': 0,
                'kind': 'header', 'data': header, 'previous': None,
                'hash': _sha(_canonical({
                    'schema': TASK_LEDGER_SCHEMA, 'sequence': 0,
                    'kind': 'header', 'data': header,
                    'previous': None})),
            }))
        self.rows()

    def rows(self) -> list[dict]:
        _require(not self.path.is_symlink() and
                 self.path.stat().st_mode & 0o077 == 0,
                 'excel_selection_ledger_private_required')
        lines = self.path.read_bytes().splitlines()
        _require(bool(lines), 'excel_selection_ledger_empty')
        rows = []
        previous = None
        for index, line in enumerate(lines):
            try:
                row = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ExcelSelectionError(
                    'excel_selection_ledger_json_invalid') from None
            _require(type(row) is dict and set(row) == {
                'schema', 'sequence', 'kind', 'data',
                'previous', 'hash'} and
                row['schema'] == TASK_LEDGER_SCHEMA and
                row['sequence'] == index and
                row['previous'] == previous and
                type(row['kind']) is str and
                type(row['data']) is dict and
                row['hash'] == _sha(_canonical({
                    key: row[key] for key in (
                        'schema', 'sequence', 'kind', 'data',
                        'previous')})),
                'excel_selection_ledger_hash_or_sequence_broken')
            rows.append(row)
            previous = row['hash']
        _require(rows[0]['kind'] == 'header' and
                 rows[0]['data'] == self.header,
                 'excel_selection_ledger_header_changed')
        return rows

    def append(self, kind: str, data: dict) -> dict:
        rows = self.rows()
        core = {'schema': TASK_LEDGER_SCHEMA,
                'sequence': len(rows), 'kind': kind,
                'data': data, 'previous': rows[-1]['hash']}
        row = {**core, 'hash': _sha(_canonical(core))}
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
        with os.fdopen(fd, 'ab') as stream:
            stream.write(_canonical(row))
            stream.flush()
            os.fsync(stream.fileno())
        return row


def _live_selection_graph_gate(_bindings: list[dict]) -> None:
    # The owner-side Graph controller deliberately grants only train items.
    # A separate, source-frozen selection matrix/account pilot must be built
    # before this default can authorize any paid provider dispatch.
    raise ExcelSelectionError(
        'excel_selection_graph_matrix_and_actor_account_not_qualified')


class ExcelSelectionBatch:
    """Exact 20-roster orchestrator; default live gate refuses current state."""

    def __init__(self, session, started: dict, checkpoint_path: str,
                 manifest_path: Path, out_dir: Path, *,
                 task_worker_factory=None, sampler_factory=None,
                 selection_graph_gate=None):
        self.session = session
        self.started = _started(session, started, checkpoint_path)
        self.checkpoint_path = checkpoint_path
        self.manifest_path = Path(manifest_path)
        self.out_dir = Path(out_dir).absolute()
        self.task_worker_factory = task_worker_factory or (
            lambda path: SelectionExcelTaskWorker(session, path))
        self.sampler_factory = sampler_factory or (
            lambda config: RealTinkerSelectionSampler(
                checkpoint_path, config, started['attempt_id'],
                self.out_dir))
        self.selection_graph_gate = (selection_graph_gate or
                                     _live_selection_graph_gate)

    def preflight(self) -> tuple[list[tuple[dict, Path, object, dict]],
                                 dict, str]:
        """Validate all source/ratification/SEC cases before a paid call."""
        from cursibench.full_study_teacher_adapter_v1 import _frozen_session
        _frozen_session(self.session)
        repo = Path(self.session.study.repo_root).resolve()
        root = repo / 'work'
        _require(Path.cwd().resolve() == repo and
                 self.out_dir.resolve().is_relative_to(root) and
                 not self.out_dir.is_symlink() and
                 self.manifest_path.resolve().is_relative_to(root),
                 'excel_selection_private_repo_work_required')
        manifest, _ = _private_json(self.manifest_path, root,
                                    'excel_selection_manifest')
        _require(set(manifest) == {
            'schema', 'cell_id', 'split', 'selection_attempt',
            'selection_identities_sha256', 'checkpoint_path_sha256',
            'worker_runtime_sha256', 'tasks'} and
            manifest['schema'] == BATCH_SCHEMA and
            manifest['cell_id'] == 'excel-web' and
            manifest['split'] == 'selection' and
            manifest['selection_attempt'] == self.started['attempt_id'] and
            manifest['selection_identities_sha256'] ==
                self.started['selection_identities_sha256'] and
            manifest['checkpoint_path_sha256'] ==
                self.started['checkpoint_path_sha256'] and
            manifest['worker_runtime_sha256'] == runtime_sha256() and
            type(manifest['tasks']) is list and
            len(manifest['tasks']) == MAX_TASKS,
            'excel_selection_manifest_not_frozen_start')
        config, config_sha = _student_config(self.session)
        prepared = []
        for expected, entry in zip(self.started['selection_tasks'],
                                   manifest['tasks']):
            _require(type(entry) is dict and set(entry) == {
                'task_id', 'package_sha256', 'binding_path',
                'binding_sha256'} and
                entry['task_id'] == expected['task_id'] and
                entry['package_sha256'] ==
                    expected['package_sha256'] and
                type(entry['binding_sha256']) is str and
                _HEX.fullmatch(entry['binding_sha256']),
                'excel_selection_manifest_task_order_changed')
            path = Path(entry['binding_path'])
            _require(_sha(_private_bytes(
                path, root, 'excel_selection_binding')) ==
                entry['binding_sha256'],
                'excel_selection_binding_bytes_changed')
            worker = self.task_worker_factory(path)
            binding, _task_path, _seed_path, _cases_path = \
                worker._binding(expected)
            prepared.append((expected, path, worker, binding))
        # The default gate is deliberately closed; offline tests inject a
        # fake gate. It is evaluated after all 20 source checks and before
        # Tinker setup, E2B lease, or Graph readback.
        self.selection_graph_gate([row[3] for row in prepared])
        if hasattr(self.session, '_counter_totals'):
            hours = sum(Decimal(row[3]['lease_seconds']) * 2 /
                        Decimal(3600) for row in prepared)
            used = self.session._counter_totals()['e2b_sandbox_hours']
            cap = Decimal(str(self.session.intent['e2b_sandbox_hours_cap']))
            _require(used + hours <= cap,
                     'excel_selection_twenty_task_e2b_hour_cap_exhausted')
        return prepared, config, config_sha

    def _completed_rows(self, ledger: SelectionTaskLedger,
                        prepared: list[tuple]) -> tuple[list[dict], list[str]]:
        events = ledger.rows()[1:]
        _require(all(row['kind'] in {'sampler_setup', 'task_started',
                                     'task_completed',
                                     'selection_scored'} for row in events) and
                 all(row['kind'] != 'selection_scored' or
                     index == len(events) - 1
                     for index, row in enumerate(events)),
                 'excel_selection_ledger_event_invalid')
        rows = [row for row in events if row['kind'] in
                {'task_started', 'task_completed'}]
        _require(len(rows) % 2 == 0 and
                 all(rows[index]['kind'] == 'task_started' and
                     rows[index + 1]['kind'] == 'task_completed'
                     for index in range(0, len(rows), 2)),
                 'excel_selection_inflight_task_requires_reconciliation')
        result_rows = []
        paid_ids = []
        root = Path(self.session.study.repo_root).resolve() / 'work'
        for task_index in range(len(rows) // 2):
            expected, binding_path, _worker, _binding = prepared[task_index]
            started = rows[task_index * 2]['data']
            completed = rows[task_index * 2 + 1]['data']
            receipt_path = self.out_dir / f'task-{task_index + 1:02d}' / \
                'task-receipt.private.json'
            receipt, receipt_raw = _private_json(
                receipt_path, root, 'excel_selection_completed_task')
            task_dir = receipt_path.parent
            saved_first = _private_bytes(
                task_dir / 'artifacts' / 'saved-graph' /
                    'first.private.xlsx', root,
                'excel_selection_reopened_saved')
            saved_second = _private_bytes(
                task_dir / 'artifacts' / 'saved-graph' /
                    'second.private.xlsx', root,
                'excel_selection_reopened_saved')
            verifier, verifier_raw = _private_json(
                task_dir / 'verifier.private.json', root,
                'excel_selection_reopened_verifier')
            reset, reset_raw = _private_json(
                task_dir / 'reset.private.json', root,
                'excel_selection_reopened_reset')
            _require(started == {
                'task_index': task_index + 1,
                'task_id': expected['task_id'],
                'package_sha256': expected['package_sha256'],
                'binding_sha256': _sha(binding_path.read_bytes()),
            } and
                completed.get('task_index') == task_index + 1 and
                completed.get('task_receipt_sha256') ==
                _sha(receipt_raw) and
                completed.get('result_row') == {
                    key: receipt[key] for key in (
                        'task_id', 'package_sha256', 'score',
                        'saved_state_sha256',
                        'verifier_receipt_sha256',
                        'reset_receipt_sha256')} and
                receipt.get('schema') == TASK_SCHEMA and
                receipt.get('task_id') == expected['task_id'] and
                receipt.get('package_sha256') ==
                expected['package_sha256'] and
                receipt.get('worker_runtime_sha256') ==
                runtime_sha256() and
                saved_first == saved_second and
                _sha(saved_first) ==
                    receipt['saved_state_sha256'] and
                _sha(verifier_raw) ==
                    receipt['verifier_receipt_sha256'] and
                _sha(reset_raw) ==
                    receipt['reset_receipt_sha256'] and
                verifier.get('schema') ==
                    'cua-office-excel-selection-verifier-v1' and
                verifier.get('task_id') == expected['task_id'] and
                verifier.get('score') == receipt['score'] and
                verifier.get('saved_state_sha256') ==
                    receipt['saved_state_sha256'] and
                reset.get('schema') ==
                    'cua-office-excel-selection-reset-v1' and
                reset.get('task_id') == expected['task_id'] and
                reset.get('fresh_sandbox') is True and
                completed.get('paid_attempt_ids') ==
                receipt['sample_paid_attempt_ids'] +
                receipt['e2b_paid_attempt_ids'],
                'excel_selection_completed_task_receipt_changed')
            result_rows.append(completed['result_row'])
            paid_ids.extend(completed['paid_attempt_ids'])
        return result_rows, paid_ids

    def run(self) -> dict:
        prepared, config, config_sha = self.preflight()
        self.out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.out_dir.chmod(0o700)
        lock_path = self.out_dir / '.selection-run.lock'
        _require(not lock_path.is_symlink(),
                 'excel_selection_lock_symlink')
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ExcelSelectionError(
                    'excel_selection_attempt_already_running') from None
            return self._run_locked(prepared, config, config_sha)

    def _run_locked(self, prepared: list[tuple], config: dict,
                    config_sha: str) -> dict:
        header = {
            'cell_id': 'excel-web', 'split': 'selection',
            'selection_attempt': self.started['attempt_id'],
            'selection_identities_sha256':
                self.started['selection_identities_sha256'],
            'checkpoint_path_sha256':
                self.started['checkpoint_path_sha256'],
            'manifest_sha256': _sha(self.manifest_path.read_bytes()),
            'worker_runtime_sha256': runtime_sha256(),
        }
        ledger = SelectionTaskLedger(
            self.out_dir / 'tasks.private.jsonl', header)
        _require(not any(row['kind'] == 'selection_scored' for row in
                         ledger.rows()[1:]),
                 'excel_selection_already_scored_no_replay')
        result_rows, task_paid_ids = self._completed_rows(ledger, prepared)
        previous_setups = [row['data']['paid_attempt_id'] for row in
                           ledger.rows()[1:] if row['kind'] ==
                           'sampler_setup']
        _require(len(previous_setups) <= 2 and
                 len(previous_setups) == len(set(previous_setups)),
                 'excel_selection_sampler_resume_limit_or_duplicate')
        paid_ids = previous_setups + task_paid_ids
        sampler_delegate = None
        scored_recorded = False
        try:
            if len(result_rows) < MAX_TASKS:
                sampler_delegate = self.sampler_factory(config)
                sampler = PaidSelectionSampler(
                    session=self.session, started=self.started,
                    config=config, config_sha256=config_sha,
                    delegate=sampler_delegate, paid_ids=paid_ids,
                    out_dir=self.out_dir)
                # A restart opens a new, separately paid setup attempt. A
                # started but unfinished task is never automatically replayed.
                setup_id = self.started['attempt_id'] + \
                    f'-sampler-setup-{len(previous_setups) + 1:02d}'
                sampler.setup(setup_id)
                ledger.append('sampler_setup', {
                    'paid_attempt_id': setup_id})
                for index in range(len(result_rows), MAX_TASKS):
                    expected, binding_path, worker, binding = prepared[index]
                    task_index = index + 1
                    task = {**expected,
                            'visible_instruction':
                                binding['visible_instruction']}
                    directory = self.out_dir / f'task-{task_index:02d}'
                    directory.mkdir(mode=0o700)
                    (directory / 'frames').mkdir(mode=0o700)
                    before = set(paid_ids)
                    ledger.append('task_started', {
                        'task_index': task_index,
                        'task_id': expected['task_id'],
                        'package_sha256': expected['package_sha256'],
                        'binding_sha256': _sha(binding_path.read_bytes()),
                    })

                    def dispatch_e2b(*, lease_seconds, reserve_usd,
                                     provider, phase):
                        paid_id = (self.started['attempt_id'] +
                                   f'-e2b-{task_index:02d}-{phase}')
                        request = {
                            'schema':
                                'cua-office-excel-selection-e2b-lease-v1',
                            'cell_id': 'excel-web',
                            'selection_attempt':
                                self.started['attempt_id'],
                            'task_id': expected['task_id'],
                            'package_sha256':
                                expected['package_sha256'],
                            'checkpoint_path_sha256':
                                self.started['checkpoint_path_sha256'],
                            'phase': phase,
                            'lease_seconds': lease_seconds,
                            'worker_runtime_sha256': runtime_sha256(),
                        }
                        hours = str(Decimal(lease_seconds) /
                                    Decimal(3600))
                        paid = self.session.dispatch_paid(
                            attempt_id=paid_id, category='e2b',
                            work=request, request=request,
                            reserve_usd=reserve_usd,
                            resource_reservation={
                                'e2b_sandbox_hours': hours,
                                'e2b_peak_concurrency': '1'},
                            provider=provider)
                        _require(paid.get('attempt_id') == paid_id and
                                 type(paid.get('result')) is dict and
                                 paid['result'].get('created') is True and
                                 type(paid['result'].get('sandbox_id')) is str,
                                 'excel_selection_e2b_paid_result_ambiguous')
                        paid_ids.append(paid_id)
                        return paid

                    def sample_student(observation):
                        return sampler.sample(
                            observation, task_index=task_index,
                            step=observation.step)

                    completed = worker.run_task(
                        task=task, out_dir=directory,
                        sample_student=sample_student,
                        dispatch_e2b=dispatch_e2b)
                    newly_paid = [paid_id for paid_id in paid_ids if
                                  paid_id not in before]
                    _require(type(completed) is dict and
                             set(completed) == {
                                 'task_receipt_path',
                                 'task_receipt_sha256', 'result_row',
                                 'paid_attempt_ids'} and
                             set(completed['paid_attempt_ids']) ==
                             set(newly_paid) and
                             len(completed['paid_attempt_ids']) ==
                             len(newly_paid) and
                             completed['result_row']['task_id'] ==
                             expected['task_id'] and
                             completed['result_row']['package_sha256'] ==
                             expected['package_sha256'],
                             'excel_selection_task_paid_or_result_changed')
                    ledger.append('task_completed', {
                        'task_index': task_index,
                        'task_receipt_sha256':
                            completed['task_receipt_sha256'],
                        'result_row': completed['result_row'],
                        'paid_attempt_ids':
                            completed['paid_attempt_ids'],
                    })
                    result_rows.append(completed['result_row'])
            _require(len(result_rows) == MAX_TASKS and
                     len(set(paid_ids)) == len(paid_ids),
                     'excel_selection_twenty_task_or_paid_coverage_missing')
            result = {
                'schema': 'cua-full-study-selection-saved-result-v1',
                'cell_id': 'excel-web',
                'checkpoint_sha256':
                    self.started['checkpoint_path_sha256'],
                'evaluator_isolated': True,
                'tasks': result_rows,
            }
            scored = self.session.record_selection_scored(
                attempt_id=self.started['attempt_id'], result=result,
                paid_attempt_ids=paid_ids)
            scored_recorded = True
            ledger.append('selection_scored', {
                'result_sha256': _sha(_canonical(result)),
                'paid_attempt_ids_sha256': _sha(_canonical(paid_ids)),
            })
            return {'result': result, 'campaign_result': scored,
                    'task_ledger_sha256':
                        _sha((self.out_dir /
                              'tasks.private.jsonl').read_bytes())}
        except Exception as exc:
            # A paid intent can exist even if the callback never produced a
            # result or our validation rejected it. Preserve every related
            # intent in the invalid receipt; never silently retry it.
            related_paid_ids = [
                row['data']['attempt_id'] for row in
                self.session._events('paid_intent')
                if row['data']['attempt_id'].startswith(
                    self.started['attempt_id'] + '-')]
            if scored_recorded:
                # Campaign scoring is already durable. A local ledger append
                # failure cannot change that score into an invalid attempt.
                raise
            failure_type = ('provider' if isinstance(
                exc, ExcelSelectionProviderUncertain) else
                'environment' if isinstance(
                    exc, (boundary.ExcelSelectionBoundaryError,
                          ExcelSelectionError)) else 'verifier')
            failure = {
                'schema': 'cua-office-excel-selection-invalid-v1',
                'selection_attempt': self.started['attempt_id'],
                'failure_type': failure_type,
                'exception_type': type(exc).__name__,
                'reason_code': str(exc)[:512],
                'task_ledger_sha256':
                    _sha((self.out_dir /
                          'tasks.private.jsonl').read_bytes()),
                'paid_attempt_ids': related_paid_ids,
            }
            failure_path = self.out_dir / 'invalid.private.json'
            if not failure_path.exists():
                failure_sha = _write_new(failure_path,
                                         _canonical(failure))
                self.session.record_selection_invalid(
                    attempt_id=self.started['attempt_id'],
                    failure_type=failure_type,
                    evaluator_receipt_sha256=failure_sha)
            raise
        finally:
            if sampler_delegate is not None:
                sampler_delegate.close(success=len(result_rows) == MAX_TASKS)


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
    """Freeze one private SEC selection binding; performs no paid call."""
    root = Path(session.study.repo_root).resolve() / 'work'
    target = Path(out_path).absolute()
    _require(target.parent.resolve().is_relative_to(root) and
             not target.exists() and not target.is_symlink() and
             {key: task[key] for key in
              ('task_id', 'package_sha256')} in
             list(session.views['selection']),
             'excel_selection_binding_target_or_roster_invalid')
    source = boundary.validate_package(task_path, root, task)
    case_raw = _private_bytes(cases_path, root, 'selection_cases', 8_000_000)
    reference_raw = _private_bytes(reference_path, root,
                                   'selection_reference')
    from tools.sec_excel_web_selection_oracle_v1 import one_selection_case
    one_selection_case(cases_path, case_id)
    _item(actor_item, 'actor')
    _item(reset_item, 'reset')
    rat_path = Path(session.study.ratification_path)
    _require(rat_path.is_file() and not rat_path.is_symlink(),
             'excel_selection_ratification_missing')
    cell = next(row for row in session.study.plan['cells'] if
                row['cell_id'] == 'excel-web')
    binding = {
        'schema': BINDING_SCHEMA, 'split': 'selection',
        'workflow': 'sec-integrated', 'cell_id': 'excel-web',
        'task_id': task['task_id'],
        'package_sha256': task['package_sha256'],
        'visible_instruction': task['visible_instruction'],
        'task_path': str(Path(task_path).absolute()),
        'task_file_sha256': source['task_sha256'],
        'actor_seed_sha256': source['actor_sha256'],
        'cases_path': str(Path(cases_path).absolute()),
        'cases_sha256': _sha(case_raw), 'case_id': case_id,
        'reference_path': str(Path(reference_path).absolute()),
        'reference_sha256': _sha(reference_raw),
        'actor_item': actor_item, 'reset_item': reset_item,
        'owner_email_sha256': _sha(owner_email.casefold()),
        'actor_email_sha256': _sha(actor_email.casefold()),
        'ratification_sha256':
            session.study.ratification_sha256,
        'frozen_adapter_sha256':
            train_worker.adapter_bundle_sha256(),
        'worker_runtime_sha256': runtime_sha256(),
        'verifier_sha256': cell['matched_bindings']['verifier'],
        'lease_seconds': lease_seconds, 'max_steps': max_steps,
        'wall_seconds': wall_seconds,
        'manual_wait_seconds': manual_wait_seconds,
        'post_finish_wait_seconds': post_finish_wait_seconds,
        'e2b_reserve_usd': e2b_reserve_usd,
        'graph_read_reserve_usd': graph_read_reserve_usd,
    }
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = _canonical(binding)
    sha = _write_new(target, raw)
    worker = SelectionExcelTaskWorker(
        session, target, oracle_runner=oracle_runner)
    worker._binding({key: task[key] for key in (
        'task_id', 'package_sha256')})
    return {'binding_path': str(target), 'binding_sha256': sha}


def prepare_private_manifest(session, started: dict,
                             checkpoint_path: str,
                             bindings: list[dict], out_path: Path) -> dict:
    """Bind exactly 20 existing private bindings to the campaign start."""
    _started(session, started, checkpoint_path)
    root = Path(session.study.repo_root).resolve() / 'work'
    target = Path(out_path).absolute()
    _require(target.parent.resolve().is_relative_to(root) and
             not target.exists() and not target.is_symlink() and
             type(bindings) is list and len(bindings) == MAX_TASKS,
             'excel_selection_manifest_target_or_size_invalid')
    entries = []
    for task, reference in zip(started['selection_tasks'], bindings):
        _require(type(reference) is dict and
                 set(reference) == {'binding_path', 'binding_sha256'} and
                 type(reference['binding_sha256']) is str and
                 _HEX.fullmatch(reference['binding_sha256']) and
                 _sha(_private_bytes(Path(reference['binding_path']),
                                     root, 'selection_binding')) ==
                 reference['binding_sha256'],
                 'excel_selection_binding_reference_invalid')
        entries.append({**task, **reference})
    manifest = {
        'schema': BATCH_SCHEMA, 'cell_id': 'excel-web',
        'split': 'selection',
        'selection_attempt': started['attempt_id'],
        'selection_identities_sha256':
            started['selection_identities_sha256'],
        'checkpoint_path_sha256':
            started['checkpoint_path_sha256'],
        'worker_runtime_sha256': runtime_sha256(),
        'tasks': entries,
    }
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    sha = _write_new(target, _canonical(manifest))
    return {'manifest_path': str(target), 'manifest_sha256': sha}
