"""Train-only, screenshot-bound Excel for the web actor on a manual-login E2B desktop.

This is an original-application transport pilot, not a final-task admission or
score. The actor receives only a current screenshot and train instruction. A
saved workbook is unqualified until a separately audited GUI download binds
the cloud item, source seed, and independent Excel oracle.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import parse_qsl, urlsplit
import zipfile
import xml.etree.ElementTree as ET

from cursibench.scale_action_contract import (
    ContractError, ContractLimits, Observation, make_observation,
    validate_action,
)
from cursibench.scale_action_output_v065 import (
    normalize_model_action, render_for_model,
)
from cursibench.scale_vision_proxy import (
    Limits as VisionLimits, MODEL, QwenVisionRenderer,
    TinkerVisionBackend, VisionSamplingAdapter, campaign_metadata,
    public_receipt as vision_receipt,
)
from tools import office_web_e2b_login_bridge_v1 as bridge
from tools import office_web_e2b_train_runner_v1 as office
from tools import office_web_actor_scope_gate_v1 as actor_scope
from tools.excel_web_ooxml import read_workbook


VERSION = 'excel-web-e2b-train-runner-v1'
TASK_SCHEMA = 'excel-web-original-train-package-v1'
CONFIG_SCHEMA = 'excel-web-e2b-train-run-private-v1'
MAX_STEPS = 90
MAX_WALL_SECONDS = 1800
MAX_XLSX_BYTES = 50_000_000
MIN_LEASE_REMAINDER = 60
_TASK_ID = re.compile(r'xl-train-[0-9a-f]{16}\Z')
_SANDBOX_ID = re.compile(r'[A-Za-z0-9_-]{8,128}\Z')
_ONEDRIVE_DOC = re.compile(
    r'/personal/[0-9A-Fa-f]{16}/_layouts/15/Doc\.aspx\Z')
_SOURCE_DOC = re.compile(
    r'\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}\Z')
_TRAIN_FILE = re.compile(r'EL-Excel-Train-[A-Za-z0-9._-]{1,100}\.xlsx\Z')
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')


class RunnerError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RunnerError(code)


def digest(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def private_root() -> Path:
    return (Path.cwd() / 'work').resolve()


def private_file(path: Path, *, name: str | None = None,
                 maximum: int = 2_000_000) -> bytes:
    path = Path(path).absolute()
    try:
        size = path.stat().st_size
        mode = path.stat().st_mode & 0o777
    except OSError:
        raise RunnerError('private_file_required') from None
    require(path.is_relative_to(private_root()) and
            (name is None or path.name == name) and
            not path.is_symlink() and path.is_file() and
            mode == 0o600 and size <= maximum,
            'private_file_required')
    for parent in (path.parent, *path.parents):
        if parent == private_root().parent:
            break
        require(not parent.is_symlink(), 'private_file_required')
    return path.read_bytes()


def load_json(raw: bytes, code: str) -> dict:
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RunnerError(code) from None
    require(type(result) is dict, code)
    return result


def readback_xlsx(raw: bytes) -> dict:
    """Check the package shape only; no calculation, provenance, or score."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_XLSX_BYTES,
            'invalid_saved_xlsx')
    try:
        workbook = read_workbook(raw)
        members = workbook['members']
        sheets = workbook['sheets']
        require('[Content_Types].xml' in members and
                'xl/workbook.xml' in members and
                'xl/_rels/workbook.xml.rels' in members and
                1 <= len(sheets) <= 100 and
                all(sheet['path'] in members for sheet in sheets.values()),
                'invalid_saved_xlsx')
        formula_count = sum(
            cell['formula'] is not None
            for sheet in sheets.values() for cell in sheet['cells'].values())
    except (KeyError, OSError, ValueError, TypeError, IndexError, RuntimeError,
            zipfile.BadZipFile, zipfile.LargeZipFile, ET.ParseError):
        raise RunnerError('invalid_saved_xlsx') from None
    return {'sha256': digest(raw), 'bytes': len(raw),
            'sheet_count': len(sheets), 'formula_count': formula_count,
            'status': 'package_readback_only_unscored'}


def validate_train_workbook_url(url: object) -> str:
    """Constrain navigation to a manually asserted train cloud item.

    A matching URL is not proof that the cloud item contains the actor seed.
    """
    require(type(url) is str and len(url) <= 2048,
            'invalid_train_workbook_url')
    try:
        parsed = urlsplit(url)
        hostname, port = parsed.hostname, parsed.port
    except ValueError:
        raise RunnerError('invalid_train_workbook_url') from None
    require(parsed.scheme == 'https' and
            hostname == 'onedrive.live.com' and
            parsed.username is None and parsed.password is None and
            port is None and not parsed.fragment and
            _ONEDRIVE_DOC.fullmatch(parsed.path) is not None,
            'invalid_train_workbook_url')
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(pairs)
    require(len(pairs) == len(query) and
            set(query) in ({'sourcedoc', 'file', 'action'},
                           {'sourcedoc', 'file', 'action', 'mobileredirect'}) and
            _SOURCE_DOC.fullmatch(query['sourcedoc']) is not None and
            _TRAIN_FILE.fullmatch(query['file']) is not None and
            not any(token in query['file'].lower()
                    for token in ('final', 'official')) and
            query['action'] in ('default', 'edit') and
            query.get('mobileredirect') in (None, 'true'),
            'invalid_train_workbook_url')
    return url


@dataclass(frozen=True)
class Admission:
    session_path: Path
    session_sha256: str
    sandbox_id: str
    template_id: str
    task_id: str
    instruction: str
    task_sha256: str
    actor_sha256: str
    workbook_url: str
    workbook_url_sha256: str
    max_steps: int
    wall_seconds: int
    lease_end_unix: int
    actor_scope_receipt_sha256: str


@dataclass(frozen=True)
class TrainPackage:
    task_id: str
    instruction: str
    task_sha256: str
    actor_sha256: str


def validate_train_package(task_path: Path) -> TrainPackage:
    """Offline preflight with no cloud session or provider dependency."""
    task_path = Path(task_path).absolute()
    parts = task_path.parts
    require(task_path.is_relative_to(private_root()) and
            task_path.name == 'task.private.json' and
            any(parts[i:i + 2] == ('packages', 'train')
                for i in range(len(parts) - 1)) and
            not any('final' in part.lower() or 'official' in part.lower()
                    for part in parts),
            'train_package_path_required')
    task_raw = private_file(task_path, name='task.private.json')
    task = load_json(task_raw, 'invalid_train_package')
    require(set(task) == {'schema', 'split', 'official_final_credit',
                          'task_id', 'actor_task', 'actor_xlsx_sha256'} and
            task['schema'] == TASK_SCHEMA and task['split'] == 'train' and
            type(task['official_final_credit']) is int and
            task['official_final_credit'] == 0 and
            isinstance(task['task_id'], str) and
            _TASK_ID.fullmatch(task['task_id']) is not None and
            task_path.parent.name == task['task_id'] and
            type(task['actor_task']) is str and
            0 < len(task['actor_task'].encode()) <= 8192 and
            isinstance(task['actor_xlsx_sha256'], str) and
            _HEX64.fullmatch(task['actor_xlsx_sha256']) is not None,
            'invalid_train_package')
    actor_raw = private_file(task_path.parent / 'actor.xlsx',
                             name='actor.xlsx', maximum=MAX_XLSX_BYTES)
    require(digest(actor_raw) == task['actor_xlsx_sha256'],
            'actor_seed_hash_mismatch')
    readback_xlsx(actor_raw)
    return TrainPackage(task['task_id'], task['actor_task'],
                        digest(task_raw), digest(actor_raw))


def admit(session_path: Path, task_path: Path, config_path: Path,
          out: Path, *, now: int | None = None) -> Admission:
    """Reject hidden-final paths and data before any provider connection."""
    now = int(time.time()) if now is None else now
    task = validate_train_package(task_path)
    out = Path(out).absolute()
    require(out.is_relative_to(private_root()) and not out.exists() and
            not out.is_symlink() and
            out.parent.resolve().is_relative_to(private_root()),
            'fresh_private_output_required')
    session_path = Path(session_path).absolute()
    session_raw = private_file(session_path, name='session.private.json')
    require(not (session_path.parent / 'stop.private.json').exists(),
            'session_already_stopped')
    session = load_json(session_raw, 'invalid_login_receipt')
    require(session.get('schema') == bridge.SCHEMA and
            session.get('status') == 'awaiting_manual_login' and
            session.get('task_split') == 'train_only' and
            session.get('account_login') == 'manual_only' and
            session.get('credential_or_cookie_injection') is False and
            session.get('credential_snapshot_or_export') is False and
            type(session.get('official_final_admitted')) is int and
            session['official_final_admitted'] == 0 and
            type(session.get('model_calls')) is int and
            session['model_calls'] == 0 and
            session.get('sdk_version') == '2.2.0' and
            session.get('expected_template_id') == bridge.EXPECTED_TEMPLATE_ID and
            session.get('observed_template_id') == bridge.EXPECTED_TEMPLATE_ID and
            type(session.get('lease_started_at_unix')) is int and
            type(session.get('lease_seconds')) is int and
            300 <= session['lease_seconds'] <= 3600 and
            isinstance(session.get('sandbox_id'), str) and
            _SANDBOX_ID.fullmatch(session['sandbox_id']) is not None,
            'invalid_login_receipt')
    try:
        bridge.validate_stream(session['stream_url'],
                               session['stream_auth_key'])
    except (KeyError, ValueError):
        raise RunnerError('invalid_login_receipt') from None
    lease_end = session['lease_started_at_unix'] + session['lease_seconds']
    require(lease_end - now >= MIN_LEASE_REMAINDER,
            'lease_expired_or_too_short')
    config = load_json(private_file(config_path, name='run.private.json'),
                       'invalid_run_config')
    require(set(config) == {'schema', 'split', 'manual_login_confirmed_at_unix',
                            'workbook_url', 'max_steps', 'wall_seconds'} and
            config['schema'] == CONFIG_SCHEMA and config['split'] == 'train' and
            type(config['manual_login_confirmed_at_unix']) is int and
            session['lease_started_at_unix'] <=
            config['manual_login_confirmed_at_unix'] <= now and
            type(config['max_steps']) is int and
            1 <= config['max_steps'] <= MAX_STEPS and
            type(config['wall_seconds']) is int and
            1 <= config['wall_seconds'] <= MAX_WALL_SECONDS and
            config['wall_seconds'] + MIN_LEASE_REMAINDER <= lease_end - now,
            'invalid_run_config')
    url = validate_train_workbook_url(config['workbook_url'])
    try:
        scope = actor_scope.validate(
            session_path.parent / 'actor-scope.private.json',
            session_raw=session_raw, sandbox_id=session['sandbox_id'],
            item_url=url, app='excel',
            lease_started_at_unix=session['lease_started_at_unix'],
            lease_end_unix=lease_end, actor_seed_sha256=task.actor_sha256,
            now=now)
    except actor_scope.ScopeError:
        raise RunnerError('actor_scope_unverified') from None
    return Admission(session_path, digest(session_raw), session['sandbox_id'],
                     bridge.EXPECTED_TEMPLATE_ID, task.task_id,
                     task.instruction, task.task_sha256, task.actor_sha256,
                     url, digest(url), config['max_steps'],
                     config['wall_seconds'], lease_end,
                     scope['receipt_sha256'])


class EventJournal:
    """Append-only private intent/result journal without task text or URL."""

    def __init__(self, root: Path):
        self.path = root / 'events.private.jsonl'
        self.sequence = 0

    def record(self, event: str, **fields) -> None:
        self.sequence += 1
        row = {'version': VERSION, 'sequence': self.sequence,
               'at_unix': int(time.time()), 'event': event, **fields}
        raw = (json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def write_new_bytes(path: Path, payload: bytes) -> None:
    """Keep raw screen evidence private and immutable for later provenance QA."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def capture_excel_observation(sandbox, admission: Admission, *, step: int,
                              memory: str,
                              previous_action_result: dict | None) -> Observation:
    """The screenshot is the only live Excel UI modality in this desktop pilot."""
    frame = bytes(sandbox.screenshot())
    return make_observation(
        task_id=admission.task_id,
        task_binding_sha256=admission.task_sha256,
        instruction=admission.instruction, step=step,
        screenshot_bytes=frame, a11y_text='', dom_text='', controls=(),
        memory=memory, previous_action_result=previous_action_result,
        limits=ContractLimits(max_step=admission.max_steps,
                              frame_ttl_seconds=150),
    )


def dispatch_excel_action(sandbox, action: dict,
                          observation: Observation) -> None:
    """Revalidate and dispatch a coordinate-only GUI action on this exact frame."""
    validate_action(action, observation,
                    current_frame_id=observation.frame_id)
    for key in ('target', 'from', 'to'):
        require(key not in action or set(action[key]) == {'x', 'y'},
                'coordinate_target_required')
    frame = bytes(sandbox.screenshot())
    require(digest(frame) == observation.screenshot['sha256'],
            'frame_changed_during_sampling')
    require(time.monotonic() <= observation.expires_at,
            'frame_or_lease_expired')
    office.dispatch(sandbox, action)


class ArtifactUnavailable(RunnerError):
    pass


class UnqualifiedExcelDownload:
    def retrieve(self, _sandbox, _admission: Admission) -> bytes:
        raise ArtifactUnavailable('excel_download_not_qualified')


def make_tinker_sampler(journal_path: Path, max_steps: int):
    require(bool(os.environ.get('TINKER_API_KEY')),
            'tinker_host_key_required')
    import tinker
    service = tinker.ServiceClient(user_metadata=campaign_metadata(
        'excel-web-e2b-train-pilot-v1'))
    try:
        renderer = QwenVisionRenderer.load()
        backend = TinkerVisionBackend.from_service(
            service, renderer, checkpoint=os.environ.get('TINKER_SAMPLER_PATH'))
        sampler = VisionSamplingAdapter(
            backend, journal_path,
            limits=VisionLimits(max_actions=max_steps,
                                request_timeout_seconds=120))
        return sampler, service
    except BaseException:
        service.close('errored').result(timeout=30)
        raise


def _stop_session(admission: Admission, sandbox_factory, samples: int) -> str:
    try:
        killed = sandbox_factory.kill(admission.sandbox_id)
    except Exception:
        killed = False
    status = 'killed' if killed else 'termination_unconfirmed'
    receipt = {
        'schema': bridge.SCHEMA, 'status': status,
        'sandbox_id_sha256': digest(admission.sandbox_id),
        'session_sha256': admission.session_sha256,
        'terminated_at_unix': int(time.time()),
        'model_calls': samples, 'official_final_admitted': 0,
    }
    try:
        bridge.write_new(admission.session_path.parent / 'stop.private.json',
                         receipt)
    except FileExistsError:
        status += '_stop_receipt_already_exists'
    except Exception:
        status += '_stop_receipt_failed'
    return status


def run(session_path: Path, task_path: Path, config_path: Path, out: Path,
        sandbox_factory, sampler_factory=make_tinker_sampler,
        artifact_retriever=None) -> dict:
    admission = admit(session_path, task_path, config_path, out)
    require(bool(os.environ.get('E2B_API_KEY')), 'e2b_host_key_required')
    out = Path(out).absolute()
    out.mkdir(parents=True, mode=0o700)
    out.chmod(0o700)
    journal = EventJournal(out)
    bridge.write_new(out / 'admission.private.json', {
        'version': VERSION, 'task_id_sha256': digest(admission.task_id),
        'task_package_sha256': admission.task_sha256,
        'actor_seed_sha256': admission.actor_sha256,
        'workbook_url_sha256': admission.workbook_url_sha256,
        'login_receipt_sha256': admission.session_sha256,
        'actor_scope_receipt_sha256': admission.actor_scope_receipt_sha256,
        'model': MODEL, 'action_version': 'scale-action-output-v0.6.5',
        'max_steps': admission.max_steps,
        'wall_seconds': admission.wall_seconds,
        'cloud_seed_binding_qualified': False,
        'official_final_admitted': 0,
    })
    sandbox = None
    connect_attempted = False
    service = None
    status = 'setup_failed'
    samples = 0
    actions = 0
    artifact = None
    started = time.monotonic()
    journal.record('trusted_setup_intent',
                   sandbox_id_sha256=digest(admission.sandbox_id),
                   workbook_url_sha256=admission.workbook_url_sha256)
    try:
        connect_attempted = True
        # Do not pass timeout: a reconnect must not extend the human-login lease.
        sandbox = sandbox_factory.connect(admission.sandbox_id)
        require(sandbox.sandbox_id == admission.sandbox_id,
                'desktop_identity_mismatch')
        info = sandbox.get_info(request_timeout=12)
        require(info.template_id == admission.template_id,
                'desktop_template_drift')
        sandbox.launch('google-chrome', uri=admission.workbook_url)
        journal.record('trusted_setup_complete',
                       template_id=admission.template_id,
                       workbook_url_sha256=admission.workbook_url_sha256)
        sampler, service = sampler_factory(out / 'proxy', admission.max_steps)
        require(getattr(sampler, 'binding', {}).get('backend', {}).get('model')
                == MODEL, 'wrong_vision_model')
        memory = ''
        previous = None
        for step in range(admission.max_steps):
            require(time.monotonic() - started <= admission.wall_seconds,
                    'wall_budget_exhausted')
            observation = capture_excel_observation(
                sandbox, admission, step=step, memory=memory,
                previous_action_result=previous)
            write_new_bytes(out / f'frame-{step:03d}.private.png',
                            observation.screenshot_bytes)
            bridge.write_new(out / f'frame-{step:03d}.private.json', {
                'frame_id_sha256': digest(observation.frame_id),
                'screenshot_sha256': observation.screenshot['sha256'],
                'width': observation.screenshot['width'],
                'height': observation.screenshot['height'],
                'screenshot_file': f'frame-{step:03d}.private.png',
            })
            request = render_for_model(observation)
            request_id = f'excelweb-{secrets.token_hex(12)}-{step:03d}'
            journal.record('model_request_intent', step=step,
                           request_id=request_id,
                           frame_id_sha256=digest(observation.frame_id),
                           screenshot_sha256=observation.screenshot['sha256'])
            result = sampler.sample(request_id=request_id, **request)
            samples += 1
            journal.record('model_request_result', step=step,
                           request_id=request_id,
                           receipt=vision_receipt(result))
            require(result.get('status') == 'completed' and
                    type(result.get('text')) is str,
                    'sampling_failed')
            action = normalize_model_action(
                result['text'], observation,
                current_frame_id=observation.frame_id)
            current_frame = bytes(sandbox.screenshot())
            require(digest(current_frame) == observation.screenshot['sha256'],
                    'frame_changed_during_sampling')
            require(time.monotonic() - started <= admission.wall_seconds and
                    int(time.time()) < admission.lease_end_unix,
                    'frame_or_lease_expired')
            journal.record('gui_action_intent', step=step,
                           action=office.action_receipt(action),
                           frame_id_sha256=digest(observation.frame_id))
            if action['type'] == 'finish':
                journal.record('gui_action_result', step=step,
                               status='finished_no_dispatch')
                status = 'artifact_gate_blocked'
                retriever = artifact_retriever or UnqualifiedExcelDownload()
                journal.record('artifact_download_intent', step=step)
                try:
                    downloaded = retriever.retrieve(sandbox, admission)
                    artifact = readback_xlsx(downloaded)
                    status = 'artifact_readback_unscored'
                    journal.record('artifact_readback_result', **artifact)
                except ArtifactUnavailable as error:
                    journal.record('artifact_download_blocked', code=error.code)
                break
            try:
                dispatch_excel_action(sandbox, action, observation)
            except BaseException:
                journal.record('gui_action_result', step=step,
                               status='dispatch_uncertain')
                raise
            actions += 1
            memory = action['memory']
            previous = {'status': 'applied', 'code': 'ok'}
            journal.record('gui_action_result', step=step, status='applied')
        else:
            status = 'action_budget_exhausted'
    except (RunnerError, ContractError) as error:
        status = error.code
        journal.record('runner_error', code=status)
    except BaseException as error:
        status = 'provider_or_desktop_error'
        journal.record('runner_error', code=status,
                       error_type=type(error).__name__)
    finally:
        if service is not None:
            try:
                service.close('success' if status.startswith('artifact_')
                              else 'errored').result(timeout=30)
            except Exception:
                journal.record('sampler_close_error')
        teardown = 'not_connected'
        if connect_attempted:
            teardown = _stop_session(admission, sandbox_factory, samples)
        journal.record('teardown_result', status=teardown)
        receipt = {
            'version': VERSION, 'status': status,
            'teardown': teardown,
            'task_id_sha256': digest(admission.task_id),
            'task_package_sha256': admission.task_sha256,
            'actor_seed_sha256': admission.actor_sha256,
            'workbook_url_sha256': admission.workbook_url_sha256,
            'actor_scope_receipt_sha256': admission.actor_scope_receipt_sha256,
            'model': MODEL, 'samples': samples,
            'gui_actions': actions, 'artifact': artifact,
            'cloud_seed_binding_qualified': False,
            'official_final_admitted': 0,
            'provider_billed_usd': None,
        }
        bridge.write_new(out / 'result.private.json', receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-package', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--session', type=Path)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.check_package:
        package = validate_train_package(args.task)
        print(json.dumps({
            'version': VERSION, 'status': 'train_package_validated_offline',
            'task_id_sha256': digest(package.task_id),
            'task_package_sha256': package.task_sha256,
            'actor_seed_sha256': package.actor_sha256,
            'provider_calls': 0, 'official_final_admitted': 0,
        }, sort_keys=True))
        return
    require(args.session is not None and args.config is not None and
            args.out is not None, 'session_config_output_required')
    admission = admit(args.session, args.task, args.config, args.out)
    if args.dry_run:
        print(json.dumps({
            'version': VERSION, 'status': 'admitted_no_provider_call',
            'task_id_sha256': digest(admission.task_id),
            'actor_seed_sha256': admission.actor_sha256,
            'workbook_url_sha256': admission.workbook_url_sha256,
            'actor_scope_receipt_sha256': admission.actor_scope_receipt_sha256,
            'max_steps': admission.max_steps,
            'wall_seconds': admission.wall_seconds,
            'cloud_seed_binding_qualified': False,
            'official_final_admitted': 0,
        }, sort_keys=True))
        return
    from e2b_desktop import Sandbox
    require(importlib.metadata.version('e2b-desktop') == '2.2.0',
            'desktop_sdk_version_drift')
    result = run(args.session, args.task, args.config,
                 args.out, Sandbox)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
