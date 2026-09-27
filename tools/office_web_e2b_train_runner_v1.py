"""Bounded, train-only PowerPoint web actor on a manually signed-in E2B Desktop.

The login bridge owns sandbox creation and the human sign-in. This runner
reconnects without renewing the lease, sends only current screenshots and the
train actor instruction to the shared Qwen vision proxy, and dispatches only
v0.6.5-validated desktop actions. The production artifact gate deliberately
fails closed until a live, source-bound Office download is qualified.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit
import zipfile
import xml.etree.ElementTree as ET

from cursibench.scale_action_contract import ContractError, ContractLimits, make_observation
from cursibench.scale_action_output_v065 import normalize_model_action, render_for_model
from cursibench.scale_vision_proxy import (
    Limits as VisionLimits, MODEL, QwenVisionRenderer, TinkerVisionBackend,
    VisionSamplingAdapter, campaign_metadata, public_receipt,
)
from tools import office_web_e2b_login_bridge_v1 as bridge


VERSION = 'office-web-e2b-train-runner-v1'
CONFIG_SCHEMA = 'office-web-e2b-train-run-private-v1'
TASK_SCHEMA = 'ppt-wdi-original-candidates-v1'
MAX_STEPS = 20
MAX_WALL_SECONDS = 600
MIN_LEASE_REMAINDER = 60
MAX_TASK_BYTES = 2_000_000
MAX_PPTX_BYTES = 50_000_000
_TASK_ID = re.compile(r'ppt-wdi-[a-z0-9]{16}\Z')
_SANDBOX_ID = re.compile(r'[A-Za-z0-9_-]{8,128}\Z')


class RunnerError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def digest(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RunnerError(code)


def private_root() -> Path:
    return (Path.cwd() / 'work').resolve()


def private_file(path: Path, *, name: str | None = None) -> bytes:
    path = Path(path).absolute()
    require(path.is_relative_to(private_root()) and
            (name is None or path.name == name) and
            not path.is_symlink() and path.is_file() and
            path.stat().st_mode & 0o777 == 0o600,
            'private_file_required')
    for parent in (path.parent, *path.parents):
        if parent == private_root().parent:
            break
        require(not parent.is_symlink(), 'private_file_required')
    raw = path.read_bytes()
    require(len(raw) <= MAX_TASK_BYTES, 'private_file_too_large')
    return raw


def load_json(raw: bytes, code: str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RunnerError(code) from None
    require(type(data) is dict, code)
    return data


@dataclass(frozen=True)
class Admission:
    session_path: Path
    session_sha256: str
    sandbox_id: str
    template_id: str
    task_id: str
    instruction: str
    task_sha256: str
    deck_url: str
    deck_url_sha256: str
    max_steps: int
    wall_seconds: int
    lease_end_unix: int


def admit(session_path: Path, task_path: Path, config_path: Path,
          out: Path, *, now: int | None = None) -> Admission:
    """Reject non-train packages before reading their contents or calling E2B."""
    now = int(time.time()) if now is None else now
    task_path = Path(task_path).absolute()
    out = Path(out).absolute()
    parts = task_path.parts
    require(task_path.is_relative_to(private_root()) and
            task_path.name == 'task.private.json' and
            any(parts[i:i+2] == ('packages', 'train') for i in range(len(parts)-1)) and
            not any('final' in part.lower() or 'official' in part.lower()
                    for part in parts), 'train_package_path_required')
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
            session.get('official_final_admitted') == 0 and
            session.get('model_calls') == 0 and
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
                            'deck_url', 'max_steps', 'wall_seconds'} and
            config['schema'] == CONFIG_SCHEMA and config['split'] == 'train' and
            type(config['manual_login_confirmed_at_unix']) is int and
            session['lease_started_at_unix'] <= config['manual_login_confirmed_at_unix'] <= now and
            type(config['max_steps']) is int and 1 <= config['max_steps'] <= MAX_STEPS and
            type(config['wall_seconds']) is int and
            1 <= config['wall_seconds'] <= MAX_WALL_SECONDS and
            config['wall_seconds'] + MIN_LEASE_REMAINDER <= lease_end - now,
            'invalid_run_config')
    url = config['deck_url']
    require(type(url) is str and len(url) <= 2048, 'invalid_train_deck_url')
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and
            parsed.hostname == 'powerpoint.cloud.microsoft' and
            parsed.username is None and parsed.password is None and
            parsed.port is None and not parsed.fragment and
            parsed.path.startswith('/') and parsed.path != '/' and
            'signin' not in parsed.path.lower(),
            'invalid_train_deck_url')
    task_raw = private_file(task_path, name='task.private.json')
    task = load_json(task_raw, 'invalid_train_package')
    require(task.get('schema') == TASK_SCHEMA and task.get('split') == 'train' and
            type(task.get('official_final_credit')) is int and
            task['official_final_credit'] == 0 and
            isinstance(task.get('task_id'), str) and
            _TASK_ID.fullmatch(task['task_id']) is not None and
            task_path.parent.name == task['task_id'] and
            type(task.get('actor_task')) is str and
            0 < len(task['actor_task'].encode()) <= 8192,
            'invalid_train_package')
    return Admission(session_path, digest(session_raw), session['sandbox_id'],
                     bridge.EXPECTED_TEMPLATE_ID, task['task_id'],
                     task['actor_task'], digest(task_raw), url, digest(url),
                     config['max_steps'], config['wall_seconds'], lease_end)


class EventJournal:
    """Private append-only intent/result log; never writes URL, typed text, or key."""

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


def action_receipt(action: dict) -> dict:
    row = {'type': action['type'], 'action_sha256': digest(json.dumps(
        action, sort_keys=True, separators=(',', ':')))}
    for key in ('target', 'from', 'to'):
        if key in action:
            row[key] = action[key]
    if action['type'] == 'type':
        row['text_sha256'] = digest(action['text'])
        row['text_bytes'] = len(action['text'].encode())
        row['mode'] = action['mode']
    if action['type'] == 'key':
        row['key'] = action['key']
    if action['type'] == 'scroll':
        row['dx'], row['dy'] = action['dx'], action['dy']
    if action['type'] == 'wait':
        row['duration_ms'] = action['duration_ms']
    return row


_KEYS = {
    'Enter': 'enter', 'Tab': 'tab', 'Shift+Tab': ['shift', 'tab'],
    'Escape': 'escape', 'Backspace': 'backspace', 'Delete': 'delete',
    'Space': 'space', 'ArrowUp': 'up', 'ArrowDown': 'down',
    'ArrowLeft': 'left', 'ArrowRight': 'right', 'Home': 'home',
    'End': 'end', 'PageUp': 'page_up', 'PageDown': 'page_down',
    'Control+A': ['ctrl', 'a'], 'Control+S': ['ctrl', 's'],
}


def point(target: dict) -> tuple[int, int]:
    require(set(target) == {'x', 'y'}, 'coordinate_target_required')
    return target['x'], target['y']


def click_point(sandbox, target: dict) -> None:
    # e2b-desktop 2.2.0's left_click(x,y) treats zero as false. Move first.
    sandbox.move_mouse(*point(target))
    sandbox.left_click()


def dispatch(sandbox, action: dict) -> None:
    kind = action['type']
    if kind == 'click':
        click_point(sandbox, action['target'])
    elif kind == 'type':
        click_point(sandbox, action['target'])
        if action['mode'] == 'fill':
            sandbox.press(['ctrl', 'a'])
        sandbox.write(action['text'])
    elif kind == 'key':
        require(action['key'] in _KEYS, 'unsupported_desktop_key')
        if 'target' in action:
            click_point(sandbox, action['target'])
        sandbox.press(_KEYS[action['key']])
    elif kind == 'scroll':
        require(action['dx'] == 0, 'horizontal_scroll_unavailable')
        if 'target' in action:
            sandbox.move_mouse(*point(action['target']))
        direction = 'down' if action['dy'] > 0 else 'up'
        amount = max(1, (abs(action['dy']) + 119) // 120)
        sandbox.scroll(direction=direction, amount=amount)
    elif kind == 'drag':
        sandbox.drag(point(action['from']), point(action['to']))
    elif kind == 'wait':
        time.sleep(action['duration_ms'] / 1000)
    elif kind == 'finish':
        return
    else:
        raise RunnerError('unsupported_desktop_action')


class ArtifactUnavailable(RunnerError):
    pass


class UnqualifiedOfficeDownload:
    """No guessed browser path or direct authenticated URL fetch is accepted."""

    def retrieve(self, _sandbox, _admission: Admission) -> bytes:
        raise ArtifactUnavailable('office_download_not_qualified')


def readback_pptx(raw: bytes) -> dict:
    """Independent package sanity check; a task-specific oracle is still needed."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_PPTX_BYTES,
            'invalid_saved_pptx')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            infos = package.infolist()
            names = [info.filename for info in infos]
            require(len(names) == len(set(names)) and len(names) <= 10_000 and
                    sum(info.file_size for info in infos) <= 200_000_000 and
                    all(info.file_size <= 50_000_000 and
                        not info.flag_bits & 1 and
                        not name.startswith('/') and '..' not in Path(name).parts
                        for info, name in zip(infos, names)) and
                    '[Content_Types].xml' in names and
                    'ppt/presentation.xml' in names and
                    'ppt/_rels/presentation.xml.rels' in names and
                    any(re.fullmatch(r'ppt/slides/slide\d+\.xml', name)
                        for name in names) and
                    package.testzip() is None,
                    'invalid_saved_pptx')
            ET.fromstring(package.read('ppt/presentation.xml'))
            slides = [name for name in names if
                      re.fullmatch(r'ppt/slides/slide\d+\.xml', name)]
            for name in slides:
                ET.fromstring(package.read(name))
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError):
        raise RunnerError('invalid_saved_pptx') from None
    return {'sha256': digest(raw), 'bytes': len(raw),
            'slide_xml_count': len(slides),
            'status': 'package_readback_only_unscored'}


def make_tinker_sampler(journal_path: Path, max_steps: int):
    """Called only by --run, after train admission and sandbox setup."""
    require(bool(os.environ.get('TINKER_API_KEY')),
            'tinker_host_key_required')
    import tinker
    service = tinker.ServiceClient(user_metadata=campaign_metadata(
        'office-web-e2b-train-pilot-v1'))
    try:
        renderer = QwenVisionRenderer.load()
        backend = TinkerVisionBackend.from_service(
            service, renderer, checkpoint=os.environ.get('TINKER_SAMPLER_PATH'))
        adapter = VisionSamplingAdapter(backend, journal_path,
            limits=VisionLimits(max_actions=max_steps,
                                request_timeout_seconds=120))
        return adapter, service
    except BaseException:
        service.close('errored').result(timeout=30)
        raise


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
        'deck_url_sha256': admission.deck_url_sha256,
        'login_receipt_sha256': admission.session_sha256,
        'model': MODEL, 'action_version': 'scale-action-output-v0.6.5',
        'max_steps': admission.max_steps,
        'wall_seconds': admission.wall_seconds,
        'official_final_admitted': 0,
    })
    sandbox = None
    connect_attempted = False
    service = None
    status = 'setup_failed'
    actions = 0
    samples = 0
    artifact = None
    started = time.monotonic()
    journal.record('trusted_setup_intent',
                   sandbox_id_sha256=digest(admission.sandbox_id),
                   deck_url_sha256=admission.deck_url_sha256)
    try:
        # No timeout argument: reconnect must not renew the human-login lease.
        connect_attempted = True
        sandbox = sandbox_factory.connect(admission.sandbox_id)
        info = sandbox.get_info(request_timeout=12)
        require(info.template_id == admission.template_id,
                'desktop_template_drift')
        sandbox.launch('google-chrome', uri=admission.deck_url)
        journal.record('trusted_setup_complete',
                       template_id=admission.template_id,
                       deck_url_sha256=admission.deck_url_sha256)
        sampler, service = sampler_factory(out / 'proxy', admission.max_steps)
        require(getattr(sampler, 'binding', {}).get('backend', {}).get('model') == MODEL,
                'wrong_vision_model')
        memory = ''
        previous = None
        for step in range(admission.max_steps):
            require(time.monotonic() - started <= admission.wall_seconds,
                    'wall_budget_exhausted')
            raw_frame = bytes(sandbox.screenshot())
            observation = make_observation(
                task_id=admission.task_id,
                task_binding_sha256=admission.task_sha256,
                instruction=admission.instruction, step=step,
                screenshot_bytes=raw_frame, memory=memory,
                previous_action_result=previous,
                limits=ContractLimits(max_step=admission.max_steps,
                                      frame_ttl_seconds=150))
            bridge.write_new(out / f'frame-{step:03d}.private.json', {
                'frame_id_sha256': digest(observation.frame_id),
                'screenshot_sha256': observation.screenshot['sha256'],
                'width': observation.screenshot['width'],
                'height': observation.screenshot['height'],
            })
            request = render_for_model(observation)
            request_id = f'officeweb-{secrets.token_hex(12)}-{step:03d}'
            journal.record('model_request_intent', step=step,
                           request_id=request_id,
                           frame_id_sha256=digest(observation.frame_id),
                           screenshot_sha256=observation.screenshot['sha256'])
            result = sampler.sample(request_id=request_id, **request)
            samples += 1
            journal.record('model_request_result', step=step,
                           request_id=request_id,
                           receipt=public_receipt(result))
            require(result.get('status') == 'completed' and
                    type(result.get('text')) is str,
                    'sampling_failed')
            action = normalize_model_action(
                result['text'], observation,
                current_frame_id=observation.frame_id)
            # A human, browser animation, or async page update may have changed
            # the pixels while the provider sampled. Re-observe before dispatch.
            current_frame = bytes(sandbox.screenshot())
            require(digest(current_frame) == observation.screenshot['sha256'],
                    'frame_changed_during_sampling')
            require(time.monotonic() <= observation.expires_at and
                    time.monotonic() - started <= admission.wall_seconds and
                    int(time.time()) < admission.lease_end_unix,
                    'frame_or_lease_expired')
            journal.record('gui_action_intent', step=step,
                           action=action_receipt(action),
                           frame_id_sha256=digest(observation.frame_id))
            if action['type'] == 'finish':
                journal.record('gui_action_result', step=step,
                               status='finished_no_dispatch')
                status = 'artifact_gate_blocked'
                retriever = artifact_retriever or UnqualifiedOfficeDownload()
                journal.record('artifact_download_intent', step=step)
                try:
                    downloaded = retriever.retrieve(sandbox, admission)
                    artifact = readback_pptx(downloaded)
                    # Package readback is not cloud-item binding or a task score.
                    status = 'artifact_readback_unscored'
                    journal.record('artifact_readback_result', **artifact)
                except ArtifactUnavailable as error:
                    journal.record('artifact_download_blocked', code=error.code)
                break
            try:
                dispatch(sandbox, action)
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
        journal.record('runner_error', code=status, error_type=type(error).__name__)
    finally:
        if service is not None:
            try:
                service.close('success' if status.startswith('artifact_') else 'errored').result(timeout=30)
            except Exception:
                journal.record('sampler_close_error')
        teardown = 'not_connected'
        if connect_attempted:
            try:
                if digest(private_file(admission.session_path)) == admission.session_sha256:
                    stopped = bridge.stop(admission.session_path, sandbox_factory)
                    teardown = stopped['status']
                else:
                    teardown = ('killed_receipt_changed'
                                if sandbox_factory.kill(admission.sandbox_id)
                                else 'termination_unconfirmed')
            except Exception:
                try:
                    teardown = ('killed_bridge_stop_failed'
                                if sandbox_factory.kill(admission.sandbox_id)
                                else 'termination_unconfirmed')
                except Exception:
                    teardown = 'termination_unconfirmed'
        journal.record('teardown_result', status=teardown)
        receipt = {'version': VERSION, 'status': status,
                   'teardown': teardown, 'task_id_sha256': digest(admission.task_id),
                   'task_package_sha256': admission.task_sha256,
                   'deck_url_sha256': admission.deck_url_sha256,
                   'model': MODEL, 'samples': samples, 'gui_actions': actions,
                   'artifact': artifact, 'official_final_admitted': 0,
                   'provider_billed_usd': None}
        bridge.write_new(out / 'result.private.json', receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    admission = admit(args.session, args.task, args.config, args.out)
    if args.dry_run:
        print(json.dumps({'version': VERSION, 'status': 'admitted_no_provider_call',
                          'task_id_sha256': digest(admission.task_id),
                          'deck_url_sha256': admission.deck_url_sha256,
                          'max_steps': admission.max_steps,
                          'wall_seconds': admission.wall_seconds,
                          'official_final_admitted': 0}, sort_keys=True))
        return
    from e2b_desktop import Sandbox
    require(importlib.metadata.version('e2b-desktop') == '2.2.0',
            'desktop_sdk_version_drift')
    result = run(args.session, args.task, args.config, args.out, Sandbox)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
