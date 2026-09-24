"""v0.6.3 Magento pilot with bounded fresh-frame resampling.

At most five applied GUI actions and seven distinct provider samples are
allowed. A completed sample whose screenshot changed during inference is
discarded, recorded, and replaced by a new observation/new request ID, at
most twice. Provider errors are never retried. Coordinate actions require
the exact observed pixels; ref actions additionally require the same current
visible DOM element. The pinned v0.6 host still owns login, local-only routes,
business-state readback, and the unmodified published evaluator.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from cursibench.scale_action_contract import VERSION as TRUSTED_ACTION_VERSION
from cursibench.scale_action_output_v063 import (
    OUTPUT_VERSION, normalize_model_action, render_for_model,
)

VERSION = 'magento-model-pilot-v0.6.3'
CAMPAIGN_ID = 'magento-base-pilot-v4'
MAX_GUI_ACTIONS = 5
MAX_SAMPLES = 7
MAX_STALE_SAMPLES = 2
ROOT = Path(__file__).resolve().parents[1]
BASE_RUNNER = ROOT / 'tools/run_magento_model_pilot_v06.py'
BASE_RUNNER_SHA256 = '25f32928ff11e7ebdeb426be943680ddc8e05fa72f1caea3117a18a67bdebeeb'
V062_BOUNDARY = ROOT / 'src/cursibench/scale_action_output_v062.py'
V062_BOUNDARY_SHA256 = '6e140ea2f8e7dab9bba74d689860d33c8e821fa050bd216610e28c0cc7862d5d'


def _load_host():
    if hashlib.sha256(BASE_RUNNER.read_bytes()).hexdigest() != BASE_RUNNER_SHA256:
        raise RuntimeError('pinned_v06_host_changed')
    if hashlib.sha256(V062_BOUNDARY.read_bytes()).hexdigest() != V062_BOUNDARY_SHA256:
        raise RuntimeError('pinned_v062_output_changed')
    spec = importlib.util.spec_from_file_location('pinned_magento_v06_host_for_v063', BASE_RUNNER)
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    strict_validator = host.validate_action

    def validate_output(raw, observation, *, current_frame_id):
        if type(raw) is str:
            return normalize_model_action(raw, observation,
                                          current_frame_id=current_frame_id)
        return strict_validator(raw, observation,
                                current_frame_id=current_frame_id)

    host.VERSION = VERSION
    host.CAMPAIGN_ID = CAMPAIGN_ID
    host.MAX_ACTIONS = MAX_GUI_ACTIONS
    host.render_for_proxy = render_for_model
    host.validate_action = validate_output
    host.execute_policy = execute_policy
    return host


def _action_refs(action: dict) -> tuple[str, ...]:
    targets = []
    if action['type'] in ('click', 'type'):
        targets.append(action['target'])
    elif action['type'] in ('key', 'scroll') and 'target' in action:
        targets.append(action['target'])
    elif action['type'] == 'drag':
        targets.extend((action['from'], action['to']))
    return tuple(target['ref'] for target in targets if 'ref' in target)


async def _same_visible_refs(page, action, observation, old_handles) -> bool:
    refs = _action_refs(action)
    if not refs:
        return True
    fresh_controls, fresh_handles = await host._visible_controls(page)
    expected = {row.ref: row for row in observation.controls}
    current = {row['ref']: row for row in fresh_controls}
    for ref in refs:
        old_handle, new_handle = old_handles.get(ref), fresh_handles.get(ref)
        old_control, new_control = expected.get(ref), current.get(ref)
        if old_handle is None or new_handle is None or old_control is None or new_control is None:
            return False
        if (old_control.role != new_control['role'] or
                old_control.label != new_control['label'] or
                not new_control['visible'] or not new_control['enabled']):
            return False
        try:
            if not await old_handle.is_visible() or not await old_handle.is_enabled():
                return False
            if not await old_handle.evaluate(
                    '(element, candidate) => element.isConnected && element === candidate',
                    new_handle):
                return False
        except Exception:
            return False
    return True


async def _same_pixels(page, observation, frame_url: str) -> tuple[bool, str | None]:
    if page.url != frame_url:
        return False, 'unexpected_navigation_during_sampling'
    image = await page.screenshot(type='png', full_page=False,
                                  animations='disabled', mask=[page.locator('.admin-user')])
    if hashlib.sha256(image).hexdigest() != observation.screenshot['sha256']:
        return False, 'pixels_changed'
    return True, None


async def execute_policy(page, adapter, *, instruction: str, binding: str,
                         request_prefix: str):
    """Discard stale completed samples; never reuse their request IDs or text."""
    memory = ''
    previous = None
    actions = []
    samples = []
    stale_reasons = []
    applied_count = 0

    def outcome(status, failure_class=None, failure_code=None):
        return {
            'status': status, 'failure_class': failure_class,
            'failure_code': failure_code, 'actions': actions, 'samples': samples,
            'action_attempt_count': len(actions),
            'applied_action_count': applied_count,
            'sample_attempt_count': len(samples),
            'stale_sample_count': len(stale_reasons),
            'stale_reasons': list(stale_reasons),
            'max_gui_actions': MAX_GUI_ACTIONS,
            'max_samples': MAX_SAMPLES,
            'max_stale_samples': MAX_STALE_SAMPLES,
        }

    async def discard_stale(reason):
        stale_reasons.append(reason)
        samples[-1]['discarded_as_stale'] = True
        samples[-1]['stale_reason'] = reason
        if reason == 'unexpected_navigation_during_sampling':
            return outcome('unscored', 'environment_failure', reason)
        if len(stale_reasons) > MAX_STALE_SAMPLES:
            return outcome('unscored', 'environment_failure', 'stale_sample_budget_exhausted')
        return None

    while len(actions) < MAX_GUI_ACTIONS and len(samples) < MAX_SAMPLES:
        step = len(actions)
        sample_index = len(samples)
        observation, handles, frame_url = await host.capture_frame(
            page, instruction=instruction, binding=binding, step=step,
            memory=memory, previous=previous)
        request = host.render_for_proxy(observation)
        request_id = f'{request_prefix}-sample-{sample_index}-step-{step}'
        try:
            result = await asyncio.to_thread(adapter.sample, request_id=request_id, **request)
        except Exception:
            return outcome('unscored', 'transport_or_provider_failure',
                           'sampling_transport_uncertain')
        if type(result) is not dict:
            return outcome('unscored', 'transport_or_provider_failure',
                           'sampling_result_invalid')
        samples.append(host.sample_receipt(result))
        if result.get('status') != 'completed' or type(result.get('text')) is not str:
            return outcome('unscored',
                           host.sampling_failure_class(result.get('error_subtype')),
                           result.get('error_subtype') or 'sampling_failed')

        # The model reply is never dispatched against pixels it did not see.
        same, reason = await _same_pixels(page, observation, frame_url)
        if not same:
            decision = await discard_stale(reason)
            if decision is not None:
                return decision
            continue
        try:
            action = host.validate_action(result['text'], observation,
                                          current_frame_id=observation.frame_id)
        except host.ContractError as exc:
            actions.append(host.action_receipt(observation, error=exc))
            return outcome('completed', 'model_failure', exc.code)

        # A ref is meaningful only while it names the same visible DOM node.
        if not await _same_visible_refs(page, action, observation, handles):
            decision = await discard_stale('ref_identity_changed')
            if decision is not None:
                return decision
            continue
        # Recheck immediately before GUI dispatch, including for coordinates.
        same, reason = await _same_pixels(page, observation, frame_url)
        if not same:
            decision = await discard_stale(reason)
            if decision is not None:
                return decision
            continue
        try:
            host.validate_action(action, observation,
                                 current_frame_id=observation.frame_id)
            previous = await host.dispatch_action(page, action, observation, handles)
        except host.ContractError as exc:
            actions.append(host.action_receipt(observation, error=exc))
            return outcome('completed', 'model_failure', exc.code)
        except host.PilotError as exc:
            if exc.code == 'target_not_found':
                previous = {'status': 'rejected', 'code': 'target_not_found'}
            else:
                return outcome('unscored', 'environment_failure', exc.code)
        except Exception:
            # Once dispatch starts, side effects can be uncertain; do not replay.
            return outcome('unscored', 'environment_failure', 'gui_dispatch_error')
        actions.append(host.action_receipt(observation, action=action))
        if previous['status'] == 'applied':
            applied_count += 1
        memory = action['memory']
        if action['type'] == 'finish':
            return outcome('completed')
    if len(actions) >= MAX_GUI_ACTIONS:
        return outcome('completed')
    return outcome('unscored', 'environment_failure', 'sample_budget_exhausted')


host = _load_host()
SOURCE = host.SOURCE


class LiveAdapterFactory(host.LiveAdapterFactory):
    def __call__(self, journal):
        if not os.environ.get('TINKER_API_KEY'):
            raise host.PilotError('tinker_key_missing')
        import tinker
        renderer = host.QwenVisionRenderer.load()
        self.service = tinker.ServiceClient(
            user_metadata=host.campaign_metadata(CAMPAIGN_ID))
        backend = host.TinkerVisionBackend.from_service(self.service, renderer)
        return host.VisionSamplingAdapter(backend, journal, limits=host.VisionLimits(
            max_actions=MAX_SAMPLES, output_tokens=512,
            request_timeout_seconds=240))


async def run(source: Path, out: Path, adapter_factory):
    out = Path(out).resolve()
    result = await host.run(source, out, adapter_factory)
    host.smoke.write(out / 'boundary.json', {
        'pilot_version': VERSION, 'model_output_version': OUTPUT_VERSION,
        'trusted_action_version': TRUSTED_ACTION_VERSION,
        'campaign_id': CAMPAIGN_ID,
        'max_gui_actions': MAX_GUI_ACTIONS,
        'max_samples': MAX_SAMPLES,
        'max_stale_samples': MAX_STALE_SAMPLES,
        'base_runner_sha256': BASE_RUNNER_SHA256,
        'v062_output_boundary_sha256': V062_BOUNDARY_SHA256,
        'output_boundary_sha256': hashlib.sha256(
            (ROOT / 'src/cursibench/scale_action_output_v063.py').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'result_sha256': hashlib.sha256((out / 'result.json').read_bytes()).hexdigest(),
        'prior_paid_pilot_results_reused': False,
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    factory = LiveAdapterFactory()
    try:
        result = asyncio.run(run(args.source, args.out, factory))
        policy = result.get('policy') or {}
        print(json.dumps({
            'version': VERSION, 'output_version': OUTPUT_VERSION,
            'status': result['status'], 'score': result['score'],
            'pilot_task_complete': result.get('pilot_task_complete'),
            'failure_class': result.get('failure_class'),
            'failure_code': result.get('failure_code'),
            'sample_attempt_count': policy.get('sample_attempt_count'),
            'stale_sample_count': policy.get('stale_sample_count'),
            'action_attempt_count': policy.get('action_attempt_count'),
            'applied_action_count': policy.get('applied_action_count'),
        }, sort_keys=True), flush=True)
        raise SystemExit(0 if result['status'] == 'completed' else 2)
    finally:
        factory.close('success' if 'result' in locals() and result['status'] == 'completed' else 'errored')


if __name__ == '__main__':
    main()
