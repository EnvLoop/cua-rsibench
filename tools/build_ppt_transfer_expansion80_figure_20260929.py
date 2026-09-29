"""Draw the source-only, offline-only PowerPoint transfer coverage figure."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from tools.build_ppt_wdi_train_calibration_figure_v1 import LABELS


def build(receipt: dict) -> str:
    if (receipt.get("schema") != "envloop-office-transfer-ppt-source-public-v1" or
            receipt.get("stage") != "expansion" or
            receipt.get("analogue_specs") != 80 or
            receipt.get("workflows") != 10 or
            receipt.get("cases_per_workflow") != 8 or
            receipt.get("new_source_country_families") != 8 or
            receipt.get("offline_control_passed") != 80 or
            receipt.get("office_web_gui_admitted") != 0 or
            receipt.get("official_final_admitted") != 0 or
            receipt.get("model_calls") != 0):
        raise ValueError("Exact offline-only 10 x 8 transfer receipt required")
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1260" height="700" '
        'viewBox="0 0 1260 700" role="img" aria-labelledby="title desc">',
        '<title id="title">PowerPoint training-transfer source coverage</title>',
        '<desc id="desc">Ten four-target workflows each have two pilot and six '
        'additional source-disjoint training cases. All eighty pass offline '
        'controls. Office web and model outcomes remain unmeasured.</desc>',
        '<rect width="1260" height="700" fill="#f5f8fb"/>',
        '<rect x="24" y="20" width="1212" height="660" rx="20" '
        'fill="#fff" stroke="#d7e1eb"/>',
        '<text x="52" y="73" font-family="Arial,sans-serif" font-size="29" '
        'font-weight="700" fill="#123349">PowerPoint training-transfer coverage</text>',
        '<text x="52" y="107" font-family="Arial,sans-serif" font-size="16" '
        'fill="#50687c">Real WDI observations · 4 edits per task · 7-slide editable decks</text>',
        '<rect x="969" y="53" width="230" height="42" rx="21" fill="#e4f5ec"/>',
        '<text x="1084" y="80" text-anchor="middle" '
        'font-family="Arial,sans-serif" font-size="16" font-weight="700" '
        'fill="#166446">80 / 80 offline QA</text>',
        '<text x="52" y="158" font-family="Arial,sans-serif" font-size="13" '
        'font-weight="700" letter-spacing="1" fill="#647c90">WORKFLOW</text>',
        '<text x="474" y="158" font-family="Arial,sans-serif" font-size="13" '
        'font-weight="700" letter-spacing="1" fill="#647c90">TRAIN-ONLY SOURCE FAMILIES</text>',
    ]
    for i, label in enumerate(LABELS):
        y = 189 + i * 40
        if i % 2 == 0:
            lines.append(f'<rect x="42" y="{y - 20}" width="1172" '
                         'height="38" rx="6" fill="#f6f9fc"/>')
        lines.append(f'<text x="52" y="{y + 5}" '
                     'font-family="Arial,sans-serif" font-size="15" '
                     f'fill="#244359">{html.escape(label)}</text>')
        for j in range(8):
            x = 474 + j * 82
            color = "#4e7eaa" if j < 2 else "#24887e"
            lines.append(f'<rect x="{x}" y="{y - 14}" width="66" '
                         f'height="27" rx="6" fill="{color}"/>')
        lines.append(f'<text x="1190" y="{y + 5}" text-anchor="end" '
                     'font-family="Arial,sans-serif" font-size="15" '
                     'font-weight="700" fill="#23445f">8</text>')
    lines += [
        '<rect x="474" y="603" width="20" height="16" rx="3" fill="#4e7eaa"/>',
        '<text x="504" y="617" font-family="Arial,sans-serif" font-size="14" '
        'fill="#476176">Pilot source families (2)</text>',
        '<rect x="750" y="603" width="20" height="16" rx="3" fill="#24887e"/>',
        '<text x="780" y="617" font-family="Arial,sans-serif" font-size="14" '
        'fill="#476176">New source families (6)</text>',
        '<line x1="52" y1="638" x2="1204" y2="638" stroke="#dce5ed"/>',
        '<text x="52" y="662" font-family="Arial,sans-serif" font-size="14" '
        'fill="#526b7e">Office-web saves: 0 · Model runs: 0 · Official final credit: 0</text>',
        '</svg>',
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    svg = build(json.loads(args.receipt.read_bytes()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg)
    print(json.dumps({"offline_train_only_cases": 80, "office_web_gui_admitted": 0,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
