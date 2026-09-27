"""Replay only JSON syntax of one preserved train-only Qwen sample offline.

No fresh provider call, GUI dispatch, current-frame validation, or task score
is performed. The historical rejection remains the original observed result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from cursibench.scale_action_contract import _strict_json
from cursibench.scale_vision_proxy import digest as sampling_digest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE = ROOT / 'docs/evidence/odoo-qwen38-train-frame-smoke-2026-09-25.json'
PARSER = ROOT / 'src/cursibench/scale_action_contract.py'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-journal', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    journal, out = args.private_journal.resolve(), args.out.resolve()
    require(journal.is_file() and not journal.is_symlink() and
            (journal.stat().st_mode & 0o077) == 0,
            'private mode-0600 journal required')
    require(out.is_relative_to((ROOT / 'docs/evidence').resolve()) and
            not out.exists(), 'new public evidence path required')
    source = json.loads(PUBLIC_SOURCE.read_bytes())
    require(source['partition'] == 'train_only' and
            source['official_hidden_task_used'] is False and
            source['model_actions_dispatched'] == 0 and
            source['model_action_error_code'] == 'invalid_action_json',
            'historical train-only rejection changed')
    with sqlite3.connect(f'file:{journal}?mode=ro', uri=True) as connection:
        rows = connection.execute('SELECT state,result FROM requests').fetchall()
    require(len(rows) == 1 and rows[0][0] == 'complete',
            'exactly one completed preserved sample required')
    saved = json.loads(rows[0][1])
    text = saved['text']
    text_sha = sampling_digest(text)
    require(text_sha == source['sampling']['text_sha256'] and
            saved['status'] == 'completed',
            'provider text differs from original public receipt')
    action = _strict_json(text)
    require(action.get('type') == 'click' and
            type(action.get('target')) is dict and
            set(action['target']) == {'ref'},
            'saved text did not have the expected action shape')
    receipt = {
        'schema': 'envloop-odoo-fenced-train-sample-offline-replay-v1',
        'historical_train_sample_text_sha256': text_sha,
        'historical_action_status': 'rejected_not_dispatched',
        'historical_error_code': 'invalid_action_json',
        'new_shared_parser_sha256': hashlib.sha256(PARSER.read_bytes()).hexdigest(),
        'new_transport_json_parse_passed': True,
        'parsed_action_type': 'click',
        'parsed_target_kind': 'current_frame_control_ref',
        'current_frame_validation_executed': False,
        'gui_action_dispatched': False,
        'provider_calls_added': 0,
        'official_hidden_task_used': False,
        'official_task_scores_added': 0,
    }
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': 'offline_syntax_replay_only',
                      'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                      'official_task_scores_added': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
