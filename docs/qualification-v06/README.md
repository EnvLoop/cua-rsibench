# EnvLoop computer-use qualification note v0.6

This directory is the English technical note and [interactive qualification explorer](index.html) for real-software computer-use environments. The [PDF](EnvLoop-Computer-Use-Qualification-Report.pdf) and [manuscript source](EnvLoop-Computer-Use-Qualification-Report.md) describe observed one-task controls and the proposed evaluation protocol. They are **not** the unrun four-researcher, six-application result study.

The site's embedded data comes from [`v0.6-qualification-report-data.json`](../evidence/v0.6-qualification-report-data.json). The five figures are generated from that evidence by [`build_v06_qualification_figures.py`](../../tools/build_v06_qualification_figures.py). The PDF uses [`build_v06_qualification_report.py`](../../tools/build_v06_qualification_report.py), and the self-contained site uses [`build_v06_qualification_site.py`](../../tools/build_v06_qualification_site.py). No authenticated Office URL, test account identifier, private HAR, or evaluator-only answer workbook is included.

To rebuild after reviewing source evidence:

```bash
python3 tools/build_v06_qualification_figures.py
python3 tools/build_v06_qualification_report.py
python3 tools/build_v06_qualification_site.py
python3 tools/validate_v06_qualification_release.py --visually-reviewed-pages 6 --interactive-site-checked
```

The final validation argument is a human review declaration. Render and inspect every PDF page again after any report or figure change before using it. A future full results release requires admitted 100-task cells, actual checkpoint lineages, official task outcomes, and complete cost/failure accounting.
