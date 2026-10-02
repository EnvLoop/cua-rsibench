"""Pre-result manual Office selection/final controls under one test account.

This reuses the train pilot's private folder/screenshot/download checks. The
evaluator alone reads hidden WDI/SEC answers and scores saved OOXML. Direct
document navigation is operator-recorded and restricted to this task folder,
actor item and reset item. No cloud/browser/model call occurs in this auditor.
The account-wide isolation boundary remains unverified and official credit 0.
"""

from __future__ import annotations

from pathlib import Path
import json
import re
from urllib.parse import parse_qsl, urlsplit

from ppt_wdi_factory import plan as ppt_plan, verify as ppt_verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal
from tools import office_single_account_train_pilot_v1 as common
from tools import sec_excel_web_train_oracle_v1 as excel_oracle


SPEC_SCHEMA = 'cua-office-single-account-candidate-spec-v1'
EVIDENCE_SCHEMA = 'cua-office-single-account-candidate-evidence-v1'
TRACE_SCHEMA = 'cua-office-single-account-navigation-trace-v1'
PRIVATE_RECEIPT_SCHEMA = 'cua-office-single-account-candidate-control-v1'
PUBLIC_SCHEMA = 'cua-office-single-account-candidate-public-v1'
EXCEL_TASK_SCHEMA = 'cua-office-excel-integrated-candidate-package-v1'
_DOC = re.compile(
    r'/personal/[0-9A-Fa-f]{16}/_layouts/15/Doc\.aspx\Z')
_SOURCE_DOC = re.compile(
    r'\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}\Z')
_NAME = re.compile(
    r'EL-(PPT|Excel)-(Selection|Final)-[A-Za-z0-9._-]{1,100}\.(pptx|xlsx)\Z')


class CandidateControlError(common.SingleAccountPilotError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise CandidateControlError(code)


def _item(value: object, cell_id: str, split: str) -> dict:
    _require(type(value) is dict and
             set(value) == {'edit_url', 'file_name'},
             'candidate_item_shape_invalid')
    parsed = urlsplit(value['edit_url'])
    try:
        port = parsed.port
    except ValueError:
        raise CandidateControlError(
            'candidate_document_url_invalid') from None
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(pairs)
    name = _NAME.fullmatch(value['file_name'])
    expected_app = 'PPT' if cell_id == 'powerpoint-web' else 'Excel'
    expected_split = 'Selection' if split == 'selection' else 'Final'
    expected_ext = 'pptx' if cell_id == 'powerpoint-web' else 'xlsx'
    _require(parsed.scheme == 'https' and
             parsed.hostname == 'onedrive.live.com' and
             parsed.username is None and parsed.password is None and
             port is None and not parsed.fragment and
             _DOC.fullmatch(parsed.path) and
             len(pairs) == len(query) and
             set(query) in ({'sourcedoc', 'file', 'action'},
                            {'sourcedoc', 'file', 'action',
                             'mobileredirect'}) and
             type(query.get('sourcedoc')) is str and
             _SOURCE_DOC.fullmatch(query['sourcedoc']) and
             query.get('file') == value['file_name'] and
             query.get('action') in ('default', 'edit') and
             query.get('mobileredirect') in (None, 'true') and
             name is not None and
             name.groups() == (expected_app, expected_split,
                               expected_ext) and
             not re.search(r'(gold|answer|reference)',
                           value['file_name'], re.IGNORECASE),
             'candidate_direct_document_url_or_name_invalid')
    return {'file_name': value['file_name'],
            'edit_url_sha256': common._sha(value['edit_url']),
            'sourcedoc_sha256': common._sha(query['sourcedoc'])}


def _folder_url(value: object) -> str:
    _require(type(value) is str and len(value) <= 2048,
             'candidate_folder_url_invalid')
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        raise CandidateControlError(
            'candidate_folder_url_invalid') from None
    _require(parsed.scheme == 'https' and
             parsed.hostname == 'onedrive.live.com' and
             parsed.username is None and parsed.password is None and
             port is None and not parsed.fragment and
             not parsed.path.endswith('/_layouts/15/Doc.aspx'),
             'candidate_folder_url_invalid')
    return value


def _exact_case(path: Path, split: str, task_id: str) -> dict:
    try:
        rows = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CandidateControlError(
            'candidate_excel_case_invalid_json') from None
    expected = ('selection_candidate' if split == 'selection' else
                'final_candidate')
    _require(type(rows) is list and len(rows) == 1 and
             type(rows[0]) is dict and
             rows[0].get('split') == expected and
             rows[0].get('case_id') == task_id and
             type(rows[0].get('source_package')) is dict and
             rows[0]['source_package'].get('schema') ==
                'sec-integrated-source-package-v1',
             'candidate_excel_case_split_or_source_invalid')
    return rows[0]


class CandidateScorer:
    """One WDI PPT or SEC integrated Excel candidate, evaluator-side only."""

    def __init__(self, spec: dict, paths: dict):
        self.spec = spec
        self.paths = paths
        self.oracle = None
        self.task = None
        if spec['cell_id'] == 'powerpoint-web':
            task = json.loads(paths['task'].read_bytes())
            expected_keys = (['summary', 'ledger', 'interpretation']
                             if spec['split'] == 'selection' else
                             ppt_verify.FINAL_TARGETS.get(
                                 task.get('workflow'),
                                 ppt_verify.DEFAULT_FINAL_TARGETS))
            _require(task.get('schema') == ppt_plan.SCHEMA and
                     task.get('split') == spec['split'] and
                     task.get('task_id') == spec['task_id'] and
                     task.get('official_final_credit') == 0 and
                     task.get('workflow') in (
                         ppt_plan.WORKFLOWS[:8] if
                         spec['split'] == 'selection' else
                         ppt_plan.WORKFLOWS) and
                     task.get('target_keys') == expected_keys and
                     type(task.get('source_group')) is str and
                     type(task.get('template_group')) is str and
                     common._sha(task.get('source_group', '')) ==
                         spec['source_group_sha256'] and
                     common._sha(task.get('template_group', '')) ==
                         spec['template_group_sha256'],
                     'candidate_ppt_source_or_template_split_changed')
            try:
                ppt_verify.freeze(paths['source'], task)
            except (OSError, KeyError, TypeError, ValueError):
                raise CandidateControlError(
                    'candidate_ppt_wdi_source_invalid') from None
            self.task = task
        else:
            task = json.loads(paths['task'].read_bytes())
            expected = ('selection_candidate' if
                        spec['split'] == 'selection' else
                        'final_candidate')
            _require(type(task) is dict and
                     set(task) == {
                         'schema', 'split', 'task_id', 'actor_task',
                         'workflow', 'source_group',
                         'template_group', 'actor_xlsx_sha256',
                         'official_final_credit'} and
                     task['schema'] == EXCEL_TASK_SCHEMA and
                     task['split'] == expected and
                     task['task_id'] == spec['task_id'] and
                     type(task['actor_task']) is str and
                     task['actor_task'] and
                     task['workflow'] == 'sec-integrated' and
                     type(task['source_group']) is str and
                     type(task['template_group']) is str and
                     task['actor_xlsx_sha256'] ==
                         spec['source_ref']['sha256'] and
                     task['official_final_credit'] == 0 and
                     common._sha(task['source_group']) ==
                         spec['source_group_sha256'] and
                     common._sha(task['template_group']) ==
                         spec['template_group_sha256'],
                     'candidate_excel_integrated_source_or_split_changed')
            self.task = task
            self.case = _exact_case(
                paths['cases'], spec['split'], spec['case_id'])
            negative = excel_oracle.sec_verify(
                paths['source'], paths['source'], self.case)
            positive = excel_oracle.sec_verify(
                paths['reference'], paths['source'], self.case)
            expected_targets = (33 if spec['split'] == 'selection'
                                else 48)
            _require(type(negative) is dict and
                     negative.get('pass') is False and
                     type(positive) is dict and
                     positive.get('pass') is True and
                     positive.get('checked_targets') ==
                         expected_targets and
                     positive.get('counterfactual_profiles') == 2 and
                     positive.get('errors') == [],
                     'candidate_excel_positive_negative_calibration_failed')

    @staticmethod
    def _ppt_neutral(value: object) -> bool:
        return common.OfficeTrainScorer._ppt_neutral(value)

    @staticmethod
    def _excel_neutral(value: object) -> bool:
        return common.OfficeTrainScorer._excel_neutral(value)

    def baseline(self, candidate: Path) -> dict:
        if self.spec['cell_id'] == 'powerpoint-web':
            try:
                semantic = semantic_source_equal(
                    self.paths['source'], candidate)
                self.oracle = ppt_verify.freeze(
                    candidate, self.task,
                    office_web_normalized=True)
                neutral = ppt_verify.verify(
                    candidate, candidate, self.oracle)
            except (OSError, KeyError, TypeError, ValueError):
                raise CandidateControlError(
                    'candidate_ppt_baseline_invalid') from None
            _require(semantic.get('slide_count') == 7 and
                     semantic.get('slide_text_equal') is True and
                     semantic.get('embedded_workbook_members_equal')
                         is True and
                     semantic.get('native_chart_cache_semantically_equal')
                         is True and
                     self._ppt_neutral(neutral),
                     'candidate_ppt_baseline_not_source_neutral')
            return {'neutral_score': 0,
                    'source_equivalence_sha256':
                        common._sha(common._canonical(semantic))}
        neutral = excel_oracle.neutral(
            self.paths['source'], candidate)
        _require(self._excel_neutral(neutral),
                 'candidate_excel_baseline_not_source_neutral')
        return {'neutral_score': 0,
                'source_equivalence_sha256':
                    common._sha(common._canonical(neutral))}

    def saved(self, baseline: Path, candidate: Path) -> dict:
        if self.spec['cell_id'] == 'powerpoint-web':
            result = ppt_verify.verify(
                baseline, candidate, self.oracle)
            _require(result.get('status') == 'scored' and
                     result.get('score') == 1 and
                     result.get('target_correct') is True and
                     result.get('preservation_pass') is True and
                     result.get('unexpected_parts') == [] and
                     type(result.get('per_target')) is dict and
                     len(result['per_target']) ==
                         len(self.task['target_keys']),
                     'candidate_ppt_saved_target_or_preservation_failed')
            return {'score': 1,
                    'verifier_result_sha256':
                        common._sha(common._canonical(result))}
        result = excel_oracle.sec_verify(
            candidate, self.paths['source'], self.case)
        expected_targets = (33 if self.spec['split'] == 'selection'
                            else 48)
        _require(type(result) is dict and
                 result.get('pass') is True and
                 result.get('checked_targets') == expected_targets and
                 result.get('counterfactual_profiles') == 2 and
                 result.get('errors') == [],
                 'candidate_excel_saved_target_or_preservation_failed')
        return {'score': 1,
                'verifier_result_sha256':
                    common._sha(common._canonical(result))}

    def reset(self, baseline: Path, candidate: Path) -> dict:
        if self.spec['cell_id'] == 'powerpoint-web':
            result = ppt_verify.verify(
                baseline, candidate, self.oracle)
            _require(self._ppt_neutral(result),
                     'candidate_ppt_fresh_reset_not_neutral')
        else:
            result = excel_oracle.neutral(
                self.paths['source'], candidate)
            _require(self._excel_neutral(result),
                     'candidate_excel_fresh_reset_not_neutral')
        return {'score': 0,
                'verifier_result_sha256':
                    common._sha(common._canonical(result))}


def _trace(path_ref: dict, root: Path, spec: dict,
           actor: dict, reset: dict, phase_times: dict) -> str:
    trace_path, trace_raw = common._ref(
        path_ref, root, maximum=2_000_000)
    trace, _ = common._json(trace_path, root)
    _require(set(trace) == {
        'schema', 'split', 'task_id', 'browser_run_sha256',
        'account_principal_sha256', 'folder_label_sha256',
        'operator_reviewed', 'events'} and
        trace['schema'] == TRACE_SCHEMA and
        trace['split'] == spec['split'] and
        trace['task_id'] == spec['task_id'] and
        trace['browser_run_sha256'] ==
            spec['browser_run_sha256'] and
        trace['account_principal_sha256'] ==
            spec['account_principal_sha256'] and
        trace['folder_label_sha256'] ==
            spec['folder_label_sha256'] and
        trace['operator_reviewed'] is True and
        type(trace['events']) is list and
        len(trace['events']) == 6,
        'candidate_navigation_trace_not_bound')
    kinds = ('open_folder', 'open_actor', 'edit_actor',
             'save_actor', 'open_reset', 'finish_folder')
    urls = (spec['folder_url'], spec['actor_item']['edit_url'],
            spec['actor_item']['edit_url'],
            spec['actor_item']['edit_url'],
            spec['reset_item']['edit_url'], spec['folder_url'])
    times = []
    for row, kind, url in zip(trace['events'], kinds, urls):
        _require(type(row) is dict and
                 set(row) == {'kind', 'url', 'observed_at_utc',
                              'screenshot_ref', 'operator_reviewed'} and
                 row['kind'] == kind and row['url'] == url and
                 row['operator_reviewed'] is True,
                 'candidate_browser_left_exact_task_allowlist')
        common._png(row['screenshot_ref'], root)
        times.append(common._time(row['observed_at_utc']))
    _require(times == sorted(times) and
             len(set(times)) == len(times) and
             times[0] <= phase_times['before'] <= times[1] and
             times[1] < times[2] < times[3] <=
                 phase_times['saved'] and
             phase_times['saved'] < times[4] <=
                 phase_times['reset'] and
             phase_times['reset'] < times[5] <=
                 phase_times['cleanup'],
             'candidate_navigation_or_inventory_chronology_invalid')
    return common._sha(trace_raw)


def audit(spec_path: Path, evidence_path: Path, out_dir: Path, *,
          work_root: Path, scorer_factory=None) -> dict:
    """Read only local candidate-control evidence; never admit a final."""
    root = Path(work_root).resolve()
    spec, spec_raw = common._json(spec_path, root)
    fields = {'schema', 'cell_id', 'split', 'task_id',
              'package_sha256', 'task_ref', 'source_ref',
              'cases_ref', 'case_id', 'reference_ref',
              'source_group_sha256', 'template_group_sha256',
              'account_principal_sha256', 'folder_label_sha256',
              'browser_run_sha256', 'folder_url',
              'actor_item', 'reset_item', 'pre_result',
              'hidden_final_model_attempts', 'official_final_credit'}
    _require(set(spec) == fields and spec['schema'] == SPEC_SCHEMA and
             spec['cell_id'] in {'powerpoint-web', 'excel-web'} and
             spec['split'] in {'selection', 'final_candidate'} and
             type(spec['task_id']) is str and spec['task_id'] and
             all(type(spec[name]) is str and
                 common._HEX.fullmatch(spec[name]) for name in (
                     'package_sha256', 'source_group_sha256',
                     'template_group_sha256',
                     'account_principal_sha256',
                     'folder_label_sha256',
                     'browser_run_sha256')) and
             spec['pre_result'] is True and
             spec['hidden_final_model_attempts'] == 0 and
             spec['official_final_credit'] == 0,
             'candidate_pre_result_spec_or_split_invalid')
    _folder_url(spec['folder_url'])
    paths = {}
    for key in ('task', 'source'):
        paths[key], _ = common._ref(spec[key + '_ref'], root)
    parts = paths['task'].parts
    _require(paths['task'].name == 'task.private.json' and
             paths['task'].parent.name == spec['task_id'] and
             any(parts[index:index + 2] == ('packages', spec['split'])
                 for index in range(len(parts) - 1)) and
             not any(part.lower() in {'train', 'official'} for part
                     in parts),
             'candidate_task_package_split_path_invalid')
    if spec['cell_id'] == 'powerpoint-web':
        _require(spec['cases_ref'] is None and
                 spec['case_id'] is None and
                 spec['reference_ref'] is None and
                 paths['source'] ==
                     paths['task'].parent / 'source.pptx',
                 'candidate_ppt_local_source_boundary_invalid')
    else:
        _require(type(spec['case_id']) is str and
                 spec['case_id'] and
                 paths['source'] ==
                 paths['task'].parent / 'actor.xlsx',
                 'candidate_excel_local_source_boundary_invalid')
        paths['cases'], _ = common._ref(
            spec['cases_ref'], root, maximum=8_000_000)
        paths['reference'], _ = common._ref(
            spec['reference_ref'], root)
    actor = _item(spec['actor_item'],
                  spec['cell_id'], spec['split'])
    reset = _item(spec['reset_item'],
                  spec['cell_id'], spec['split'])
    _require(actor['sourcedoc_sha256'] !=
             reset['sourcedoc_sha256'] and
             spec['folder_url'] not in {
                 spec['actor_item']['edit_url'],
                 spec['reset_item']['edit_url']},
             'candidate_reset_or_folder_not_distinct')
    evidence, phase_files, gui = common.inspect_manual_evidence(
        spec, spec_raw, evidence_path, root, actor, reset,
        paths, evidence_schema=EVIDENCE_SCHEMA,
        split=spec['split'],
        additional_fields=frozenset({'browser_trace_ref'}))
    trace_sha = _trace(evidence['browser_trace_ref'], root,
                       spec, actor, reset, gui['phase_times'])
    fake_test_scorer = scorer_factory is not None
    scorer = (scorer_factory(spec, paths) if fake_test_scorer else
              CandidateScorer(spec, paths))
    baseline = scorer.baseline(phase_files['before'])
    saved = scorer.saved(phase_files['before'],
                         phase_files['saved'])
    reset_result = scorer.reset(phase_files['before'],
                                phase_files['reset'])
    _require(baseline['neutral_score'] == 0 and
             saved['score'] == 1 and
             reset_result['score'] == 0,
             'candidate_saved_or_reset_control_failed')
    out_dir = Path(out_dir).absolute()
    _require(not out_dir.exists() and not out_dir.is_symlink() and
             out_dir.parent.resolve().is_relative_to(root),
             'candidate_fresh_private_output_required')
    out_dir.mkdir(mode=0o700)
    receipt = {
        'schema': PRIVATE_RECEIPT_SCHEMA,
        'status': ('fake_candidate_test_only' if fake_test_scorer else
                   'passed_pre_result_manual_candidate_control'),
        'cell_id': spec['cell_id'], 'split': spec['split'],
        'task_id': spec['task_id'],
        'package_sha256': spec['package_sha256'],
        'source_group_sha256': spec['source_group_sha256'],
        'template_group_sha256': spec['template_group_sha256'],
        'browser_run_sha256': spec['browser_run_sha256'],
        'spec_sha256': common._sha(spec_raw),
        'evidence_sha256': common._sha(
            evidence_path.read_bytes()),
        'navigation_trace_sha256': trace_sha,
        'source_sha256': spec['source_ref']['sha256'],
        'candidate_auditor_source_sha256': common._sha(
            Path(__file__).read_bytes()),
        'verifier_source_sha256': common._verifier_source_hash(
            spec['cell_id']),
        'before_sha256': common._sha(
            phase_files['before'].read_bytes()),
        'saved_sha256': common._sha(
            phase_files['saved'].read_bytes()),
        'reset_sha256': common._sha(
            phase_files['reset'].read_bytes()),
        'source_equivalence_sha256':
            baseline['source_equivalence_sha256'],
        'saved_verifier_sha256': saved['verifier_result_sha256'],
        'reset_verifier_sha256':
            reset_result['verifier_result_sha256'],
        'download_count': 6,
        'folder_inventory_count': 4,
        'operator_reviewed_navigation_only': True,
        'account_wide_acl_independently_verified': False,
        'fresh_browser_sandbox_independently_verified': False,
        'download_item_identity_independently_verified': False,
        'common_six_cell_freeze_verified': False,
        'required_selection_controls_per_cell': 20,
        'required_final_controls_per_cell': 100,
        'full_cell_denominator_completed': False,
        'independent_scorer_executed': not fake_test_scorer,
        'model_calls': 0,
        'official_selection_credit': 0,
        'official_final_credit': 0,
        'official_final_admitted': False,
    }
    receipt_sha = common._write_new(
        out_dir / 'candidate-control.private.json',
        common._canonical(receipt))
    return {'schema': PUBLIC_SCHEMA,
            'status': ('fake_candidate_test_only' if
                       fake_test_scorer else
                       'pre_result_candidate_control_only'),
            'cell_id': spec['cell_id'],
            'split': spec['split'],
            'receipt_sha256': receipt_sha,
            'saved_known_positive': True,
            'fresh_reset_neutral': True,
            'operator_reviewed_navigation_only': True,
            'account_wide_acl_independently_verified': False,
            'fresh_browser_sandbox_independently_verified': False,
            'common_six_cell_freeze_verified': False,
            'full_cell_denominator_completed': False,
            'independent_scorer_executed': not fake_test_scorer,
            'model_calls': 0,
            'official_selection_credit': 0,
            'official_final_admitted': False,
            'official_final_credit': 0}


def preserve_invalid(spec_path: Path, evidence_path: Path,
                     out_dir: Path, *, work_root: Path,
                     reason_type: str, reason_code: str | None) -> dict:
    """Keep a failed per-ID control visible without inventing a score."""
    root = Path(work_root).resolve()
    out_dir = Path(out_dir).absolute()
    _require(not out_dir.exists() and not out_dir.is_symlink() and
             out_dir.parent.resolve().is_relative_to(root) and
             type(reason_type) is str and reason_type,
             'candidate_invalid_private_output_required')
    refs = {}
    for label, path in (('spec', spec_path),
                        ('evidence', evidence_path)):
        try:
            raw = common._private(path, root,
                                   maximum=2_000_000)
        except common.SingleAccountPilotError:
            raw = None
        refs[label + '_sha256'] = (
            common._sha(raw) if raw is not None else None)
    out_dir.mkdir(mode=0o700)
    receipt = {
        'schema': PRIVATE_RECEIPT_SCHEMA,
        'status': 'invalid_pre_result_candidate_control',
        'spec_sha256': refs['spec_sha256'],
        'evidence_sha256': refs['evidence_sha256'],
        'reason_type': reason_type,
        'reason_code': reason_code[:256] if
            type(reason_code) is str else None,
        'model_calls': 0,
        'official_selection_credit': 0,
        'official_final_credit': 0,
        'official_final_admitted': False,
    }
    digest = common._write_new(
        out_dir / 'invalid.private.json',
        common._canonical(receipt))
    return {'status': 'invalid_pre_result_candidate_control',
            'private_failure_sha256': digest,
            'official_selection_credit': 0,
            'official_final_credit': 0}
