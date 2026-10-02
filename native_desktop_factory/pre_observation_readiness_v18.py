"""Bounded passive focus readiness; exact current-frame dispatch stays intact.

Run after pointer actions or Control+A, before returning the next observation.
Every full native screenshot is retained. No pixels, input, task answers or
saved-state results are changed. The existing narrow caret shape is used only
to classify the final passive samples, never to alter a returned screenshot.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import time

from cursibench.scale_action_contract import ContractLimits, make_observation
from . import qwen_v066_adapter_v4_strict as strict
from .qwen_v064_adapter import application_frame_digest
from .qwen_v066_adapter import _single_caret_column
from .post_enter_train_probe_v1 import _append_fsynced
from .v066_storage_budget import reserve_and_write

SAMPLE_DELAYS_MS = (0, 250, 250, 500, 500, 500, 500)
MAX_WALL_MS = 60_000
ORIGINAL_OBSERVE = strict.observe
ORIGINAL_DISPATCH = strict.dispatch


def _owner(sandbox):
    # The control worker observes through RecordingDesktop and dispatches
    # through its immediate actor proxy. Direct model clients use one object.
    for _ in range(4):
        inner = getattr(sandbox, 'sandbox', None)
        if inner is None or inner is sandbox:
            return sandbox
        sandbox = inner
    raise ValueError('Unexpected readiness wrapper depth')


def needs_readiness(action):
    return (action['type'] in ('click', 'double_click', 'drag') or
            action['type'] in ('type', 'key', 'scroll') and 'target' in action or
            action['type'] == 'key' and action.get('key') == 'Control+A')


def dispatch(sandbox, action):
    result = ORIGINAL_DISPATCH(sandbox, action)
    if needs_readiness(action):
        _owner(sandbox)._v12_focus_pending = True
    return result


def settled_suffix(frames):
    """At least four final samples: one exact image or one narrow caret pair."""
    if len(frames) != len(SAMPLE_DELAYS_MS):
        return False
    tail = frames[-4:]
    hashes = {application_frame_digest(raw) for raw in tail}
    return (len(hashes) <= 2 and all(
        application_frame_digest(raw) == application_frame_digest(tail[0]) or
        _single_caret_column(tail[0], raw) for raw in tail))


def passive_samples(sandbox, *, clock=time.monotonic_ns, sleep=time.sleep,
                    persist=None):
    start = clock()
    initial_id = sandbox.get_current_window_id()
    initial_title = sandbox.get_window_title(initial_id)
    if not initial_id or not initial_title:
        raise ValueError('Readiness requires a native visible window')
    frames = []
    rows = []
    for sample, delay in enumerate(SAMPLE_DELAYS_MS):
        if delay:
            sleep(delay / 1000)
        before = clock()
        first_id = sandbox.get_current_window_id()
        first_title = sandbox.get_window_title(first_id)
        raw = bytes(sandbox.screenshot())
        second_id = sandbox.get_current_window_id()
        second_title = sandbox.get_window_title(second_id)
        after = clock()
        row = {'sample': sample, 'requested_delay_ms': delay,
               'monotonic_before_ns': before, 'monotonic_after_ns': after,
               'elapsed_ns': after - start,
               'full_frame_sha256': sha256(raw).hexdigest(),
               'application_frame_sha256': application_frame_digest(raw),
               'window_id_sha256': sha256(first_id.encode()).hexdigest(),
               'window_title_sha256': sha256(first_title.encode()).hexdigest(),
               'native_window_unchanged':
               first_id == second_id == initial_id and
               first_title == second_title == initial_title}
        if persist is not None:
            persist(row, raw)
        rows.append(row)
        frames.append(raw)
        if (not row['native_window_unchanged'] or before < start or
                after < before or after - start > MAX_WALL_MS * 1_000_000):
            raise ValueError('Passive readiness window or time boundary changed')
    if (rows[-1]['elapsed_ns'] < sum(SAMPLE_DELAYS_MS) * 1_000_000 or
            not settled_suffix(frames)):
        raise ValueError('Passive readiness did not settle')
    return frames[-1], rows


def observe(sandbox, *, task_id, task_binding_sha256, instruction, step,
            previous_action_result=None, memory='', max_actions=5):
    owner = _owner(sandbox)
    if not getattr(owner, '_v12_focus_pending', False):
        return ORIGINAL_OBSERVE(
            sandbox, task_id=task_id, task_binding_sha256=task_binding_sha256,
            instruction=instruction, step=step,
            previous_action_result=previous_action_result, memory=memory,
            max_actions=max_actions)
    if type(step) is not int or step <= 0:
        raise ValueError('Focus readiness requires the next action step')
    root = Path(os.environ['ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT']).resolve()
    out = Path(os.environ['ENVLOOP_DESKTOP_V4_ATTEMPT_DIR']).resolve()
    if out.parent.parent != root or not out.is_dir() or out.is_symlink():
        raise ValueError('Passive readiness evidence scope changed')
    journal = out / 'pre-observation-readiness-v12.ndjson'
    if journal.exists() and any(json.loads(line)['step'] == step for line in
                              journal.read_bytes().splitlines()):
        raise ValueError('Passive readiness step is already consumed')

    def persist(row, raw):
        ref = reserve_and_write(root, out / f'readiness-{step:02d}-{row["sample"]:02d}.png', raw)
        _append_fsynced(journal, {'schema': 'cua-native-passive-focus-readiness-v12',
                                'step': step, 'preceding_step': step - 1,
                                **row, 'frame': ref})

    raw, _rows = passive_samples(sandbox, persist=persist)
    owner._v12_focus_pending = False
    return make_observation(
        task_id=task_id, task_binding_sha256=task_binding_sha256,
        instruction=instruction, step=step, screenshot_bytes=raw,
        a11y_text='', dom_text='', controls=(), memory=memory,
        previous_action_result=previous_action_result,
        limits=ContractLimits(max_step=max_actions))


def audit_samples(root, out, actions, receipt):
    """Reopen all passive frames and bind them to first returned observations."""
    expected = [i + 1 for i, action in enumerate(actions[:-1]) if needs_readiness(action)]
    journal = out / 'pre-observation-readiness-v12.ndjson'
    rows = [json.loads(line) for line in journal.read_bytes().splitlines()] if journal.exists() else []
    if len(rows) != len(expected) * len(SAMPLE_DELAYS_MS):
        raise ValueError('Passive readiness samples missing or unexpected')
    from .v066_final_control_audit import _bound_file
    for ordinal, step in enumerate(expected):
        group = rows[ordinal * 7:(ordinal + 1) * 7]
        frames = []
        for index, row in enumerate(group):
            raw = _bound_file(root, row['frame'])
            if (row.get('schema') != 'cua-native-passive-focus-readiness-v12' or
                    row.get('step') != step or row.get('preceding_step') != step - 1 or
                    row.get('sample') != index or row.get('requested_delay_ms') != SAMPLE_DELAYS_MS[index] or
                    row.get('native_window_unchanged') is not True or
                    row.get('full_frame_sha256') != sha256(raw).hexdigest() or
                    row.get('application_frame_sha256') != application_frame_digest(raw) or
                    type(row.get('monotonic_before_ns')) is not int or
                    type(row.get('monotonic_after_ns')) is not int or
                    row['monotonic_before_ns'] > row['monotonic_after_ns'] or
                    not 0 <= row.get('elapsed_ns', -1) <= MAX_WALL_MS * 1_000_000):
                raise ValueError('Passive readiness raw sample binding changed')
            frames.append(raw)
        if (not settled_suffix(frames) or
                len({(r['window_id_sha256'], r['window_title_sha256']) for r in group}) != 1 or
                len({r['monotonic_after_ns'] - r['elapsed_ns'] for r in group}) != 1 or
                group[-1]['elapsed_ns'] < sum(SAMPLE_DELAYS_MS) * 1_000_000 or
                any(b['monotonic_before_ns'] - a['monotonic_after_ns'] < b['requested_delay_ms'] * 1_000_000
                    for a, b in zip(group, group[1:])) or
                (out / f'frame-{step:02d}-0.png').read_bytes() != frames[-1]):
            raise ValueError('Passive readiness did not bind a stable fresh observation')
    return len(expected)
