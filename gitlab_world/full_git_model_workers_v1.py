"""Additive model wrappers retaining complete native Git proof before reset.

Original workers, actors, graders and campaign gates keep their source bytes.
The one supplemental source binding is mandatory for teacher, Qwen base,
checkpoint selection and every final slot; it earns no admission or model credit.
"""
from __future__ import annotations

import copy
import ast
import argparse
from contextlib import contextmanager, nullcontext
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re

from . import teacher_episode_worker_v066 as teacher
from . import selection_worker_v066 as selection
from . import full_git_model_oracle_v1 as oracle
from . import verify
from . import v066_prospective_cohort_v6 as cohort_source
from . import v066_prospective_cohort_runtime_v6 as cohort_scope

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'envloop-gitlab-full-git-model-source-binding-v1'
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
FILES = tuple(dict.fromkeys((
    'gitlab_world/full_git_model_workers_v1.py', 'gitlab_world/full_git_model_oracle_v1.py',
    'gitlab_world/full_git_final_worker_v1.py', 'gitlab_world/full_git_shared_base_execution_v1.py',
    'gitlab_world/v066_saved_git_oracle_v1.py', 'gitlab_world/train_teacher_oracle_v066.py',
    'gitlab_world/selection_oracle_v066.py', 'gitlab_world/verify.py',
    'gitlab_world/vision_actor_v066_train.py', 'gitlab_world/vision_actor.py',
    'gitlab_world/v066_prospective_cohort_runtime_v6.py',
    'src/cursibench/full_study_shared_base_execution_v1.py',
    'src/cursibench/full_study_final_dispatch_v1.py',
    'src/cursibench/full_study_matrix_v1.py',
) + tuple(teacher.RUNTIME_FILES) + tuple(selection.RUNTIME_FILES) + tuple(cohort_source.SOURCE_FILES)))


def digest(raw):
    return sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def require(ok, code):
    if not ok:
        raise ValueError(code)


def closed_source_files():
    """Read-only recursive in-repository import closure, including lazy imports.

    Parse source rather than importing dependencies, so freezing cannot start
    an application or provider. Explicit source/data roots also cover the
    runtime's known dynamic import tables and fixed dataset assets.
    """
    names = set(FILES)
    pending = list(FILES)

    def resolve(module):
        if not module:
            return None
        relative = module.replace('.', '/')
        for name in (relative + '.py', relative + '/__init__.py',
                     'src/' + relative + '.py', 'src/' + relative + '/__init__.py'):
            path = ROOT / name
            if path.is_file():
                require(not path.is_symlink(), 'full_git_source_dependency_symlink')
                return name
        return None

    while pending:
        name = pending.pop()
        if not name.endswith('.py'):
            continue
        module = name.removeprefix('src/').removesuffix('.py').replace('/', '.')
        package = module.removesuffix('.__init__') if module.endswith('.__init__') else module.rsplit('.', 1)[0]
        tree = ast.parse((ROOT / name).read_bytes(), filename=name)
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = ('.'.join(package.split('.')[:len(package.split('.')) - node.level + 1])
                        if node.level else '')
                module_name = '.'.join(part for part in (base, node.module or '') if part)
                modules.append(module_name)
                modules.extend(module_name + '.' + alias.name for alias in node.names if alias.name != '*')
        for module_name in modules:
            found = resolve(module_name)
            if found is not None and found not in names:
                names.add(found)
                pending.append(found)
    return tuple(sorted(names))


def public_binding():
    data = {'schema': SCHEMA, 'source_sha256s': {p: digest((ROOT / p).read_bytes()) for p in closed_source_files()},
            'partition_oracle_source_sha256s': oracle.source_bindings(),
            'adapter_sha256': teacher.adapter_sha256(),
            'legacy_teacher_runtime_sha256': teacher.runtime_sha256(),
            'legacy_selection_runtime_sha256': selection.runtime_sha256(),
            'same_original_model_action_runtime_data': True, 'full_git_sidecar_before_reset': True,
            'captured_boolean_is_authority': False, 'historical_six_path_fallback_allowed': False,
            'source_closure_policy': 'recursive_in_repository_python_imports_and_explicit_dynamic_roots',
            'uniform_final_slot_source_policy': 'one_whole_binding_for_shared_base_and_four_selected_slots',
            'model_calls': 0, 'official_final_admitted': 0}
    return {**data, 'binding_sha256': digest(canonical(data))}


def validate_binding(value):
    require(type(value) is dict and canonical(value) == canonical(public_binding()),
            'full_git_model_source_binding_changed')
    return value


def private_json(path, expected_sha=None):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and not path.stat().st_mode & 0o077 and
            0 < path.stat().st_size <= 8_000_000, 'full_git_private_binding_unsafe')
    raw = path.read_bytes()
    require(expected_sha is None or digest(raw) == expected_sha, 'full_git_source_file_hash_changed')
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError('full_git_private_json_invalid') from None
    require(type(value) is dict, 'full_git_binding_object_required')
    return value


def _read_ref(root, ref):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink() and not root.stat().st_mode & 0o077,
            'full_git_raw_root_unsafe')
    require(type(ref) is dict and set(ref) == {'path', 'sha256'} and type(ref['path']) is str and
            HEX64.fullmatch(str(ref['sha256'])) is not None, 'full_git_raw_ref_shape_changed')
    relative = PurePosixPath(ref['path'])
    require(ref['path'] and not relative.is_absolute() and
            all(part not in ('', '.', '..') for part in ref['path'].split('/')),
            'full_git_ref_escaped_owned_artifact_root')
    current = root
    for part in relative.parts:
        current = current / part
        require(not current.is_symlink() and current.exists() and not current.stat().st_mode & 0o077,
                'full_git_raw_artifact_path_unsafe')
    require(current.is_file() and current.stat().st_size <= 8_000_000, 'full_git_raw_artifact_unsafe')
    raw = current.read_bytes()
    require(digest(raw) == ref['sha256'], 'full_git_raw_artifact_hash_changed')
    return raw


def _write(root, name, raw):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink() and not root.stat().st_mode & 0o077 and
            type(raw) is bytes and len(raw) <= 8_000_000 and type(name) is str and
            PurePosixPath(name).name == name and name not in ('', '.', '..'), 'full_git_private_write_unsafe')
    path = root / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': name, 'sha256': digest(raw)}


def execution_verdict(partition, audited):
    """Mechanical receipt adaptation; the original formal verdict is retained."""
    verdict = audited['verdict']
    if partition != 'final_candidate_unsealed':
        return copy.deepcopy(verdict)
    require(type(verdict.get('score')) is float and verdict['score'] in (0.0, 1.0) and
            type(verdict.get('no_regression')) is bool, 'full_git_final_original_verdict_invalid')
    return {'reward': verdict['score'], 'checks_passed': verdict['no_regression'],
            'difference_codes': [] if verdict['no_regression'] else ['target_or_no_regression_mismatch'],
            'before_business_sha256': verdict['before_business_sha256'],
            'after_business_sha256': verdict['after_business_sha256']}


class FullGitSession:
    """Capture inside the original backend lease, before its cold-reset finally."""

    def __init__(self, active, *, partition, artifact_root, binding, cohort_source_file_sha256=None):
        self._active, self.partition = active, partition
        self.artifact_root, self.binding = Path(artifact_root), binding
        self.cohort_source_file_sha256 = cohort_source_file_sha256
        self._saved = None
        self._capture_attempted = False
        self._read_called = False

    def __getattr__(self, name):
        return getattr(self._active, name)

    def _capture(self, *, reload_gui, reason):
        require(not self._capture_attempted, 'full_git_capture_one_attempt_only')
        self._capture_attempted = True
        validate_binding(self.binding)
        active = self._active
        reload_sha = None
        if reload_gui:
            require(active.loop.call(active._check_scoped()) is True, 'full_git_model_left_scoped_project')
            reload_sha = active.loop.call(active._reload())
            require(HEX64.fullmatch(str(reload_sha)) is not None, 'full_git_native_reload_frame_invalid')
        before = active.baseline_semantic['business_snapshot']
        after = verify.state_snapshot()
        task = active.original_task
        project, progress = verify._context(task)
        identity = {key: active.task[key] for key in ('task_id', 'package_sha256')}
        require(identity['task_id'] == task['task_id'] and HEX64.fullmatch(identity['package_sha256']) is not None,
                'full_git_actor_identity_changed')
        root = self.artifact_root / 'full-git-proof'
        root.mkdir(mode=0o700, exist_ok=False)
        context = copy.deepcopy({'schema': 'envloop-gitlab-full-git-private-context-v1',
                                 'partition': self.partition, 'actor_identity': identity,
                                 'task': task, 'project': project, 'progress': progress, 'before': before})
        context_ref = _write(root, 'context.private.json', canonical(context))
        sidecar = oracle.capture_model_git(task, before, after, project=project, progress=progress,
                                           git=verify._git, save_ref=lambda name, raw: _write(root, name, raw),
                                           partition=self.partition)
        sidecar_ref = _write(root, 'sidecar.private.json', canonical(sidecar))
        audited = oracle.audit_model_saved_task(
            task, before, after, project=project, progress=progress, captured_git=sidecar,
            read_ref=lambda ref: _read_ref(root, ref), partition=self.partition,
            expected_sourcebindings=self.binding['partition_oracle_source_sha256s'])
        require(audited.get('full_git_tree_verified') is True, 'full_git_model_readback_incomplete')
        audit_ref = _write(root, 'audit.private.json', canonical(audited))
        saved = {'business_snapshot': after, 'independent_score': execution_verdict(self.partition, audited),
                 'full_git_original_verdict': audited['verdict'], 'gui_reload_frame_sha256': reload_sha,
                 'original_gitlab_ce': True, 'postgresql_and_git_readback': True,
                 'model_finished': active.finished, 'full_git_tree_verified': True,
                 'full_git_capture_reason': reason, 'full_git_sidecar_before_reset': True,
                 'full_git_sidecar_ref': {'path': 'full-git-proof/' + sidecar_ref['path'], 'sha256': sidecar_ref['sha256']},
                 'full_git_audit_ref': {'path': 'full-git-proof/' + audit_ref['path'], 'sha256': audit_ref['sha256']},
                 'full_git_context_ref': {'path': 'full-git-proof/' + context_ref['path'], 'sha256': context_ref['sha256']},
                 'full_git_model_binding_sha256': self.binding['binding_sha256'],
                 'full_git_cohort_source_file_sha256': self.cohort_source_file_sha256,
                 'captured_boolean_is_authority': False}
        _write(root, 'captured-saved.private.json', canonical(saved))
        self._saved = copy.deepcopy(saved)
        return saved

    def read_saved_state(self):
        require(not self._read_called, 'full_git_saved_read_one_attempt_only')
        self._read_called = True
        if self.partition == 'train':
            require(self._active.finished is True, 'full_git_teacher_finish_missing')
        return self._capture(reload_gui=True, reason='model_saved_read_before_reset')

    def retain_before_reset(self, original_error):
        if not self._capture_attempted:
            try:
                self._capture(reload_gui=False, reason='terminal_backend_exit_before_reset_no_model_credit')
            except BaseException as error:
                _write(self.artifact_root, 'full-git-capture-failure.private.json', canonical({
                    'schema': 'envloop-gitlab-full-git-capture-failure-v1', 'error_type': type(error).__name__,
                    'original_error_type': type(original_error).__name__ if original_error else None,
                    'automatic_capture_replay': False, 'model_credit': 0}))
                if original_error is None:
                    raise
        if original_error is None:
            require(self._read_called and self._saved is not None, 'full_git_model_saved_read_missing')


class FullGitBackend:
    def __init__(self, backend, *, partition, binding, cohort_freeze_path=None):
        require(partition in oracle.PARTITIONS, 'full_git_backend_partition_invalid')
        self.backend, self.partition, self.binding = backend, partition, validate_binding(binding)
        self.output_root = None
        self.cohort_freeze_path = Path(cohort_freeze_path) if cohort_freeze_path is not None else None
        if self.cohort_freeze_path is not None:
            private_json(self.cohort_freeze_path)
        self.cohort_source_file_sha256 = (digest(self.cohort_freeze_path.read_bytes())
                                         if self.cohort_freeze_path is not None else None)

    def set_output_root(self, path):
        self.output_root = Path(path) if path is not None else None

    @contextmanager
    def open(self, identity):
        validate_binding(self.binding)
        require(self.output_root is not None, 'full_git_artifact_root_required_before_start')
        root = self.output_root / 'artifacts'
        require(root.is_dir() and not root.is_symlink() and not root.stat().st_mode & 0o077,
                'full_git_owned_artifact_root_missing_before_start')
        if self.cohort_freeze_path is not None:
            private_json(self.cohort_freeze_path, self.cohort_source_file_sha256)
        value = cohort_source.validate_source(self.cohort_freeze_path) if self.cohort_freeze_path else None
        scope = cohort_scope.cohort_context(value) if value is not None else nullcontext()
        with scope:
            with self.backend.open(identity) as active:
                wrapper = FullGitSession(active, partition=self.partition, artifact_root=root, binding=self.binding,
                                         cohort_source_file_sha256=self.cohort_source_file_sha256)
                original_error = None
                try:
                    yield wrapper
                except BaseException as error:
                    original_error = error
                    raise
                finally:
                    # This executes before leaving backend.open, whose finally
                    # destroys the mutable clone and restores the cold baseline.
                    wrapper.retain_before_reset(original_error)


def _verify_saved_proof(root, saved, identity, before, binding, *, cohort_source_file_sha256=None):
    """Reopen raw proof after reset using retained private context, no lookup."""
    validate_binding(binding)
    require(saved.get('full_git_model_binding_sha256') == binding['binding_sha256'] and
            saved.get('full_git_cohort_source_file_sha256') == cohort_source_file_sha256 and
            saved.get('full_git_sidecar_before_reset') is True and saved.get('full_git_tree_verified') is True and
            saved.get('captured_boolean_is_authority') is False and
            saved.get('full_git_capture_reason') == 'model_saved_read_before_reset',
            'full_git_saved_proof_binding_missing')
    context = json.loads(_read_ref(root, saved['full_git_context_ref']))
    require(type(context) is dict and set(context) == {'schema', 'partition', 'actor_identity', 'task', 'project', 'progress', 'before'} and
            context['schema'] == 'envloop-gitlab-full-git-private-context-v1' and
            context['actor_identity'] == {key: identity[key] for key in ('task_id', 'package_sha256')} and
            context['task']['task_id'] == identity['task_id'] and context['task']['partition'] == context['partition'] and
            context['before'] == before, 'full_git_saved_private_context_changed')
    sidecar = json.loads(_read_ref(root, saved['full_git_sidecar_ref']))
    retained = json.loads(_read_ref(root, saved['full_git_audit_ref']))
    proofroot = Path(root) / 'full-git-proof'
    audited = oracle.audit_model_saved_task(
        context['task'], before, saved['business_snapshot'], project=context['project'], progress=context['progress'],
        captured_git=sidecar, read_ref=lambda ref: _read_ref(proofroot, ref), partition=context['partition'],
        expected_sourcebindings=binding['partition_oracle_source_sha256s'])
    require(canonical(audited) == canonical(retained) and
            canonical(saved['full_git_original_verdict']) == canonical(audited['verdict']) and
            canonical(saved['independent_score']) == canonical(execution_verdict(context['partition'], audited)),
            'full_git_saved_formal_proof_rederivation_changed')
    return audited


def _require_source(worker, binding, path, file_sha):
    require(worker.enable_live is True, 'full_git_model_live_gate_disabled')
    require(canonical(private_json(path, file_sha)) == canonical(binding), 'full_git_model_exact_source_freeze_changed')
    validate_binding(binding)


def _audit_episode_output(out_dir, identity, binding, *, backend):
    artifacts = Path(out_dir) / 'artifacts'
    saved = private_json(artifacts / 'saved-artifact.private.json')
    baseline = private_json(artifacts / 'baseline.private.json')
    private_json(backend.cohort_freeze_path, backend.cohort_source_file_sha256)
    audit = _verify_saved_proof(artifacts, saved, identity, baseline['business_snapshot'], binding,
                                cohort_source_file_sha256=backend.cohort_source_file_sha256)
    _write(artifacts, 'full-git-post-reset-audit.private.json', canonical(audit))
    return audit


def train_worker(*, full_git_binding_path, full_git_binding_file_sha256, cohort_freeze_path, **kwargs):
    require(cohort_freeze_path is not None, 'full_git_model_explicit_cohort_required')
    binding = validate_binding(private_json(full_git_binding_path, full_git_binding_file_sha256))

    class Worker(teacher.GitLabTrainEpisodeWorker):
        def __init__(self, **options):
            super().__init__(**options)
            self.backend = FullGitBackend(self.backend, partition='train', binding=binding, cohort_freeze_path=cohort_freeze_path)

        def _require_ratification(self):
            _require_source(self, binding, full_git_binding_path, full_git_binding_file_sha256)
            return super()._require_ratification()

        def run_episode(self, **episode):
            self.backend.set_output_root(episode['out_dir'])
            try:
                result = super().run_episode(**episode)
                _audit_episode_output(episode['out_dir'], episode['task'], binding, backend=self.backend)
                return result
            finally:
                self.backend.set_output_root(None)

    return Worker(**kwargs)


def selection_worker(*, full_git_binding_path, full_git_binding_file_sha256, cohort_freeze_path,
                     base_mode=False, expected_base_freeze_sha256=None, **kwargs):
    binding = validate_binding(private_json(full_git_binding_path, full_git_binding_file_sha256))
    require(cohort_freeze_path is not None, 'full_git_model_explicit_cohort_required')
    require(type(base_mode) is bool, 'full_git_base_mode_boolean_required')

    class Worker(selection.GitLabSelectionWorker):
        def __init__(self, **options):
            super().__init__(**options)
            self.backend = FullGitBackend(self.backend, partition='selection', binding=binding, cohort_freeze_path=cohort_freeze_path)

        def _require_frozen(self, session, started):
            _require_source(self, binding, full_git_binding_path, full_git_binding_file_sha256)
            return super()._require_frozen(session, started)

        def _task_episode(self, **episode):
            self.backend.set_output_root(episode['out_dir'])
            try:
                result = super()._task_episode(**episode)
                _audit_episode_output(episode['out_dir'], episode['identity'], binding, backend=self.backend)
                return result
            finally:
                self.backend.set_output_root(None)

        def _resolve_checkpoint_path(self, session, checkpoint_sha):
            if not base_mode:
                return super()._resolve_checkpoint_path(session, checkpoint_sha)
            from cursibench.full_study_shared_base_execution_v1 import _verify_base_freeze
            require(checkpoint_sha == session.cell['base_checkpoint_sha256'] and
                    _verify_base_freeze(session.study, session.cell)['freeze_receipt_sha256'] == expected_base_freeze_sha256,
                    'full_git_shared_base_checkpoint_freeze_changed')
            return selection.MODEL

    return Worker(**kwargs)


__all__ = ['FullGitBackend', 'FullGitSession', 'public_binding', 'validate_binding', 'train_worker',
           'selection_worker', '_verify_saved_proof', '_audit_episode_output', 'execution_verdict']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    freeze = sub.add_parser('freeze-source')
    freeze.add_argument('--out', required=True, type=Path)
    check = sub.add_parser('check-source')
    check.add_argument('--binding', required=True, type=Path)
    check.add_argument('--binding-file-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'freeze-source':
        binding = public_binding()
        ref = _write(args.out.parent, args.out.name, canonical(binding))
    else:
        binding = validate_binding(private_json(args.binding, args.binding_file_sha256))
        ref = {'sha256': args.binding_file_sha256}
    print(json.dumps({'schema': SCHEMA, 'binding_sha256': binding['binding_sha256'],
                      'binding_file_sha256': ref['sha256'], 'source_files': len(binding['source_sha256s']),
                      'model_calls': 0, 'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
