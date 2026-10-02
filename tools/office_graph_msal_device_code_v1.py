"""Manual MSAL device-code enrollment for two personal Graph principals.

No browser state, cookie, password, or application secret is read. Enrollment
starts only when an operator explicitly invokes one role. The returned access
token is kept in a separate owner-only file per role; no token reaches stdout,
logs, the app config, or the durable scope proof. Tokens are not refreshed or
reused after expiry by this helper. The Graph bootstrap pilot remains gated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


APP_SCHEMA = 'cua-office-graph-msal-public-client-v1'
ROLE_SCHEMA = 'cua-office-graph-device-role-token-v1'
SCOPE_SCHEMA = 'cua-office-graph-delegated-scope-observation-v1'
AUTHORITY = 'https://login.microsoftonline.com/consumers'
_GUID = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z')
_ID = re.compile(r'[A-Za-z0-9!._:-]{4,180}\Z')
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_CODE = re.compile(r'[A-Z0-9-]{4,32}\Z')
SCOPES = {'owner': ['Files.ReadWrite', 'User.Read'],
          'actor': ['Files.Read', 'User.Read']}


class DeviceAuthError(ValueError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise DeviceAuthError(code)


def _sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else
                           raw.encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _private_file(path: Path, root: Path,
                  maximum: int = 2_000_000) -> bytes:
    target = Path(path)
    _require(not target.is_symlink() and target.is_file() and
             target.resolve().is_relative_to(root.resolve()) and
             target.stat().st_mode & 0o077 == 0 and
             0 < target.stat().st_size <= maximum,
             'office_oauth_private_file_required')
    return target.read_bytes()


def _private_json(path: Path, root: Path) -> tuple[dict, bytes]:
    raw = _private_file(path, root)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DeviceAuthError('office_oauth_private_json_invalid') from None
    _require(type(value) is dict,
             'office_oauth_private_json_invalid')
    return value, raw


def _write_new(path: Path, raw: bytes) -> str:
    _require(not path.exists() and not path.is_symlink(),
             'office_oauth_output_already_exists')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(raw)


def load_app_config(path: Path, work_root: Path) -> tuple[dict, str]:
    config, raw = _private_json(path, work_root)
    fields = {'schema', 'client_id', 'authority', 'account_audience',
              'public_client_flows_enabled', 'role_scopes',
              'expected_graph_user_ids', 'max_device_seconds'}
    _require(set(config) == fields and
             config['schema'] == APP_SCHEMA and
             type(config['client_id']) is str and
             _GUID.fullmatch(config['client_id']) and
             type(config['authority']) is str and
             config['authority'].rstrip('/') == AUTHORITY and
             config['account_audience'] in {
                 'personal_microsoft_accounts_only',
                 'organizations_and_personal_microsoft_accounts'} and
             config['public_client_flows_enabled'] is True and
             config['role_scopes'] == SCOPES and
             type(config['expected_graph_user_ids']) is dict and
             set(config['expected_graph_user_ids']) == {'owner', 'actor'} and
             all(type(config['expected_graph_user_ids'][role]) is str and
                 _ID.fullmatch(config['expected_graph_user_ids'][role])
                 for role in ('owner', 'actor')) and
             config['expected_graph_user_ids']['owner'] !=
                 config['expected_graph_user_ids']['actor'] and
             type(config['max_device_seconds']) is int and
             120 <= config['max_device_seconds'] <= 900,
             'office_oauth_app_registration_config_invalid')
    return config, _sha(raw)


def _device_prompt(flow: object) -> tuple[str, str]:
    _require(type(flow) is dict and
             type(flow.get('user_code')) is str and
             _CODE.fullmatch(flow['user_code']) and
             type(flow.get('verification_uri')) is str,
             'office_oauth_device_response_invalid')
    parsed = urlsplit(flow['verification_uri'])
    _require(parsed.scheme == 'https' and
             parsed.hostname in {'microsoft.com', 'www.microsoft.com'} and
             parsed.path == '/devicelogin' and
             not parsed.query and not parsed.fragment and
             parsed.username is None and parsed.password is None and
             parsed.port is None,
             'office_oauth_verification_uri_unexpected')
    return flow['verification_uri'], flow['user_code']


def _granted_scopes(raw: object, role: str) -> list[str]:
    _require(type(raw) is str and raw.strip(),
             'office_oauth_token_scope_response_missing')
    scopes = set()
    for value in raw.split():
        if value.startswith('https://graph.microsoft.com/'):
            value = value.removeprefix('https://graph.microsoft.com/')
        elif '/' in value:
            raise DeviceAuthError(
                'office_oauth_token_scope_resource_changed')
        scopes.add(value.casefold())
    _require(all(scope.casefold() in scopes for scope in SCOPES[role]),
             'office_oauth_granted_scopes_insufficient')
    allowed = {scope.casefold() for scope in SCOPES[role]} | {
        'openid', 'profile', 'email', 'offline_access'}
    _require(scopes <= allowed,
             'office_oauth_unrequested_scope_in_token_response')
    return [scope for scope in SCOPES[role]]


def _real_graph_me(access_token: str) -> dict:
    import httpx
    with httpx.Client(timeout=httpx.Timeout(20, connect=8),
                      follow_redirects=False) as client:
        response = client.get('https://graph.microsoft.com/v1.0/me',
                              headers={'Authorization':
                                       'Bearer ' + access_token},
                              params={'$select': 'id'})
        _require(response.status_code == 200,
                 'office_oauth_graph_me_unavailable')
        value = response.json()
    _require(type(value) is dict,
             'office_oauth_graph_me_invalid')
    return value


def login_role(*, role: str, config_path: Path, output_dir: Path,
               work_root: Path, present, msal_module=None,
               graph_me=None, clock=None) -> dict:
    """One explicit, bounded device login; never silently picks an account."""
    _require(role in {'owner', 'actor'}, 'office_oauth_role_invalid')
    config, config_sha = load_app_config(config_path, work_root)
    output_dir = Path(output_dir).absolute()
    root = Path(work_root).resolve()
    parent = output_dir.parent
    _require(not output_dir.exists() and
             not output_dir.is_symlink() and
             parent.resolve().is_relative_to(root) and
             not parent.is_symlink() and
             callable(present),
             'office_oauth_fresh_private_role_dir_required')
    if not parent.exists():
        _require(parent.parent.resolve().is_relative_to(root),
                 'office_oauth_private_parent_required')
        parent.mkdir(mode=0o700)
    _require(parent.is_dir() and
             parent.stat().st_mode & 0o077 == 0,
             'office_oauth_private_parent_required')
    if msal_module is None:
        try:
            import msal as msal_module
        except ImportError:
            raise DeviceAuthError(
                'office_oauth_msal_dependency_missing') from None
    graph_me = graph_me or _real_graph_me
    clock = clock or (lambda: datetime.now(timezone.utc))
    app = msal_module.PublicClientApplication(
        config['client_id'], authority=AUTHORITY)
    flow = app.initiate_device_flow(scopes=SCOPES[role])
    uri, code = _device_prompt(flow)
    _require(type(flow.get('expires_at')) in (int, float) and
             flow['expires_at'] > 0,
             'office_oauth_device_expiry_missing')
    now = clock()
    flow['expires_at'] = min(flow['expires_at'],
                             now.timestamp() +
                             config['max_device_seconds'])
    present(uri, code)
    result = app.acquire_token_by_device_flow(flow)
    _require(type(result) is dict and
             type(result.get('access_token')) is str and
             len(result['access_token']) >= 32 and
             result.get('token_type') == 'Bearer' and
             type(result.get('expires_in')) is int and
             300 <= result['expires_in'] <= 86_400,
             'office_oauth_device_token_missing_or_invalid')
    scopes = _granted_scopes(result.get('scope'), role)
    token = result['access_token']
    identity = graph_me(token)
    _require(type(identity) is dict and
             identity.get('id') ==
             config['expected_graph_user_ids'][role],
             'office_oauth_wrong_personal_account')
    recorded = clock()
    _require(type(recorded) is datetime and
             recorded.tzinfo is not None,
             'office_oauth_clock_invalid')
    expiry = recorded + timedelta(seconds=result['expires_in'] - 60)
    output_dir.mkdir(mode=0o700)
    output_dir.chmod(0o700)
    token_path = output_dir / 'access-token.private'
    token_sha = _write_new(token_path, token.encode())
    proof = {
        'schema': ROLE_SCHEMA, 'role': role,
        'status': 'device_flow_graph_me_verified',
        'client_id_sha256': _sha(config['client_id']),
        'app_config_sha256': config_sha,
        'authority': AUTHORITY,
        'graph_user_id': identity['id'],
        'observed_scopes': scopes,
        'access_token_sha256': token_sha,
        'recorded_at_utc': recorded.isoformat(),
        'expires_at_utc': expiry.isoformat(),
        'token_storage': 'owner_only_mode_0600',
    }
    proof_sha = _write_new(output_dir / 'role-proof.private.json',
                           _canonical(proof))
    return {'status': 'private_role_token_ready', 'role': role,
            'role_proof_sha256': proof_sha,
            'expires_at_utc': expiry.isoformat(),
            'provider_graph_reads': 1}


def finalize_scopes(*, config_path: Path, auth_dir: Path,
                    work_root: Path, clock=None) -> dict:
    """Combine two exact private role proofs for the Graph bootstrap pilot."""
    config, config_sha = load_app_config(config_path, work_root)
    root = Path(work_root).resolve()
    auth_dir = Path(auth_dir).absolute()
    _require(auth_dir.is_dir() and not auth_dir.is_symlink() and
             auth_dir.resolve().is_relative_to(root) and
             auth_dir.stat().st_mode & 0o077 == 0,
             'office_oauth_private_auth_dir_required')
    now = clock() if clock else datetime.now(timezone.utc)
    tokens = {}
    proofs = {}
    for role in ('owner', 'actor'):
        role_dir = auth_dir / role
        _require(role_dir.is_dir() and not role_dir.is_symlink() and
                 role_dir.stat().st_mode & 0o077 == 0,
                 'office_oauth_private_role_dir_required')
        proof, _ = _private_json(role_dir /
                                 'role-proof.private.json', root)
        token_raw = _private_file(role_dir /
                                   'access-token.private', root,
                                   maximum=32_768)
        _require(set(proof) == {
            'schema', 'role', 'status', 'client_id_sha256',
            'app_config_sha256', 'authority', 'graph_user_id',
            'observed_scopes', 'access_token_sha256',
            'recorded_at_utc', 'expires_at_utc', 'token_storage'} and
            proof['schema'] == ROLE_SCHEMA and proof['role'] == role and
            proof['status'] == 'device_flow_graph_me_verified' and
            proof['client_id_sha256'] == _sha(config['client_id']) and
            proof['app_config_sha256'] == config_sha and
            proof['authority'] == AUTHORITY and
            proof['graph_user_id'] ==
                config['expected_graph_user_ids'][role] and
            proof['observed_scopes'] == SCOPES[role] and
            proof['access_token_sha256'] == _sha(token_raw) and
            proof['token_storage'] == 'owner_only_mode_0600' and
            datetime.fromisoformat(proof['recorded_at_utc']) <= now <
                datetime.fromisoformat(proof['expires_at_utc']),
            'office_oauth_role_proof_or_token_changed')
        proofs[role] = proof
        tokens[role] = token_raw.decode()
    _require(proofs['owner']['graph_user_id'] !=
             proofs['actor']['graph_user_id'] and
             tokens['owner'] != tokens['actor'],
             'office_oauth_owner_actor_not_distinct')
    expires = min(datetime.fromisoformat(
        proofs[role]['expires_at_utc']) for role in proofs)
    scope = {
        'schema': SCOPE_SCHEMA,
        'status': 'observed_in_oauth_client_token_response',
        'source': 'evaluator_private_oauth_client',
        'owner_user_id': proofs['owner']['graph_user_id'],
        'actor_user_id': proofs['actor']['graph_user_id'],
        'owner_token_sha256': _sha(tokens['owner']),
        'actor_token_sha256': _sha(tokens['actor']),
        'owner_delegated_scopes': SCOPES['owner'],
        'actor_delegated_scopes': SCOPES['actor'],
        'recorded_at_utc': now.isoformat(),
        'expires_at_utc': expires.isoformat(),
    }
    path = auth_dir / 'oauth-scopes.private.json'
    digest = _write_new(path, _canonical(scope))
    return {'status': 'bootstrap_scope_proof_ready',
            'scope_receipt_sha256': digest,
            'expires_at_utc': expires.isoformat(),
            'owner_actor_distinct': True}


def with_private_tokens(*, auth_dir: Path, work_root: Path,
                        run) -> object:
    """Inject two bound tokens into an explicit callback, then erase env."""
    root = Path(work_root).resolve()
    auth_dir = Path(auth_dir).absolute()
    scope, _ = _private_json(
        auth_dir / 'oauth-scopes.private.json', root)
    _require(set(scope) == {
        'schema', 'status', 'source', 'owner_user_id',
        'actor_user_id', 'owner_token_sha256',
        'actor_token_sha256', 'owner_delegated_scopes',
        'actor_delegated_scopes', 'recorded_at_utc',
        'expires_at_utc'} and
             scope.get('schema') == SCOPE_SCHEMA and
             scope.get('status') ==
             'observed_in_oauth_client_token_response' and
             scope.get('source') ==
             'evaluator_private_oauth_client' and
             scope.get('owner_delegated_scopes') == SCOPES['owner'] and
             scope.get('actor_delegated_scopes') == SCOPES['actor'] and
             scope.get('owner_user_id') != scope.get('actor_user_id') and
             datetime.fromisoformat(scope['recorded_at_utc']) <=
             datetime.now(timezone.utc) <
             datetime.fromisoformat(scope['expires_at_utc']),
             'office_oauth_scope_receipt_expired_or_invalid')
    tokens = {}
    for role in ('owner', 'actor'):
        raw = _private_file(auth_dir / role /
                            'access-token.private', root,
                            maximum=32_768)
        _require(_sha(raw) == scope[role + '_token_sha256'],
                 'office_oauth_access_token_changed')
        tokens[role] = raw.decode()
    _require(callable(run), 'office_oauth_callback_required')
    old = {name: os.environ.get(name) for name in (
        'MS_GRAPH_OWNER_TOKEN', 'MS_GRAPH_ACTOR_TOKEN')}
    try:
        os.environ['MS_GRAPH_OWNER_TOKEN'] = tokens['owner']
        os.environ['MS_GRAPH_ACTOR_TOKEN'] = tokens['actor']
        return run()
    finally:
        for name, prior in old.items():
            if prior is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = prior
