"""Render an admitted cell-neutral GUI SFT episode offline, with no API call."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cursibench.gui_sft_episode_v2 import build_tinker_datums


ROOT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--selection-manifest', type=Path, required=True)
    parser.add_argument('--final-manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'work') or out.exists():
        raise ValueError('fresh_private_output_required')
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    rendered = build_tinker_datums(
        args.episode, selection_manifest=args.selection_manifest,
        final_manifest=args.final_manifest)
    with out.open('x') as stream:
        json.dump(rendered.receipt, stream, indent=2, sort_keys=True)
        stream.write('\n')
    out.chmod(0o600)
    print(json.dumps({key: rendered.receipt[key] for key in
                      ('schema', 'cell', 'datum_count', 'max_supervised_tokens',
                       'minimum_positive_assistant_loss_sum',
                       'paid_provider_calls', 'official_final_task_count_added')},
                     sort_keys=True))
