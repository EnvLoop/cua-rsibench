"""Original selection20 reference controls; no paid/model/final authority.

The original V15 runtime, 146-file binding, V20 action wrappers and original
selection oracle stay frozen. Root reviews this separate controller explicitly.
"""
from __future__ import annotations
import argparse
import asyncio
import csv
from hashlib import sha256
import json
from io import StringIO
from pathlib import Path
import time
from types import SimpleNamespace
from urllib.parse import urlsplit
from . import v066_uniform_task_runtime_v15 as world
from . import v066_uniform_model_workers_v15 as models
from . import v066_uniform_train_qualification_v15 as train
from . import v066_uniform_reference_controls_v20 as reference
from . import selection_worker_v066 as selection
from . import selection_oracle_v066 as oracle
from . import verify
from cursibench import native_surface_guard_policy_v1 as policy

SCHEMA = 'gitlab-original-selection20-reference-authority-v1'
MODES = (('baseline', 0.0), ('positive', 1.0), ('wrong_variant', 0.0))
require = world.require
private = models.private_json


def ref(path):
    path = Path(path).resolve()
    require(path.is_file() and not path.is_symlink() and not path.stat().st_mode & 0o077,
            'selection_private_ref_unsafe')
    return {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}


def source_binding():
    root = Path(__file__).resolve().parents[1]
    names = ('gitlab_world/v066_selection_reference_controls_v1.py',
             'tests/test_gitlab_selection_reference_controls_v1.py',
             'gitlab_world/v066_uniform_reference_controls_v20.py')
    value = {'schema': 'gitlab-selection20-reference-controller-source-v1',
             'native_binding_sha256': models.public_binding()['binding_sha256'],
             'source_sha256s': {name: sha256((root/name).read_bytes()).hexdigest() for name in names},
             'original_runtime_actor_guard_oracle_budgets_unchanged': True,
             'model_lane_authority': False, 'formal_admissions': 0}
    return value | {'binding_sha256': models.common.digest(models.common.canonical(value))}


def _reset_proof(native):
    """Reopen the original complete SQL/Git/process restoration witnesses."""
    before = private(native/'original-before.private.json')
    resumed = private(native/'original-resumed.private.json')
    require(resumed['same_identity'] is True and resumed['healthy'] is True and
            resumed['exact_business_snapshot'] is True and resumed['snapshot'] == before['snapshot'] and
            len(before['full_git_trees']) == len(resumed['full_git_trees']) == 33 and
            world.cold.tree_digests(before['full_git_trees']) == world.cold.tree_digests(resumed['full_git_trees']),
            'selection_original_sql_full_git_not_restored')
    for group in ('protected', 'seed'):
        require(world.cold.source.private(native/f'{group}-before.private.json') ==
                world.cold.source.private(native/f'{group}-exit.private.json'), 'selection_protected_seed_changed')
    require(private(native/'parent-teardown.private.json')['owned_parent_absent'] is True,
            'selection_owned_parent_remains')
    lifecycle = private(native/'owned-lifecycle-end.private.json')
    require(lifecycle['seconds_limit'] == 1200 and lifecycle['within_limit'] is True and
            0 <= lifecycle['elapsed_seconds'] <= 1200 and
            lifecycle['ended_monotonic'] - lifecycle['started_monotonic'] == lifecycle['elapsed_seconds'],
            'selection_original_owned_lifecycle_budget_changed')
    for index in (0, 1):
        teardown = private(native/f'cycle-{index}-teardown.private.json')
        require(all(teardown[key] is True for key in
                    ('owned_container_absent', 'owned_overlay_mounts_absent', 'owned_vm_subtree_absent')),
                'selection_owned_reset_resources_remain')
        state = private(native/f'cycle-{index}-state.private.json')
        attrs = private(native/f'cycle-{index}-native-attributes.private.json')
        world.cold.validate_attributes(attrs, started_at=state['StartedAt'])
        witness = world.cold.profile.validate_witness(
            world.cold.source.private(native/f'cycle-{index}-effective-wait-witness.private.jsonl'),
            started_at=state['StartedAt'])
        require(witness == private(native/f'cycle-{index}-effective-wait-result.private.json') and
                private(native/f'cycle-{index}-snapshot.private.json') == before['snapshot'],
                'selection_reset_profile_or_snapshot_changed')


def _source_prerequisite(path, expected, plan_path, binding_path):
    review = private(path, expected); root = Path(path).parent
    require(review.get('schema') == 'gitlab-current-source-readonly-root-visual-review-v1' and
            all(review.get(key) is True for key in (
                'actual_release_policy_and_csv_and_completed_activity_frames_viewed',
                'all_three_source_readability_checks_passed', 'both_owned_generations_and_parent_absent',
                'current_code_source146_unchanged', 'no_actor_business_inputs_or_model_tinker_calls',
                'original_container_sql_and_all33_git_projects_restored')) and
            review.get('full_task_qualification_or_final_admissions_claimed') is False,
            'selection_current_source_readability_review_required')
    intent = private(root/'intent.private.json')
    require(intent['plan_ref'] == ref(plan_path) and intent['binding_ref'] == ref(binding_path) and
            intent['source_map'] == world.source_hashes() and intent['business_inputs_authorized'] is False and
            intent['model_calls'] == intent['tinker_calls'] == intent['automatic_restarts'] == 0,
            'selection_source_reading_epoch_or_authority_changed')
    names = {'release-policy.final.private.png', 'asset-register.final.private.png',
             'activity-after-bounded-wait.private.png'}
    require(set(review['source_frames']) == names, 'selection_source_frame_roster_changed')
    require(root.is_dir() and not root.is_symlink() and not root.stat().st_mode & 0o077,
            'selection_private_source_directory_required')
    for name, digest in review['source_frames'].items():
        image = root/name
        require(image.is_file() and not image.is_symlink() and
                sha256(image.read_bytes()).hexdigest() == digest, 'selection_reviewed_source_pixels_changed')
    result = private(root/'readonly-source-result.private.json')
    require(result['business_state_unchanged'] is True and result['task_mutation_inputs'] ==
            result['model_calls'] == result['tinker_calls'] == result['qualification_credit'] == 0 and
            set(result['readability_checks']) == {'release-policy', 'asset-register', 'active-issue'} and
            all(result['readability_checks'].values()), 'selection_source_reading_result_changed')
    for label in result['readability_checks']:
        require(private(root/f'{label}.readiness.private.json')['required_strings_visible'] is True,
                'selection_source_reading_positive_witness_missing')
    _reset_proof(root/'native.private/native-runtime')


def review_contract(*, plan_path, binding_path, train_accept_path, train_accept_sha256,
                    source_review_path, source_review_sha256, output):
    """Saved prerequisite audit and metadata only; no selection body is opened."""
    plan, _ = world.checked_plan(Path(plan_path))
    binding = models.validate_binding(private(binding_path))
    require(plan['source_sha256s'] == binding['source_sha256s'] and len(binding['source_sha256s']) == 146,
            'selection_original146_source_changed')
    accepted = private(train_accept_path, train_accept_sha256)
    require(accepted['accepted'] is True and accepted['historical_credit'] == accepted['model_calls'] == 0 and
            accepted['plan_sha256'] == ref(plan_path)['sha256'] and
            accepted['source_sha256s'] == plan['source_sha256s'] and
            Path(accepted['binding_path']).resolve() == Path(binding_path).resolve(),
            'selection_current_train_acceptance_required')
    actual = train.audit(plan_path=Path(plan_path), binding_path=Path(binding_path),
                         out=Path(accepted['qualification_out']))
    require(actual['result_sha256'] == accepted['result_sha256'], 'selection_train_raw_proof_changed')
    _source_prerequisite(source_review_path, source_review_sha256, plan_path, binding_path)
    rows = plan['rosters']['selection']
    require(len(rows) == len({row['task_id'] for row in rows}) == 20 and
            not ({row['task_id'] for row in rows} &
                 {row['task_id'] for key in ('train', 'final_candidate_unsealed') for row in plan['rosters'][key]}),
            'selection_exact_original20_required')
    return {'schema': SCHEMA, 'plan_ref': ref(plan_path), 'native_binding_ref': ref(binding_path),
            'train_accept_ref': {'path': str(Path(train_accept_path).resolve()), 'sha256': train_accept_sha256},
            'source_review_ref': {'path': str(Path(source_review_path).resolve()), 'sha256': source_review_sha256},
            'controller_binding': source_binding(), 'ordered_selection20': rows,
            'ordered_roster_sha256': models.common.digest(models.common.canonical(rows)),
            'selection_families': sorted(oracle.SELECTION_FAMILIES),
            'modes': [[mode, score] for mode, score in MODES], 'output_root': str(Path(output).resolve()),
            'underlying_native_phase': 'train-qualification',
            'explicit_selection_only_authority': True, 'final_task_substitution_authorized': False,
            'paid_sampler_or_model_lane_authorized': False, 'automatic_restart_authorized': False,
            'old_control_credit': 0, 'formal_admissions': 0, 'model_calls': 0}


def _check_authority(review_path, review_sha256):
    value = private(review_path, review_sha256)
    require(value.get('schema') == SCHEMA and value.get('explicit_selection_only_authority') is True,
            'selection_explicit_root_authority_required')
    expected = review_contract(plan_path=value['plan_ref']['path'], binding_path=value['native_binding_ref']['path'],
        train_accept_path=value['train_accept_ref']['path'], train_accept_sha256=value['train_accept_ref']['sha256'],
        source_review_path=value['source_review_ref']['path'], source_review_sha256=value['source_review_ref']['sha256'],
        output=value['output_root'])
    require(value == expected, 'selection_exact_root_review_changed')
    return value


def _budget(active):
    require(active.step < 90 and active.guard.lease is not None and
            active.guard.clock() < active.guard.lease['expires_at'], 'selection_original_actor_budget_expired')


class _ReferenceActive:
    """Same V20 wrappers; a conservative controller-side original budget cap."""
    def __init__(self, active):
        self.original = active
        class Guard:
            def __getattr__(self, name): return getattr(active.guard, name)
            async def dispatch(self, action):
                _budget(active)
                return await active.guard.dispatch(action)
        self.guard = Guard()
    def __getattr__(self, name): return getattr(self.original, name)


def _owned_uri(active, relative):
    expected = urlsplit(world.runtime.BASE+'/'+active.project_path+relative)
    current = urlsplit(active.page.url)
    require(not current.username and not current.password and
            (current.scheme, current.netloc, current.path) == (expected.scheme, expected.netloc, expected.path),
            'selection_current_original_project_uri_required')


async def _readable(active, locator, expected, *, table=False, target_row=None, relative=None):
    deadline = min(time.monotonic()+30, active.guard.lease['expires_at'])
    url = active.page.url; previous = None; stable = None
    while time.monotonic() < deadline:
        if relative is not None: _owned_uri(active, relative)
        require(active.page.url == url, 'selection_source_document_changed')
        async def sample():
            if await locator.count() != 1 or not await locator.is_visible(): return None
            value = await locator.inner_text()
            if not all(text in value for text in expected): return None
            if table:
                headers = [value.strip() for value in await locator.locator('tr').first.locator('th,td').all_text_contents()]
                if headers != ['asset_id', 'cve_id', 'vendor', 'product', 'site', 'disposition']: return None
                if await locator.locator('tbody tr').count() == 0: return None
                rows = locator.locator('tbody tr')
                actual_rows = []
                for index in range(await rows.count()):
                    cells = [text.strip() for text in await rows.nth(index).locator('th,td').all_text_contents()]
                    if len(cells) != 6 or not all(cells): return None
                    actual_rows.append(cells)
                if target_row is not None and actual_rows.count(target_row) != 1: return None
            if await locator.locator('.gl-skeleton-loader,[data-testid*="skeleton"],.gl-spinner').filter(visible=True).count(): return None
            box = await locator.bounding_box()
            if not box or box['width'] <= 0 or box['height'] <= 0: return None
            return value, box
        current = await asyncio.wait_for(sample(), max(.001, deadline-time.monotonic()))
        if relative is not None: _owned_uri(active, relative)
        require(active.page.url == url, 'selection_source_document_changed')
        now = time.monotonic()
        if current is not None and current == previous and stable is not None and now-stable >= .1: return
        if current != previous: previous, stable = current, now if current is not None else None
        await asyncio.sleep(min(.05, max(0, deadline-time.monotonic())))
    raise ValueError('selection_source_content_not_stable_within_original_budget')


async def _issue_readable(active, page, heading, cve):
    # These explicit states are visible in the retained native issue frame;
    # section headings alone do not establish asynchronous widget completion.
    await _readable(active, page.locator('body'), [heading, cve, 'Activity',
        'No child items are currently assigned.', "Link items together to show that they're related.",
        'added', 'labels'])


async def workflow(active, task, mode, folder):
    require(task['partition'] == 'selection' and task['template_group'] in oracle.SELECTION_FAMILIES,
            'selection_only_original_recipe_required')
    proxy = _ReferenceActive(active); page = reference.Page(proxy)
    project, progress = verify._context(task); base = world.runtime.BASE+'/'+project['full_path']
    await page.goto(base+'/-/blob/main/security/release-policy.md', wait_until='domcontentloaded', timeout=90000)
    _owned_uri(active, '/-/blob/main/security/release-policy.md')
    await _readable(active, page.locator('body'), [project['policy']['milestone_title'], project['principals']['oncall'], task['oracle']['cve']],
                    relative='/-/blob/main/security/release-policy.md')
    await page.screenshot(path=str(folder/'policy.png'), full_page=True)
    await page.goto(base+'/-/blob/main/security/kev-register.csv', wait_until='domcontentloaded', timeout=90000)
    _owned_uri(active, '/-/blob/main/security/kev-register.csv')
    original_rows = list(csv.DictReader(StringIO(project['files']['security/kev-register.csv'])))
    target_rows = [row for row in original_rows if row['asset_id'] == project['asset_id']+'-1' and
                   row['cve_id'] == task['oracle']['cve']]
    require(len(target_rows) == 1, 'selection_original_public_asset_row_required')
    target_row = [target_rows[0][key] for key in ('asset_id', 'cve_id', 'vendor', 'product', 'site', 'disposition')]
    await _readable(active, page.get_by_role('table'), [], table=True, target_row=target_row,
                    relative='/-/blob/main/security/kev-register.csv')
    _owned_uri(active, '/-/blob/main/security/kev-register.csv')
    await page.screenshot(path=str(folder/'asset-register.png'), full_page=True)
    if mode == 'baseline': return
    wrong = mode == 'wrong_variant'; family = task['template_group']
    if family in ('issue_owner_transfer', 'false_positive_closure'):
        key = ('historical_duplicate' if wrong else 'active') if family == 'issue_owner_transfer' else ('active' if wrong else 'historical_duplicate')
        await page.goto(base+'/-/issues/'+str(progress['issue_iids'][key]), wait_until='domcontentloaded', timeout=90000)
        _owned_uri(active, '/-/issues/'+str(progress['issue_iids'][key]))
        heading = 'Active remediation:' if key == 'active' else 'Historical verification:'
        await _issue_readable(active, page, heading, task['oracle']['cve'])
        await page.screenshot(path=str(folder/'issue-before.png'), full_page=True)
        if family == 'false_positive_closure':
            await page.get_by_role('button', name='Close issue', exact=True).click()
            await _readable(active, page.locator('body'), [heading, 'Closed'])
        else:
            section = page.locator('[data-testid="work-item-assignees"]')
            await section.locator('[data-testid="edit-button"]').click()
            await section.get_by_role('combobox').fill(project['principals']['oncall'])
            await section.get_by_role('option').filter(has_text='@'+project['principals']['oncall']).click()
            if await section.locator('[data-testid="apply-button"]').count():
                await section.locator('[data-testid="apply-button"]').click()
            await _readable(active, section.locator('a[href$="/'+project['principals']['oncall']+'"]'), [])
        await _issue_readable(active, page, heading, task['oracle']['cve'])
        await page.screenshot(path=str(folder/'issue-after.png'), full_page=True)
    elif family == 'runbook_contact_annotation':
        contact = project['principals']['contractor' if wrong else 'oncall']
        await reference.gui_workflows._edit_repository_file(page, project, 'docs/response-runbook.md',
            'Current contact: pending', 'Current contact: @'+contact, folder, 'runbook-contact')
    else:
        await page.goto(base+'/-/project_members', wait_until='domcontentloaded', timeout=90000)
        await page.get_by_role('button', name='Invite members').first.click()
        dialog = page.get_by_role('dialog')
        await dialog.locator('[data-testid="members-token-select-input"]').fill(project['principals']['incoming'])
        await dialog.get_by_role('menuitem').filter(has_text=project['principals']['incoming']).click()
        await dialog.locator('[data-testid="base-dropdown-toggle"]').click()
        await dialog.get_by_role('option', name='Guest' if wrong else 'Reporter', exact=True).click()
        await dialog.locator('input[placeholder="YYYY-MM-DD"]').fill(project['policy']['access_expiry'])
        await dialog.locator('input[placeholder="YYYY-MM-DD"]').press('Tab')
        await dialog.locator('[data-testid="invite-modal-submit"]').click()
        row = page.get_by_role('row').filter(has_text='@'+project['principals']['incoming'])
        await _readable(active, row, [project['principals']['incoming']])
        await page.screenshot(path=str(folder/'member-added.png'), full_page=True)


def _audit_native(safety, identity):
    count = 0; nonces = set()
    for step, path in enumerate(sorted(safety.glob('turn-*/receipt.private.json'))):
        receipt = private(path); policy.validate_receipt(receipt)
        require(receipt['status'] == 'applied' and receipt['driver_result'] == 'succeeded', 'selection_native_dispatch_not_applied')
        envelopes = []
        for phase in ('observation', 'predispatch'):
            envelope = private(path.parent/f'{phase}-envelope.private.json')
            policy.validate_envelope(envelope); envelopes.append(envelope)
            require(envelope['task_id'] == identity['task_id'] and
                    envelope['task_binding_sha256'] == identity['package_sha256'] and
                    envelope['step'] == step, 'selection_native_task_or_step_changed')
            for key in ('raw_image', 'raw_envelope'):
                policy.verify_artifact(safety, envelope[key])
        intent = private(path.parent/'intent.private.json'); action = intent['action']
        decision = private(path.parent/'decision.private.json'); check = decision['lease_check']
        policy.verify_artifact(safety, check['evidence'])
        require(policy.decision(*envelopes, action, lease_check=lambda _: check,
                               now=check['checked_at']) == decision and decision['status'] == 'accepted' and
                models.common.digest(models.common.canonical(decision)) == intent['decision_sha256'],
                'selection_original_native_decision_changed')
        require(receipt['action_sha256'] == policy.digest(action) and
                receipt['decision_sha256'] == policy.digest(decision) and
                receipt['frame_id'] == action['frame_id'] == envelopes[0]['frame_id'] == envelopes[1]['frame_id'] and
                receipt['intent']['path'] == str((path.parent/'intent.private.json').relative_to(safety)) and
                receipt['intent']['sha256'] == ref(path.parent/'intent.private.json')['sha256'],
                'selection_native_receipt_action_decision_or_intent_link_changed')
        policy.verify_artifact(safety, receipt['intent'])
        require(receipt['frame_id'] not in nonces and receipt['step'] == step and
                private(path.parent/'nonce.private.json') == {'frame_id': receipt['frame_id'], 'consumed': True},
                'selection_native_nonce_changed')
        nonces.add(receipt['frame_id']); policy.verify_artifact(safety, receipt['driver_evidence'])
        require(private(safety/receipt['driver_evidence']['path'])['result'] == 'succeeded',
                'selection_actual_native_driver_changed')
        count += 1
    require(0 < count <= 90, 'selection_original_action_count_changed')
    return count


def _audit_case(folder, identity, binding, plan_path):
    artifacts = folder/'artifacts'; before = private(artifacts/'baseline.private.json'); saved = private(artifacts/'saved-artifact.private.json')
    with models.source_scope():
        models._verify_saved_proof(artifacts, saved, identity, before['business_snapshot'], binding,
                                  cohort_source_file_sha256=ref(plan_path)['sha256'])
    context = json.loads(models.common._read_ref(artifacts, saved['full_git_context_ref']))
    require(context['partition'] == 'selection' and context['task']['template_group'] in oracle.SELECTION_FAMILIES,
            'selection_saved_original_partition_changed')
    _reset_proof(artifacts/'native-runtime'); count = _audit_native(artifacts/'native-safety', identity)
    return {'score': saved['independent_score']['reward'], 'native_receipts': count,
            'saved_ref': ref(artifacts/'saved-artifact.private.json'), 'case_context_ref': saved['full_git_context_ref'],
            'reset_exact': True, 'model_calls': 0}


def run(*, review_path, review_sha256, execute=False):
    require(execute is True, 'selection_explicit_execution_required')
    authority = _check_authority(review_path, review_sha256); out = Path(authority['output_root'])
    require(not out.exists() and not out.is_symlink(), 'selection_fresh_output_required')
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    world.write(out.parent/('selection-review-'+review_sha256+'-consumed.private.json'),
                {'review_ref': ref(review_path), 'one_use': True, 'automatic_restarts': 0, 'model_calls': 0})
    out.mkdir(mode=0o700); world.write(out/'intent.private.json', authority)
    plan_path = Path(authority['plan_ref']['path']); plan, _ = world.checked_plan(plan_path)
    binding = models.validate_binding(private(authority['native_binding_ref']['path'], authority['native_binding_ref']['sha256']))
    # Existing V15 phase and permit schema are unchanged. This separately
    # owned permit is usable only after the exact selection-only Root contract.
    permit = out/'selection-only-native-permit.private.json'
    world.write(permit, {'schema': 'envloop-gitlab-uniform-task-permit-v15',
        'plan_sha256': ref(plan_path)['sha256'], 'source_sha256s': plan['source_sha256s'],
        'phase': 'train-qualification', 'accepted': True, 'uniform_all_slots': True,
        'no_historical_credit': True, 'note': 'Explicit Root selection20-only reference authority; no model/final authority.',
        'selection_only_root_authority_ref': ref(review_path)})
    rows = []
    try:
        for ordinal, identity in enumerate(authority['ordered_selection20']):
            directory = out/f'task-{ordinal:03d}'; directory.mkdir(mode=0o700); modes = []
            for mode, score in MODES:
                require(_check_authority(review_path, review_sha256) == authority, 'selection_authority_changed_before_package')
                folder = directory/mode; folder.mkdir(mode=0o700); (folder/'artifacts').mkdir(mode=0o700)
                with models.source_scope():
                    backend = models.FullGitBackend(selection.RealGitLabSelectionBackend(), partition='selection',
                        binding=binding, cohort_freeze_path=plan_path)
                backend.phase, backend.permit_path = 'train-qualification', permit; backend.set_output_root(folder)
                with models.source_scope(), backend.open(identity) as active:
                    active.loop.call(workflow(active, active.original_task, mode, folder))
                    _budget(active); observation = active.observe(memory='')
                    active.dispatch(reference.normalize_model_action('{"type":"finish","memory":""}', observation,
                                                                    current_frame_id=observation.frame_id))
                    saved = active.read_saved_state(); require(saved['independent_score']['reward'] == score, 'selection_original_control_score_changed')
                    world.write(folder/'artifacts/baseline.private.json', active.baseline_semantic)
                    world.write(folder/'artifacts/saved-artifact.private.json', saved)
                require(active.post_restore_exact and active.environment_terminated, 'selection_actual_reset_not_complete')
                audited = _audit_case(folder, identity, binding, plan_path); require(audited['score'] == score, 'selection_saved_control_score_changed')
                world.write(folder/'result.private.json', audited); modes.append({'mode': mode, 'expected': score, 'result_ref': ref(folder/'result.private.json')})
            row = {'ordinal': ordinal, 'identity': identity, 'modes': modes}; world.write(directory/'trio.private.json', row); rows.append(row)
        require(_check_authority(review_path, review_sha256) == authority, 'selection_source_changed_after_controls')
        result = {'schema': 'gitlab-original-selection20-reference-result-v1', 'authority_ref': ref(review_path),
                  'controller_binding': source_binding(), 'rows': rows, 'completed_count': 20,
                  'source_visual_review_pending': True, 'model_calls': 0, 'formal_admissions': 0}
        world.write(out/'result.private.json', result); return result
    except BaseException as error:
        world.write(out/'failure.private.json', {'status': 'terminal_preserved_no_retry', 'error_type': type(error).__name__,
                    'completed_count': len(rows), 'model_calls': 0, 'formal_admissions': 0})
        raise


def audit(*, review_path, review_sha256):
    authority = _check_authority(review_path, review_sha256); out = Path(authority['output_root'])
    require(not (out/'failure.private.json').exists() and private(out/'intent.private.json') == authority,
            'selection_failed_or_wrong_intent_cannot_qualify')
    result = private(out/'result.private.json')
    require(result['authority_ref'] == ref(review_path) and result['controller_binding'] == source_binding() and
            result['completed_count'] == len(result['rows']) == 20 and result['source_visual_review_pending'] is True and
            result['model_calls'] == result['formal_admissions'] == 0, 'selection_exact_completed20_required')
    binding = models.validate_binding(private(authority['native_binding_ref']['path'], authority['native_binding_ref']['sha256']))
    receipts = 0
    for ordinal, identity in enumerate(authority['ordered_selection20']):
        row = result['rows'][ordinal]; require(row['ordinal'] == ordinal and row['identity'] == identity and
                row == private(out/f'task-{ordinal:03d}/trio.private.json'), 'selection_order_or_identity_changed')
        require([entry['mode'] for entry in row['modes']] == [mode for mode, _ in MODES], 'selection_whole_trio_required')
        for entry, (mode, score) in zip(row['modes'], MODES):
            folder = out/f'task-{ordinal:03d}'/mode
            require(entry['expected'] == score and entry['result_ref'] == ref(folder/'result.private.json'), 'selection_case_ref_changed')
            actual = _audit_case(folder, identity, binding, Path(authority['plan_ref']['path']))
            require(actual == private(folder/'result.private.json') and actual['score'] == score, 'selection_actual_saved_case_changed')
            receipts += actual['native_receipts']
    return {'status': 'original_selection20_saved_controls_verified_source_visual_review_pending',
            'tasks': 20, 'cases': 60, 'native_receipts': receipts, 'result_ref': ref(out/'result.private.json'),
            'formal_admissions': 0, 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare-review')
    for name in ('plan-path', 'binding-path', 'train-accept-path', 'train-accept-sha256', 'source-review-path', 'source-review-sha256', 'output', 'review-output'):
        prep.add_argument('--'+name, required=True)
    for command in ('run', 'audit'):
        child = sub.add_parser(command); child.add_argument('--review-path', required=True); child.add_argument('--review-sha256', required=True)
        if command == 'run': child.add_argument('--execute', action='store_true')
    args = vars(parser.parse_args()); command = args.pop('command')
    if command == 'prepare-review':
        output = Path(args.pop('review_output')); value = review_contract(**args); world.write(output, value)
        result = {'status': 'metadata_and_saved_prerequisites_only_no_execution', 'review_proposal_ref': ref(output)}
    else: result = run(**args) if command == 'run' else audit(**args)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
