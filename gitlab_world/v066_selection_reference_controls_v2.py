"""Exact original slash-prefixed session URI contract; V1 stays preserved.

Only canonical URI construction and private refusal evidence differ. Original
selection tasks, recipes, oracle, Native146, actor budgets and reset are intact.
"""
from hashlib import sha256
from pathlib import Path
import re
from types import FunctionType, ModuleType
from urllib.parse import urlsplit, urlunsplit
from . import v066_selection_reference_controls_v1 as prior

PARENT_SHA = '59a13d171dcfe556bdbbd6da8cf58a5d79d5f1531881a95a1280f98bf2536f64'
if sha256(Path(prior.__file__).read_bytes()).hexdigest() != PARENT_SHA:
    raise ValueError('Frozen consumed selection V1 changed')
world, models = prior.world, prior.models
_scope = ModuleType('gitlab_world._selection_reference_controls_v2')
_scope.__dict__.update(vars(prior))
_scope.__file__ = __file__
_scope.SCHEMA = 'gitlab-original-selection20-reference-authority-v2'
for name, value in list(vars(prior).items()):
    if isinstance(value, FunctionType) and value.__globals__ is vars(prior):
        clone = FunctionType(value.__code__, vars(_scope), value.__name__, value.__defaults__, value.__closure__)
        clone.__kwdefaults__ = value.__kwdefaults__
        clone.__annotations__ = value.__annotations__
        setattr(_scope, name, clone)


def source_binding():
    value = prior.source_binding(); value.pop('binding_sha256')
    root = Path(__file__).resolve().parents[1]
    names = ('gitlab_world/v066_selection_reference_controls_v2.py',
             'tests/test_gitlab_selection_reference_controls_v2.py')
    value['source_sha256s'].update({name: sha256((root/name).read_bytes()).hexdigest() for name in names})
    value.update(schema='gitlab-selection20-reference-controller-source-v2',
                 original_session_slash_prefixed_project_contract=True,
                 consumed_v1_control_credit=0, uri_origin_project_or_path_relaxation=False)
    return value | {'binding_sha256': models.common.digest(models.common.canonical(value))}


def _owned_uri(active, relative):
    """Use the original session path exactly; never normalize observed URLs."""
    path = active.project_path
    original = getattr(active, 'original_task', {}).get('project_family')
    canonical = (type(path) is str and re.fullmatch(r'/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+', path) is not None
                 and all(part not in ('', '.', '..') for part in path.split('/')[1:]))
    relative_ok = (relative in ('/-/blob/main/security/release-policy.md', '/-/blob/main/security/kev-register.csv')
                   or type(relative) is str and re.fullmatch(r'/-/issues/[1-9][0-9]*', relative) is not None)
    current = urlsplit(active.page.url)
    expected_text = world.runtime.BASE + path + relative if canonical and relative_ok else None
    expected = urlsplit(expected_text) if expected_text else None
    valid = (canonical and type(original) is str and path == '/'+original and relative_ok and
             not current.username and not current.password and
             (current.scheme, current.netloc, current.path) == (expected.scheme, expected.netloc, expected.path))
    if valid: return
    # Diagnostics remain inside the owned case. Credentials/query/fragment are
    # omitted, while the exact URI digest records the rejected original bytes.
    diagnostic = {'schema': 'gitlab-selection-v2-current-uri-refusal-v1',
                  'original_session_project_path': path, 'original_task_project_family': original,
                  'relative_path': relative, 'project_path_canonical': canonical,
                  'relative_path_supported': relative_ok, 'expected_uri': expected_text,
                  'actual_uri_without_credentials_query_fragment': urlunsplit(
                      (current.scheme, current.netloc.rsplit('@', 1)[-1], current.path, '', '')),
                  'actual_exact_uri_sha256': sha256(active.page.url.encode()).hexdigest(),
                  'actual_uri_had_credentials': bool(current.username or current.password),
                  'gui_input_performed_by_uri_check': False, 'observed_uri_normalized_for_acceptance': False}
    error = ValueError('selection_current_original_project_uri_required')
    error.uri_diagnostic = diagnostic
    try:
        store = active.guard.store
        sequence = getattr(active, '_uri_refusal_sequence', 0)
        active._uri_refusal_sequence = sequence + 1
        store.json(f'reference-uri/refusal-{sequence:03d}.private.json', diagnostic,
                   'native_observation_envelope')
    except BaseException as capture_error:
        error.uri_diagnostic_capture_error = type(capture_error).__name__
    raise error


_scope._owned_uri = _owned_uri
_scope.source_binding = source_binding
def __getattr__(name): return getattr(_scope, name)


if __name__ == '__main__': _scope.main()
