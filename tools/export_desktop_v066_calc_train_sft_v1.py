"""Source-bound public-train Calc current-frame SFT exporter; no provider call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import export_desktop_v066_calc_writer_train_sft_common_v1 as common


HELPER_SHA256 = "8e770aeabc2f2136ad12d609767168ca76eba02288639314b6a783864ff829ea"


def _pinned() -> None:
    common.require(common.digest(Path(common.__file__).read_bytes()) ==
                   HELPER_SHA256,
                   "Calc exporter shared source changed")


def source_bound_steps(episode_dir: Path) -> tuple[dict, list[dict]]:
    _pinned()
    return common.source_bound_steps("calc", episode_dir)


def render(episode_dir: Path, ratification: Path) -> tuple[dict, dict]:
    _pinned()
    return common.render(kind="calc", episode_dir=episode_dir,
                         ratification=ratification,
                         exporter_source=Path(__file__))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    _pinned()
    result = common.publish(
        kind="calc", episode_dir=args.episode_dir,
        ratification=args.ratification, exporter_source=Path(__file__),
        private_out=args.private_out, public_out=args.public_out)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
