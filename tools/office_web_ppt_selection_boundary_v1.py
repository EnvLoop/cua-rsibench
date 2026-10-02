"""Selection-only E2B manual login and one-file PowerPoint actor admission.

Train-only Office sessions and ACL receipts are never relabeled as selection.
The real selection Graph permission lease is currently disabled until a frozen
matrix gate and account pilot exist, so live admission fails closed. Fake tests
exercise the exact source, task, sandbox and permission receipt contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlsplit

from tools import office_web_actor_scope_gate_v1 as prior_scope
from tools import office_web_e2b_login_bridge_v1 as prior_bridge
from ppt_wdi_factory import verify as ppt_verify
from ppt_wdi_factory import plan as ppt_plan


SESSION_SCHEMA = 'cua-office-ppt-e2b-selection-session-v1'
SCOPE_SCHEMA = 'cua-office-ppt-selection-one-file-scope-v1'
TASK_SCHEMA = 'ppt-wdi-original-candidates-v1'
CONFIG_SCHEMA = 'cua-office-ppt-e2b-selection-run-v1'
GRAPH_LEASE_SCHEMA = 'cua-office-ppt-selection-graph-lease-v1'
EXPECTED_TEMPLATE_ID = prior_bridge.EXPECTED_TEMPLATE_ID
HOME_URL = 'https://powerpoint.cloud.microsoft/'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_TASK = re.compile(r'ppt-wdi-[a-z0-9]{16}\Z')
_FILE = re.compile(r'EL-PPT-Selection-[A-Za-z0-9._-]{1,100}\.pptx\Z')
_DOC = re.compile(r'/personal/[0-9A-Fa-f]{16}/_layouts/15/Doc\.aspx\Z')
_SOURCE_DOC = re.compile(
    r'\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}\Z')


class PptSelectionBoundaryError(ValueError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise PptSelectionBoundaryError(code)


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


def _private(path: Path, root: Path, label: str,
             maximum: int = 2_000_000) -> bytes:
    original = Path(path)
    _require(not original.is_symlink(), label + '_private_file_required')
    target = original.resolve()
    _require(target.is_file() and
             target.is_relative_to(root.resolve()) and
             target.stat().st_mode & 0o077 == 0 and
             0 < target.stat().st_size <= maximum,
             label + '_private_file_required')
    return target.read_bytes()


def _json(path: Path, root: Path, label: str) -> tuple[dict, bytes]:
    raw = _private(path, root, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PptSelectionBoundaryError(label + '_invalid_json') from None
    _require(type(value) is dict, label + '_object_required')
    return value, raw


def validate_selection_url(value: object) -> str:
    _require(type(value) is str and len(value) <= 2048,
             'ppt_selection_url_invalid')
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        raise PptSelectionBoundaryError('ppt_selection_url_invalid') from None
    _require(parsed.scheme == 'https' and
             parsed.hostname == 'onedrive.live.com' and
             parsed.username is None and parsed.password is None and
             port is None and not parsed.fragment and
             _DOC.fullmatch(parsed.path) is not None,
             'ppt_selection_url_invalid')
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(pairs)
    _require(len(pairs) == len(query) and
             set(query) in ({'sourcedoc', 'file', 'action'},
                            {'sourcedoc', 'file', 'action',
                             'mobileredirect'}) and
             _SOURCE_DOC.fullmatch(query['sourcedoc']) is not None and
             _FILE.fullmatch(query['file']) is not None and
             query['action'] in ('default', 'edit') and
             query.get('mobileredirect') in (None, 'true'),
             'ppt_selection_url_invalid')
    return value


def validate_package(task_path: Path, work_root: Path,
                     expected_task: dict) -> dict:
    path = Path(task_path).absolute()
    parts = path.parts
    _require(path.name == 'task.private.json' and
             path.parent.name == expected_task['task_id'] and
             any(parts[index:index + 2] == ('packages', 'selection')
                 for index in range(len(parts) - 1)) and
             not any(part.lower() in ('final', 'official')
                     for part in parts),
             'ppt_selection_package_path_invalid')
    value, raw = _json(path, work_root, 'ppt_selection_task')
    _require(value.get('schema') == TASK_SCHEMA and
        value.get('split') == 'selection' and
        value.get('task_id') == expected_task['task_id'] and
        _TASK.fullmatch(value['task_id']) and
        value.get('actor_task') == expected_task['visible_instruction'] and
        value.get('official_final_credit') == 0 and
        value.get('workflow') in ppt_plan.WORKFLOWS[:8] and
        value.get('target_keys') ==
            ['summary', 'ledger', 'interpretation'] and
        type(expected_task.get('actor_seed_sha256')) is str and
        _HEX.fullmatch(expected_task['actor_seed_sha256']),
        'ppt_selection_package_not_frozen')
    source = path.parent / 'source.pptx'
    source_raw = _private(source, work_root,
                          'ppt_selection_source', 50_000_000)
    frozen = ppt_verify.freeze(source, value)
    _require(frozen['source_sha256'] == _sha(source_raw) and
             len(frozen['targets']) == 3,
             'ppt_selection_source_or_three_targets_changed')
    return {'task_sha256': _sha(raw),
            'source_sha256': _sha(source_raw),
            'actor_sha256': expected_task['actor_seed_sha256'],
            'task_path': path}


def _permission_snapshot(directory: Path, reference: dict, *,
                         name: str, owner_hash: str,
                         item_id: str) -> dict:
    try:
        return prior_scope.permission_snapshot(
            directory, reference, name=name,
            owner_hash=owner_hash, item_id=item_id)
    except prior_scope.ScopeError:
        raise PptSelectionBoundaryError(
            'ppt_selection_permission_snapshot_invalid') from None


def _non_actor_permission(permission: object, actor_email: str) -> bool:
    """Accept owner/inherited effective grants, never an extra direct share."""
    if type(permission) is not dict or type(permission.get('id')) is not str:
        return False
    roles = permission.get('roles')
    if type(roles) is not list or any(type(role) is not str for role in roles):
        return False
    link = permission.get('link')
    if link is not None and (type(link) is not dict or
                             link.get('scope') != 'existingAccess'):
        return False
    emails = []
    invitation = permission.get('invitation')
    if invitation is not None:
        if type(invitation) is not dict or type(invitation.get('email')) is not str:
            return False
        # A second direct invitation would expand the actor-visible file
        # beyond the exact one-person grant, even if its role says owner.
        if permission.get('inheritedFrom') is None:
            return False
        emails.append(invitation['email'])
    for name in ('grantedTo', 'grantedToV2'):
        identity = permission.get(name)
        if identity is not None:
            if type(identity) is not dict or type(identity.get('user')) is not dict:
                return False
            email = identity['user'].get('email')
            if email is not None:
                if type(email) is not str:
                    return False
                emails.append(email)
    for name in ('grantedToIdentities', 'grantedToIdentitiesV2'):
        identities = permission.get(name)
        if identities is not None:
            if type(identities) is not list:
                return False
            for identity in identities:
                if type(identity) is not dict or type(identity.get('user')) is not dict:
                    return False
                email = identity['user'].get('email')
                if email is not None:
                    if type(email) is not str:
                        return False
                    emails.append(email)
    if any(email.casefold() == actor_email.casefold() for email in emails):
        return False
    return (permission.get('inheritedFrom') is not None or
            'owner' in roles or link is not None)


def validate_scope(scope_path: Path, *, work_root: Path,
                   session_raw: bytes, sandbox_id: str,
                   item_url: str, task_id: str,
                   package_sha256: str, actor_seed_sha256: str,
                   lease_started_at_unix: int,
                   lease_end_unix: int, now: int) -> dict:
    directory = scope_path.parent
    value, raw = _json(scope_path, work_root,
                       'ppt_selection_scope')
    fields = {'schema', 'split', 'status', 'observed_at_unix',
              'valid_until_unix', 'session_sha256',
              'sandbox_id_sha256', 'assigned_url_sha256',
              'task_id', 'package_sha256', 'actor_seed_sha256',
              'owner_email', 'actor_email',
              'owner_principal_sha256', 'actor_principal_sha256',
              'assigned_item_id', 'parent_item_id',
              'owner_permissions', 'parent_permissions',
              'graph_lease', 'evidence', 'reviews'}
    _require(set(value) == fields and
             value['schema'] == SCOPE_SCHEMA and
             value['split'] == 'selection' and
             value['status'] == 'operator_reviewed' and
             type(value['observed_at_unix']) is int and
             type(value['valid_until_unix']) is int and
             lease_started_at_unix <= value['observed_at_unix'] <= now and
             now - value['observed_at_unix'] <= 300 and
             now < value['valid_until_unix'] <= lease_end_unix and
             value['session_sha256'] == _sha(session_raw) and
             value['sandbox_id_sha256'] == _sha(sandbox_id) and
             value['assigned_url_sha256'] == _sha(item_url) and
             value['task_id'] == task_id and
             value['package_sha256'] == package_sha256 and
             value['actor_seed_sha256'] == actor_seed_sha256 and
             type(value['owner_email']) is str and
             prior_scope._EMAIL.fullmatch(value['owner_email']) and
             type(value['actor_email']) is str and
             prior_scope._EMAIL.fullmatch(value['actor_email']) and
             value['owner_email'].casefold() !=
             value['actor_email'].casefold() and
             value['owner_principal_sha256'] ==
             _sha(value['owner_email'].casefold()) and
             value['actor_principal_sha256'] ==
             _sha(value['actor_email'].casefold()) and
             type(value['assigned_item_id']) is str and
             prior_scope._ITEM_ID.fullmatch(value['assigned_item_id']) and
             type(value['parent_item_id']) is str and
             prior_scope._ITEM_ID.fullmatch(value['parent_item_id']) and
             value['assigned_item_id'] != value['parent_item_id'],
             'ppt_selection_scope_binding_invalid')
    reviews = {'distinct_accounts', 'actor_signed_in_as_actor',
               'assigned_file_editable', 'sentinel_file_denied',
               'owner_seed_readback_matched',
               'no_other_benchmark_item_visible'}
    _require(type(value['reviews']) is dict and
             set(value['reviews']) == reviews and
             all(value['reviews'][key] is True for key in reviews) and
             type(value['evidence']) is dict and
             set(value['evidence']) == set(prior_scope._EVIDENCE_NAMES),
             'ppt_selection_scope_review_incomplete')
    for name in prior_scope._EVIDENCE_NAMES:
        try:
            prior_scope.evidence_file(
                directory, value['evidence'][name], name=name)
        except prior_scope.ScopeError:
            raise PptSelectionBoundaryError(
                'ppt_selection_scope_screenshot_invalid') from None
    owner = _permission_snapshot(
        directory, value['owner_permissions'],
        name='assigned-permissions',
        owner_hash=value['owner_principal_sha256'],
        item_id=value['assigned_item_id'])
    parent = _permission_snapshot(
        directory, value['parent_permissions'],
        name='parent-permissions',
        owner_hash=value['owner_principal_sha256'],
        item_id=value['parent_item_id'])
    _require(type(parent['value']) is list and
             all(_non_actor_permission(entry, value['actor_email'])
                 for entry in parent['value']) and
             type(owner['value']) is list,
             'ppt_selection_parent_or_file_scope_not_single')
    actor_grants = [entry for entry in owner['value'] if
                    type(entry) is dict and
                    type(entry.get('invitation')) is dict and
                    type(entry['invitation'].get('email')) is str and
                    entry['invitation']['email'].casefold() ==
                    value['actor_email'].casefold()]
    _require(len(actor_grants) == 1 and
             all(entry is actor_grants[0] or
                 _non_actor_permission(entry, value['actor_email'])
                 for entry in owner['value']),
             'ppt_selection_parent_or_file_scope_not_single')
    permission = actor_grants[0]
    _require(type(permission) is dict and
             type(permission.get('id')) is str and
             permission.get('roles') == ['write'] and
             type(permission.get('invitation')) is dict and
             permission['invitation'].get('signInRequired') is True and
             type(permission['invitation'].get('email')) is str and
             permission['invitation']['email'].casefold() ==
             value['actor_email'].casefold() and
             permission.get('inheritedFrom') is None and
             permission.get('link') is None,
             'ppt_selection_actor_permission_not_specific')
    graph_ref = value['graph_lease']
    _require(type(graph_ref) is dict and
             set(graph_ref) == {'file', 'sha256'} and
             graph_ref['file'] == 'selection-graph-lease.private.json' and
             type(graph_ref['sha256']) is str and
             _HEX.fullmatch(graph_ref['sha256']),
             'ppt_selection_graph_lease_missing')
    graph, graph_raw = _json(directory / graph_ref['file'],
                             work_root, 'ppt_selection_graph_lease')
    _require(_sha(graph_raw) == graph_ref['sha256'] and
             graph == {
                 'schema': GRAPH_LEASE_SCHEMA,
                 'status': 'active_verified_pre_result',
                 'cell_id': 'powerpoint-web',
                 'split': 'selection',
                 'task_id': task_id,
                 'package_sha256': package_sha256,
                 'actor_seed_sha256': actor_seed_sha256,
                 'item_id_sha256': _sha(value['assigned_item_id']),
                 'permission_id_sha256': _sha(permission['id']),
                 'actor_email_sha256':
                     _sha(value['actor_email'].casefold()),
                 'actor_target_read_and_sentinel_denial_passed': True,
             }, 'ppt_selection_graph_lease_not_bound')
    return {'scope_sha256': _sha(raw),
            'permission_id_sha256': _sha(permission['id']),
            'assigned_item_id': value['assigned_item_id'],
            'actor_email': value['actor_email']}


@dataclass(frozen=True)
class Admission:
    session_path: Path
    session_sha256: str
    sandbox_id: str
    task_id: str
    instruction: str
    task_sha256: str
    actor_sha256: str
    deck_url: str
    deck_url_sha256: str
    max_steps: int
    wall_seconds: int
    lease_end_unix: int
    scope_sha256: str
    permission_id_sha256: str
    assigned_item_id: str
    actor_email: str


def admit(session_path: Path, task_path: Path,
          config_path: Path, out: Path, *,
          work_root: Path, expected_task: dict,
          now: int | None = None) -> Admission:
    now = int(time.time()) if now is None else now
    source = validate_package(task_path, work_root, expected_task)
    out = Path(out).absolute()
    _require(out.resolve().is_relative_to(work_root.resolve()) and
             not out.exists() and not out.is_symlink(),
             'ppt_selection_admit_output_not_fresh')
    session, session_raw = _json(session_path, work_root,
                                  'ppt_selection_session')
    _require(set(session) == {
        'schema', 'status', 'task_split', 'account_login',
        'credential_or_cookie_injection',
        'credential_snapshot_or_export', 'official_final_admitted',
        'model_calls', 'sdk_version', 'expected_template_id',
        'observed_template_id', 'lease_started_at_unix',
        'lease_seconds', 'sandbox_id', 'stream_url',
        'stream_auth_key'} and
        session['schema'] == SESSION_SCHEMA and
        session['status'] == 'awaiting_manual_login' and
        session['task_split'] == 'selection_only' and
        session['account_login'] == 'manual_only' and
        session['credential_or_cookie_injection'] is False and
        session['credential_snapshot_or_export'] is False and
        session['official_final_admitted'] == 0 and
        session['model_calls'] == 0 and
        session['sdk_version'] == '2.2.0' and
        session['expected_template_id'] == EXPECTED_TEMPLATE_ID and
        session['observed_template_id'] == EXPECTED_TEMPLATE_ID and
        type(session['lease_started_at_unix']) is int and
        type(session['lease_seconds']) is int and
        300 <= session['lease_seconds'] <= 3600 and
        type(session['sandbox_id']) is str and
        re.fullmatch(r'[A-Za-z0-9_-]{8,128}',
                     session['sandbox_id']) is not None and
        not (session_path.parent / 'stop.private.json').exists(),
        'ppt_selection_login_session_invalid')
    prior_bridge.validate_stream(session['stream_url'],
                                 session['stream_auth_key'])
    end = session['lease_started_at_unix'] + session['lease_seconds']
    _require(end - now >= 60,
             'ppt_selection_e2b_lease_expired')
    config, _ = _json(config_path, work_root,
                       'ppt_selection_run_config')
    _require(set(config) == {
        'schema', 'split', 'manual_login_confirmed_at_unix',
        'deck_url', 'max_steps', 'wall_seconds'} and
        config['schema'] == CONFIG_SCHEMA and
        config['split'] == 'selection' and
        type(config['manual_login_confirmed_at_unix']) is int and
        session['lease_started_at_unix'] <=
        config['manual_login_confirmed_at_unix'] <= now and
        type(config['max_steps']) is int and
        1 <= config['max_steps'] <= 90 and
        type(config['wall_seconds']) is int and
        1 <= config['wall_seconds'] <= 1800 and
        config['wall_seconds'] + 60 <= end - now,
        'ppt_selection_run_config_invalid')
    url = validate_selection_url(config['deck_url'])
    scope = validate_scope(
        session_path.parent / 'actor-scope.private.json',
        work_root=work_root, session_raw=session_raw,
        sandbox_id=session['sandbox_id'], item_url=url,
        task_id=expected_task['task_id'],
        package_sha256=expected_task['package_sha256'],
        actor_seed_sha256=source['actor_sha256'],
        lease_started_at_unix=session['lease_started_at_unix'],
        lease_end_unix=end, now=now)
    return Admission(
        session_path, _sha(session_raw), session['sandbox_id'],
        expected_task['task_id'],
        expected_task['visible_instruction'],
        source['task_sha256'], source['actor_sha256'],
        url, _sha(url), config['max_steps'],
        config['wall_seconds'], end,
        scope['scope_sha256'], scope['permission_id_sha256'],
        scope['assigned_item_id'], scope['actor_email'])


class SelectionBridgeLeases:
    """Selection-only E2B Desktop2.2.0; separate from train bridge receipts."""

    def preflight(self) -> None:
        _require(bool(os.environ.get('E2B_API_KEY')),
                 'ppt_selection_e2b_key_missing_before_reservation')

    def create(self, out_dir: Path, lease_seconds: int) -> str:
        from e2b_desktop import Sandbox
        _require(not out_dir.exists() and 300 <= lease_seconds <= 3600,
                 'ppt_selection_e2b_fresh_bounded_lease_required')
        out_dir.mkdir(parents=True, mode=0o700)
        out_dir.chmod(0o700)
        _write_new(out_dir / 'intent.private.json', _canonical({
            'schema': SESSION_SCHEMA,
            'status': 'start_intent',
            'task_split': 'selection_only',
            'lease_seconds': lease_seconds,
            'expected_template_id': EXPECTED_TEMPLATE_ID,
            'credential_or_cookie_injection': False,
            'official_final_admitted': 0,
            'created_at_unix': int(time.time()),
        }))
        sandbox = None
        try:
            sandbox = Sandbox.create(
                template='desktop', resolution=(1280, 800),
                timeout=lease_seconds, allow_internet_access=True,
                secure=True, envs={})
            info = sandbox.get_info(request_timeout=12)
            _require(info.template_id == EXPECTED_TEMPLATE_ID,
                     'ppt_selection_template_changed')
            sandbox.stream.start(require_auth=True)
            url = sandbox.stream.get_url(auto_connect=False,
                                         view_only=False)
            key = sandbox.stream.get_auth_key()
            prior_bridge.validate_stream(url, key)
            sandbox.launch('google-chrome', uri=HOME_URL)
            session = {
                'schema': SESSION_SCHEMA,
                'status': 'awaiting_manual_login',
                'task_split': 'selection_only',
                'account_login': 'manual_only',
                'credential_or_cookie_injection': False,
                'credential_snapshot_or_export': False,
                'official_final_admitted': 0,
                'model_calls': 0,
                'sdk_version': importlib.metadata.version('e2b-desktop'),
                'expected_template_id': EXPECTED_TEMPLATE_ID,
                'observed_template_id': info.template_id,
                'lease_started_at_unix': int(time.time()),
                'lease_seconds': lease_seconds,
                'sandbox_id': sandbox.sandbox_id,
                'stream_url': url,
                'stream_auth_key': key,
            }
            _write_new(out_dir / 'session.private.json',
                       _canonical(session))
            return sandbox.sandbox_id
        except BaseException as exc:
            cleanup = 'not_created'
            if sandbox is not None:
                try:
                    cleanup = 'killed' if sandbox.kill() else \
                        'termination_unconfirmed'
                except Exception:
                    cleanup = 'termination_unconfirmed'
            _write_new(out_dir / 'failure.private.json', _canonical({
                'schema': SESSION_SCHEMA,
                'status': 'setup_failed',
                'task_split': 'selection_only',
                'exception_type': type(exc).__name__,
                'cleanup': cleanup,
                'official_final_admitted': 0,
            }))
            raise

    def connect(self, sandbox_id: str):
        from e2b_desktop import Sandbox
        return Sandbox.connect(sandbox_id)

    def stop(self, session_path: Path) -> str:
        from e2b_desktop import Sandbox
        value = json.loads(session_path.read_bytes())
        try:
            killed = Sandbox.kill(value['sandbox_id'])
        except Exception:
            killed = False
        status = 'killed' if killed else 'termination_unconfirmed'
        _write_new(session_path.parent / 'stop.private.json',
                   _canonical({
                       'schema': SESSION_SCHEMA,
                       'status': status,
                       'session_sha256': _sha(session_path.read_bytes()),
                       'sandbox_id_sha256': _sha(value['sandbox_id']),
                       'official_final_admitted': 0,
                   }))
        return status
