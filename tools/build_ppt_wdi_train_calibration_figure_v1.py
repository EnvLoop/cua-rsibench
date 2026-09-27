"""Render the public offline-only PowerPoint calibration coverage figure."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


LABELS = (
    "Nominal output growth",
    "Per-capita growth",
    "Inflation acceleration",
    "Labor-rate change",
    "Population growth",
    "Output/person divergence",
    "Price–labor spread",
    "Dual-threshold review",
    "Source-year reconciliation",
    "Chart-caption reconciliation",
)


def build(receipt: dict) -> str:
    if (receipt.get("schema") != "envloop-ppt-wdi-train-calibration-80-public-v1"
            or receipt.get("calibration_analogue_tasks") != 80
            or receipt.get("tasks_per_workflow") != 8
            or receipt.get("declared_workflows") != 10
            or receipt.get("train_only_source_families") != 8
            or receipt.get("offline_positive_partial_collateral_chart_controls_pass") != 80
            or receipt.get("model_calls") != 0
            or receipt.get("office_web_gui_admitted") != 0
            or receipt.get("official_final_admitted") != 0):
        raise ValueError("Offline-only 10 x 8 receipt required")
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="670" '
        'viewBox="0 0 1180 670" role="img" aria-labelledby="title desc">',
        '<title id="title">PowerPoint training calibration coverage</title>',
        '<desc id="desc">Ten workflows each have eight four-target training '
        'analogues from eight source families. All eighty pass offline controls; '
        'model difficulty and Office web behavior remain unmeasured.</desc>',
        '<rect width="1180" height="670" fill="#f6f8fb"/>',
        '<rect x="20" y="18" width="1140" height="632" rx="20" '
        'fill="#ffffff" stroke="#dce4ec"/>',
        '<text x="48" y="70" font-family="Arial,sans-serif" font-size="27" '
        'font-weight="700" fill="#102a43">PowerPoint training calibration coverage</text>',
        '<text x="48" y="101" font-family="Arial,sans-serif" font-size="15" '
        'fill="#52677a">Four-target, seven-slide analogues on train-only WDI '
        'sources · offline evidence</text>',
        '<rect x="901" y="49" width="223" height="42" rx="21" fill="#e5f5ee"/>',
        '<text x="1012" y="76" text-anchor="middle" '
        'font-family="Arial,sans-serif" font-size="15" font-weight="700" '
        'fill="#116446">80 / 80 offline QA</text>',
        '<text x="48" y="142" font-family="Arial,sans-serif" font-size="12" '
        'font-weight="700" letter-spacing="1" fill="#60768b">CAUSAL WORKFLOW</text>',
        '<text x="428" y="142" font-family="Arial,sans-serif" font-size="12" '
        'font-weight="700" letter-spacing="1" fill="#60768b">TRAIN-ONLY SOURCE FAMILIES</text>',
    ]
    for index, label in enumerate(LABELS):
        y = 161 + 40 * index
        if index % 2 == 0:
            parts.append(f'<rect x="36" y="{y - 18}" width="1108" height="37" '
                         'rx="7" fill="#f7f9fc"/>')
        parts.append(f'<text x="48" y="{y + 5}" font-family="Arial,sans-serif" '
                     f'font-size="15" fill="#1d3448">{html.escape(label)}</text>')
        for family in range(8):
            x = 428 + family * 80
            fill = "#2f7ba6" if index < 7 else "#2c8c7f"
            parts.append(f'<rect x="{x}" y="{y - 13}" width="64" height="26" '
                         f'rx="6" fill="{fill}"/>')
        parts.append(f'<text x="1118" y="{y + 5}" text-anchor="end" '
                     'font-family="Arial,sans-serif" font-size="14" '
                     'font-weight="700" fill="#23445f">8 / 8</text>')
    parts += [
        '<line x1="48" y1="568" x2="1132" y2="568" stroke="#dce4ec"/>',
        '<text x="48" y="598" font-family="Arial,sans-serif" font-size="15" '
        'font-weight="700" fill="#102a43">Train-only structural coverage is complete.</text>',
        '<text x="48" y="624" font-family="Arial,sans-serif" font-size="14" '
        'fill="#52677a">Paired Qwen vs Astra/Sol saved-state scores: 0 · '
        'Office-web GUI admissions: 0 · Official final admissions: 0</text>',
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    svg = build(json.loads(args.receipt.read_bytes()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(json.dumps({"figure": str(args.out), "workflows": 10,
                      "train_only_analogues": 80, "official_final_credit": 0}))


if __name__ == "__main__":
    main()
