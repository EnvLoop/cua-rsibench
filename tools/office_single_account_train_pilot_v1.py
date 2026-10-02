"""Read-only auditor for one manual, original Office web *train* pilot.

No second account, Graph token, Entra app, browser automation, model or paid
provider is needed. The local evaluator keeps the task, source and reference.
The signed-in dedicated test account is only operator-reviewed within one
folder: actor item, then a distinct reset item, then an empty folder.
Screenshots/inventory are assertions, not independent account-wide ACL proof.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlsplit

from ppt_wdi_factory import plan as ppt_plan, verify as ppt_verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal
from tools import office_web_e2b_train_runner_v1 as ppt_runner
from tools import excel_web_e2b_train_runner_v1 as excel_runner
from tools.office_web_excel_teacher_worker_v1 import SecOracleSubprocess
from tools.sec_excel_web_train_oracle_v1 import one_train_case


SPEC_SCHEMA = 'cua-office-single-account-train-spec-v1'
EVIDENCE_SCHEMA = 'cua-office-single-account-train-evidence-v1'
INVENTORY_SCHEMA = 'cua-office-single-account-folder-inventory-v1'
PRIVATE_RECEIPT_SCHEMA = 'cua-office-single-account-train-audit-v1'
PUBLIC_SCHEMA = 'cua-office-single-account-train-public-status-v1'
DEDICATED_ACCOUNT_SCOPE = 'signed_in_dedicated_test_account'
EXISTING_FOLDER_SCOPE = 'existing_account_dedicated_disposable_folder'
FOLDER_EVIDENCE_SCHEMA = 'cua-office-existing-account-folder-train-evidence-v1'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_DOC = re.compile(r'\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}\Z')
ROOT = Path(__file__).resolve().parents[1]


class SingleAccountPilotError(ValueError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise SingleAccountPilotError(code)


def _sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else
                           raw.encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _verifier_source_hash(cell_id: str) -> str:
    files = (
        ('ppt_wdi_factory/verify.py',
         'ppt_wdi_factory/plan.py',
         'tools/audit_ppt_wdi_web_train_triad_v1.py')
        if cell_id == 'powerpoint-web' else
        ('tools/sec_excel_web_train_oracle_v1.py',
         'sec_excel_factory/verify_integrated_candidate.py',
         'sec_excel_factory/verify_ooxml.py'))
    return _sha(_canonical({name: _sha((ROOT / name).read_bytes())
                            for name in (*files,
                                         'tools/office_single_account_train_pilot_v1.py')}))


def _private(path: Path, root: Path,
             maximum: int = 50_000_000) -> bytes:
    original = Path(path)
    _require(not original.is_symlink(),
             'single_account_private_file_required')
    target = original.resolve()
    _require(target.is_file() and
             target.is_relative_to(root.resolve()) and
             target.stat().st_mode & 0o077 == 0 and
             0 < target.stat().st_size <= maximum,
             'single_account_private_file_required')
    return target.read_bytes()


def _json(path: Path, root: Path) -> tuple[dict, bytes]:
    raw = _private(path, root, 2_000_000)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SingleAccountPilotError(
            'single_account_private_json_invalid') from None
    _require(type(value) is dict,
             'single_account_private_json_invalid')
    return value, raw


def _ref(value: object, root: Path, *, maximum=50_000_000) -> tuple[Path, bytes]:
    _require(type(value) is dict and set(value) == {'path', 'sha256'} and
             type(value['path']) is str and
             type(value['sha256']) is str and
             _HEX.fullmatch(value['sha256']) and
             not Path(value['path']).is_absolute(),
             'single_account_reference_invalid')
    path = root / value['path']
    raw = _private(path, root, maximum)
    _require(_sha(raw) == value['sha256'],
             'single_account_reference_bytes_changed')
    return path, raw


def _png(value: object, root: Path) -> str:
    _path, raw = _ref(value, root, maximum=4_000_000)
    _require(raw.startswith(b'\x89PNG\r\n\x1a\n') and
             len(raw) > 100,
             'single_account_ui_screenshot_invalid')
    return _sha(raw)


def _time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise SingleAccountPilotError(
            'single_account_observation_time_invalid') from None
    _require(parsed.tzinfo is not None,
             'single_account_observation_time_invalid')
    return parsed


def _item(value: object, cell_id: str) -> dict:
    _require(type(value) is dict and
             set(value) == {'edit_url', 'file_name'},
             'single_account_item_shape_invalid')
    try:
        url = (ppt_runner.validate_train_deck_url(value['edit_url'])
               if cell_id == 'powerpoint-web' else
               excel_runner.validate_train_workbook_url(
                   value['edit_url']))
    except ValueError:
        raise SingleAccountPilotError(
            'single_account_train_item_url_invalid') from None
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    source_doc = query.get('sourcedoc', [None])
    _require(query.get('file') == [value['file_name']] and
             len(source_doc) == 1 and
             type(source_doc[0]) is str and
             _DOC.fullmatch(source_doc[0]) and
             not re.search(r'(gold|answer|reference|selection|final)',
                           value['file_name'], re.IGNORECASE),
             'single_account_item_identity_changed')
    return {'file_name': value['file_name'],
            'edit_url_sha256': _sha(url),
            'sourcedoc_sha256': _sha(source_doc[0])}


def _write_new(path: Path, raw: bytes) -> str:
    _require(not path.exists() and not path.is_symlink(),
             'single_account_audit_already_exists')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(raw)


def _ppt_train_profile(task: dict, task_id: str) -> str:
    """Recognize source declarations only; raw WDI freeze remains mandatory."""
    _require(type(task) is dict and type(task_id) is str and
             task.get('schema') == 'ppt-wdi-original-candidates-v1' and
             task.get('task_id') == task_id and
             task.get('official_final_credit') == 0 and
             type(task.get('actor_task')) is str,
             'single_account_ppt_task_not_train_source')
    if (task.get('split') == 'train' and task.get('target_keys') == ['summary'] and
            not task_id.startswith('ppt-wdi-transfer-')):
        return 'original_wdi_single_target_train'
    workflow = task.get('workflow')
    _require(type(workflow) is str, 'single_account_ppt_task_not_train_source')
    expected = ppt_verify.FINAL_TARGETS.get(workflow, ppt_verify.DEFAULT_FINAL_TARGETS)
    _require(task.get('split') == 'train_policy_development' and
             task.get('development_source_split') == 'train' and
             task.get('analogue_role') ==
                 'additional_train_only_after_private_control_admission' and
             task.get('source_scope') == 'private_wdi_country_csv_reserve_v1' and
             task.get('rights_tier') == 'wdi_cc_by_4_0_facts_plus_authored_simulation' and
             type(task_id) is str and
             re.fullmatch(r'ppt-wdi-transfer-[0-9a-f]{16}', task_id) is not None and
             workflow in ppt_plan.WORKFLOWS and
             task.get('template_group') == f'ppt-transfer-brief-v1:{workflow}' and
             task.get('presentation_template') ==
                 'ppt_wdi_factory/build_train_transfer_deck.mjs' and
             task.get('target_keys') == expected and len(expected) == 4,
             'single_account_ppt_task_not_train_source')
    return 'transfer_wdi_four_target_train'


def _train_package_path(path: Path, cell_id: str) -> bool:
    """Require the immediate package namespace, never an earlier nested pair."""
    allowed = {'train'}
    if cell_id == 'powerpoint-web':
        allowed.add('train_policy_development')
    return (path.name == 'task.private.json' and
            path.parent.parent.name in allowed and
            path.parent.parent.parent.name == 'packages' and
            not any(part.lower() in {'selection', 'selection_candidate', 'final',
                                    'final_candidate', 'official'} for part in path.parts))


class OfficeTrainScorer:
    """Evaluator-only source/positive/reset checks for either Office file."""

    def __init__(self, spec: dict, paths: dict):
        self.spec = spec
        self.paths = paths
        self.case = None
        self.ppt_oracle = None
        self.excel_oracle = None
        if spec['cell_id'] == 'powerpoint-web':
            task = json.loads(paths['task'].read_bytes())
            self.source_profile = _ppt_train_profile(task, spec['task_id'])
            try:
                ppt_verify.freeze(paths['source'], task)
            except (OSError, KeyError, TypeError, ValueError):
                raise SingleAccountPilotError(
                    'single_account_ppt_source_not_wdi') from None
            self.case = task
        else:
            try:
                package = excel_runner.validate_train_package(
                    paths['task'])
                case = one_train_case(paths['cases'],
                                      spec['case_id'])
            except ValueError:
                raise SingleAccountPilotError(
                    'single_account_excel_source_not_train') from None
            _require(package.task_id == spec['task_id'] and
                     package.actor_sha256 ==
                     spec['source_ref']['sha256'],
                     'single_account_excel_task_source_changed')
            self.case = case
            self.excel_oracle = SecOracleSubprocess()
            calibration = self.excel_oracle.calibrate(
                paths['source'], paths['reference'],
                paths['cases'], spec['case_id'])
            _require(calibration.get('schema') ==
                     'cua-sec-integrated-train-oracle-calibration-v1' and
                     calibration.get('unsolved_seed_rejected') is True and
                     calibration.get('positive_reference_passed') is True and
                     calibration.get('source_counterfactual_profiles') == 2,
                     'single_account_excel_oracle_not_calibrated')

    def _freeze_ppt_baseline(self, candidate: Path) -> dict:
        if self.source_profile != 'transfer_wdi_four_target_train':
            return ppt_verify.freeze(candidate, self.case,
                                     office_web_normalized=True)
        # Reserve-source validation reads pinned evidence beside the deck.
        # Downloads remain separate from evaluator source/gold. Revalidate
        # trusted source bytes in a temporary evaluator-only context; the
        # unchanged verifier freezes exactly the original candidate bytes.
        source_dir = self.paths['source'].parent
        context = (
            ('source-snapshot.private.json', 'source_snapshot_sha256'),
            ('source-provenance.private.json', 'source_provenance_sha256'),
            ('source-country.private.zip', 'source_zip_sha256'),
        )
        with tempfile.TemporaryDirectory(prefix='office-source-context-',
                                         dir=source_dir) as temporary:
            directory = Path(temporary)
            for name, field in context:
                source = source_dir / name
                _require(source.is_file() and not source.is_symlink(),
                         'single_account_ppt_source_context_invalid')
                raw = source.read_bytes()
                _require(_sha(raw) == self.case.get(field),
                         'single_account_ppt_source_context_changed')
                copy = directory / name
                copy.write_bytes(raw)
                copy.chmod(0o600)
            copy = directory / 'candidate.pptx'
            copy.write_bytes(candidate.read_bytes())
            copy.chmod(0o600)
            return ppt_verify.freeze(copy, self.case,
                                     office_web_normalized=True)

    def baseline(self, candidate: Path) -> dict:
        if self.spec['cell_id'] == 'powerpoint-web':
            try:
                semantic = semantic_source_equal(
                    self.paths['source'], candidate)
                self.ppt_oracle = self._freeze_ppt_baseline(candidate)
                neutral = ppt_verify.verify(
                    candidate, candidate, self.ppt_oracle)
            except (OSError, KeyError, TypeError, ValueError):
                raise SingleAccountPilotError(
                    'single_account_ppt_baseline_invalid') from None
            _require(semantic.get('slide_count') == 7 and
                     semantic.get('slide_text_equal') is True and
                     semantic.get('embedded_workbook_members_equal')
                         is True and
                     semantic.get('native_chart_cache_semantically_equal')
                         is True and
                     self._ppt_neutral(neutral),
                     'single_account_ppt_baseline_not_source_neutral')
            return {'source_equivalence_sha256':
                        _sha(_canonical(semantic)),
                    'neutral_score': 0}
        neutral = self.excel_oracle.neutral(
            self.paths['source'], candidate)
        _require(self._excel_neutral(neutral),
                 'single_account_excel_baseline_not_source_neutral')
        return {'source_equivalence_sha256':
                    _sha(_canonical(neutral)),
                'neutral_score': 0}

    @staticmethod
    def _ppt_neutral(value: object) -> bool:
        return (type(value) is dict and
                value.get('status') == 'scored' and
                value.get('score') == 0 and
                value.get('preservation_pass') is True and
                value.get('unexpected_parts') == [] and
                type(value.get('per_target')) is dict and
                value['per_target'] and
                all(row.get('changed') is False for row in
                    value['per_target'].values()))

    @staticmethod
    def _excel_neutral(value: object) -> bool:
        return (type(value) is dict and
                value.get('schema') ==
                    'cua-sec-integrated-train-neutral-v1' and
                value.get('equivalent') is True and
                value.get('structure_pass') is True and
                value.get('changed_cell_count') == 0 and
                type(value.get('cell_count')) is int and
                value['cell_count'] > 0)

    def saved(self, baseline: Path, candidate: Path) -> dict:
        if self.spec['cell_id'] == 'powerpoint-web':
            scored = ppt_verify.verify(
                baseline, candidate, self.ppt_oracle)
            _require(type(scored) is dict and
                     scored.get('status') == 'scored' and
                     scored.get('score') == 1 and
                     scored.get('target_correct') is True and
                     scored.get('preservation_pass') is True and
                     scored.get('unexpected_parts') == [],
                     'single_account_ppt_saved_positive_or_preservation_failed')
            return {'score': 1,
                    'verifier_result_sha256':
                        _sha(_canonical(scored)),
                    'target_count': len(scored['per_target'])}
        scored = self.excel_oracle.score(
            candidate, self.paths['source'],
            self.paths['cases'], self.spec['case_id'])
        _require(type(scored) is dict and
                 scored.get('schema') ==
                     'cua-sec-integrated-train-saved-score-v1' and
                 scored.get('artifact_pass') is True and
                 scored.get('candidate_sha256') ==
                     _sha(candidate.read_bytes()) and
                 scored.get('seed_sha256') ==
                     self.spec['source_ref']['sha256'] and
                 scored.get('checked_formula_targets', 0) >= 20 and
                 scored.get('source_counterfactual_profiles') == 2 and
                 scored.get('error_count') == 0,
                 'single_account_excel_saved_positive_or_preservation_failed')
        return {'score': 1,
                'verifier_result_sha256': _sha(_canonical(scored)),
                'target_count': scored['checked_formula_targets']}

    def reset(self, baseline: Path, candidate: Path) -> dict:
        if self.spec['cell_id'] == 'powerpoint-web':
            scored = ppt_verify.verify(
                baseline, candidate, self.ppt_oracle)
            _require(self._ppt_neutral(scored),
                     'single_account_ppt_reset_not_neutral')
        else:
            scored = self.excel_oracle.neutral(
                self.paths['source'], candidate)
            _require(self._excel_neutral(scored),
                     'single_account_excel_reset_not_neutral')
        return {'score': 0,
                'verifier_result_sha256': _sha(_canonical(scored))}


def inspect_manual_evidence(spec: dict, spec_raw: bytes,
                            evidence_path: Path, root: Path,
                            actor: dict, reset: dict,
                            paths: dict[str, Path], *,
                            evidence_schema: str = EVIDENCE_SCHEMA,
                            split: str = 'train',
                            additional_fields: frozenset[str] = frozenset(),
                            account_scope: str = DEDICATED_ACCOUNT_SCOPE
                            ) -> tuple[dict, dict, dict]:
    """Reuse exact folder, screenshot and download checks across splits."""
    evidence, _ = _json(evidence_path, root)
    _require(set(evidence) == ({'schema', 'spec_sha256', 'split',
                              'manual_gui', 'phases'} | additional_fields) and
             evidence['schema'] == evidence_schema and
             evidence['spec_sha256'] == _sha(spec_raw) and
             evidence['split'] == split and
             type(evidence['phases']) is dict and
             set(evidence['phases']) ==
                 {'before', 'saved', 'reset', 'cleanup'},
             'single_account_evidence_not_bound')
    gui = evidence['manual_gui']
    _require(account_scope in {DEDICATED_ACCOUNT_SCOPE, EXISTING_FOLDER_SCOPE} and
             (account_scope == DEDICATED_ACCOUNT_SCOPE or
              (split == 'train' and evidence_schema == FOLDER_EVIDENCE_SCHEMA)),
             'single_account_manual_scope_invalid')
    folder_mode = account_scope == EXISTING_FOLDER_SCOPE
    gui_fields = {
        'operator_reviewed', 'original_office_gui',
        'signed_in_dedicated_test_account', 'model_calls',
        'application_api_edits', 'actor_edit_url_sha256',
        'before_screenshot_ref', 'after_screenshot_ref'}
    if folder_mode:
        gui_fields.add('account_scope')
    _require(type(gui) is dict and set(gui) == gui_fields and
        gui['operator_reviewed'] is True and
        gui['original_office_gui'] is True and
        gui['signed_in_dedicated_test_account'] is (not folder_mode) and
        (not folder_mode or gui['account_scope'] == EXISTING_FOLDER_SCOPE) and
        gui['model_calls'] == 0 and
        gui['application_api_edits'] is False and
        gui['actor_edit_url_sha256'] ==
            actor['edit_url_sha256'],
        'single_account_manual_original_gui_evidence_missing')
    before_screen = _png(gui['before_screenshot_ref'], root)
    after_screen = _png(gui['after_screenshot_ref'], root)
    _require(before_screen != after_screen,
             'single_account_gui_before_after_same_frame')
    phase_files = {}
    times = []
    phase_times = {}
    used_downloads = set()
    evaluator_paths = {path.resolve() for path in paths.values()}
    for phase in ('before', 'saved', 'reset', 'cleanup'):
        entry = evidence['phases'][phase]
        expected_keys = ({'inventory_ref'} if phase == 'cleanup'
                         else {'inventory_ref', 'downloads'})
        _require(type(entry) is dict and
                 set(entry) == expected_keys,
                 'single_account_phase_shape_invalid')
        inventory_path, _ = _ref(entry['inventory_ref'], root,
                                 maximum=2_000_000)
        inventory, _ = _json(inventory_path, root)
        expected_items = ([] if phase == 'cleanup' else
                          [reset] if phase == 'reset' else [actor])
        _require(set(inventory) == {
            'schema', 'phase', 'account_principal_sha256',
            'folder_label_sha256', 'items', 'screenshot_ref',
            'operator_reviewed', 'observed_at_utc'} and
            inventory['schema'] == INVENTORY_SCHEMA and
            inventory['phase'] == phase and
            inventory['account_principal_sha256'] ==
                spec['account_principal_sha256'] and
            inventory['folder_label_sha256'] ==
                spec['folder_label_sha256'] and
            inventory['items'] == expected_items and
            inventory['operator_reviewed'] is True,
            'single_account_folder_inventory_not_one_current_item')
        _png(inventory['screenshot_ref'], root)
        observed = _time(inventory['observed_at_utc'])
        times.append(observed)
        phase_times[phase] = observed
        if phase == 'cleanup':
            continue
        refs = entry['downloads']
        _require(type(refs) is list and len(refs) == 2,
                 'single_account_two_downloads_required')
        first_path, first = _ref(refs[0], root)
        second_path, second = _ref(refs[1], root)
        _require(first_path != second_path and
                 first_path not in used_downloads and
                 second_path not in used_downloads and
                 first_path.resolve() not in evaluator_paths and
                 second_path.resolve() not in evaluator_paths and
                 'packages' not in first_path.parts and
                 'packages' not in second_path.parts and
                 first == second and
                 first_path.suffix == second_path.suffix ==
                    ('.pptx' if spec['cell_id'] ==
                     'powerpoint-web' else '.xlsx'),
                 'single_account_exact_double_download_changed')
        used_downloads.update((first_path, second_path))
        phase_files[phase] = first_path
    _require(times == sorted(times) and
             len(set(times)) == len(times),
             'single_account_phase_order_invalid')
    return evidence, phase_files, {'before_screenshot_sha256': before_screen,
                                   'after_screenshot_sha256': after_screen,
                                   'phase_times': phase_times}


def audit(spec_path: Path, evidence_path: Path, out_dir: Path, *,
          work_root: Path, scorer_factory=None,
          account_scope: str = DEDICATED_ACCOUNT_SCOPE) -> dict:
    """Inspect local private evidence only; no Microsoft/provider capability."""
    root = Path(work_root).resolve()
    spec, spec_raw = _json(spec_path, root)
    fields = {'schema', 'cell_id', 'split', 'task_id',
              'package_sha256', 'task_ref', 'source_ref',
              'cases_ref', 'case_id', 'reference_ref',
              'account_principal_sha256', 'folder_label_sha256',
              'actor_item', 'reset_item', 'official_final_credit'}
    _require(set(spec) == fields and spec['schema'] == SPEC_SCHEMA and
             spec['cell_id'] in {'powerpoint-web', 'excel-web'} and
             spec['split'] == 'train' and
             spec['official_final_credit'] == 0 and
             type(spec['task_id']) is str and
             type(spec['package_sha256']) is str and
             _HEX.fullmatch(spec['package_sha256']) and
             all(type(spec[key]) is str and _HEX.fullmatch(spec[key])
                 for key in ('account_principal_sha256',
                             'folder_label_sha256')),
             'single_account_train_spec_invalid')
    paths = {}
    for key in ('task', 'source'):
        paths[key], _ = _ref(spec[key + '_ref'], root)
    task_record, _ = _json(paths['task'], root)
    _require(_train_package_path(paths['task'], spec['cell_id']) and
             paths['task'].parent.name == spec['task_id'] and
             task_record.get('split') == paths['task'].parent.parent.name,
             'single_account_train_package_path_required')
    if spec['cell_id'] == 'powerpoint-web':
        _require(spec['cases_ref'] is None and
                 spec['case_id'] is None and
                 spec['reference_ref'] is None and
                 paths['source'] ==
                     paths['task'].parent / 'source.pptx',
                 'single_account_ppt_source_boundary_invalid')
    else:
        _require(type(spec['case_id']) is str and
                 spec['case_id'] and
                 paths['source'] ==
                     paths['task'].parent / 'actor.xlsx',
                 'single_account_excel_source_boundary_invalid')
        paths['cases'], _ = _ref(spec['cases_ref'], root,
                                maximum=8_000_000)
        paths['reference'], _ = _ref(spec['reference_ref'], root)
    actor = _item(spec['actor_item'], spec['cell_id'])
    reset = _item(spec['reset_item'], spec['cell_id'])
    _require(actor != reset and
             actor['sourcedoc_sha256'] !=
                 reset['sourcedoc_sha256'],
             'single_account_reset_copy_not_distinct')
    _require(account_scope in {DEDICATED_ACCOUNT_SCOPE, EXISTING_FOLDER_SCOPE},
             'single_account_manual_scope_invalid')
    folder_mode = account_scope == EXISTING_FOLDER_SCOPE
    evidence, phase_files, _gui = inspect_manual_evidence(
        spec, spec_raw, evidence_path, root, actor, reset, paths,
        evidence_schema=FOLDER_EVIDENCE_SCHEMA if folder_mode else EVIDENCE_SCHEMA,
        account_scope=account_scope)
    fake_test_scorer = scorer_factory is not None
    scorer = (scorer_factory(spec, paths) if fake_test_scorer else
              OfficeTrainScorer(spec, paths))
    baseline = scorer.baseline(phase_files['before'])
    saved = scorer.saved(phase_files['before'],
                         phase_files['saved'])
    neutral = scorer.reset(phase_files['before'],
                           phase_files['reset'])
    _require(baseline['neutral_score'] == 0 and
             saved['score'] == 1 and neutral['score'] == 0,
             'single_account_saved_or_reset_score_invalid')
    out_dir = Path(out_dir).absolute()
    _require(not out_dir.exists() and not out_dir.is_symlink() and
             out_dir.parent.resolve().is_relative_to(root),
             'single_account_fresh_private_audit_output_required')
    out_dir.mkdir(mode=0o700)
    receipt = {
        'schema': PRIVATE_RECEIPT_SCHEMA,
        'status': ('passed_fake_test_control_only' if fake_test_scorer else
                   'passed_manual_train_development_control'),
        'cell_id': spec['cell_id'],
        'task_id': spec['task_id'],
        'package_sha256': spec['package_sha256'],
        'spec_sha256': _sha(spec_raw),
        'evidence_sha256': _sha(evidence_path.read_bytes()),
        'source_sha256': spec['source_ref']['sha256'],
        'verifier_source_sha256': _verifier_source_hash(
            spec['cell_id']),
        'before_sha256': _sha(phase_files['before'].read_bytes()),
        'saved_sha256': _sha(phase_files['saved'].read_bytes()),
        'reset_sha256': _sha(phase_files['reset'].read_bytes()),
        'source_equivalence_sha256':
            baseline['source_equivalence_sha256'],
        'saved_verifier_sha256': saved['verifier_result_sha256'],
        'reset_verifier_sha256': neutral['verifier_result_sha256'],
        'download_count': 6,
        'folder_inventory_count': 4,
        'dedicated_folder_empty_after_cleanup': True,
        'operator_reviewed_inventory_only': True,
        'account_wide_acl_independently_verified': False,
        'one_file_permission_independently_verified': False,
        'download_item_identity_independently_verified': False,
        'original_software_gui_operator_reviewed': True,
        'independent_scorer_executed': not fake_test_scorer,
        'model_calls': 0,
        'selection_or_final_admitted': False,
        'official_final_credit': 0,
    }
    if folder_mode:
        receipt.update(account_scope=EXISTING_FOLDER_SCOPE,
                       dedicated_test_account_operator_asserted=False,
                       automated_model_scope_qualified=False,
                       selection_or_final_admitted=False)
        if not fake_test_scorer:
            receipt['status'] = 'passed_manual_folder_train_development_control'
    receipt_sha = _write_new(out_dir / 'receipt.private.json',
                             _canonical(receipt))
    public = {'schema': PUBLIC_SCHEMA,
              'status': ('fake_test_control_only' if fake_test_scorer else
                         'manual_train_development_control_only'),
              'cell_id': spec['cell_id'],
              'receipt_sha256': receipt_sha,
              'saved_positive': True,
              'fresh_reset_neutral': True,
              'independent_scorer_executed': not fake_test_scorer,
              'download_pairs': 3,
              'account_wide_acl_independently_verified': False,
              'download_item_identity_independently_verified': False,
              'model_calls': 0,
              'selection_or_final_admitted': False,
              'official_final_credit': 0}
    if folder_mode:
        public.update(account_scope=EXISTING_FOLDER_SCOPE,
                      dedicated_test_account_operator_asserted=False,
                      automated_model_scope_qualified=False)
        if not fake_test_scorer:
            public['status'] = 'manual_folder_train_development_control_only'
    return public
