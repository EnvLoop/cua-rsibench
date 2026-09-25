"""Fail-closed structural screen for a new evaluator-held Excel 20/20/100 split.

This is a pre-admission screen. Passing it does not prove source authenticity,
Excel-web execution, hidden-set sealing, or a model score.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_SPLITS = {"train": 20, "selection": 20, "final": 100}
MAX_TASKS_PER_ISSUER = 5
MIN_FINAL_WORKFLOWS = 10
PUBLIC_WORKFLOWS = {
    "integrated_close", "rpo_contract_obligations", "debt_cash_capacity",
    "eps_shareholder_return", "lease_maturity", "tax_provision",
    "goodwill_intangibles", "receivables_allowance", "cashflow_quality",
    "ppe_carrying_value",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def public_issuers() -> set[int]:
    direct = json.loads((ROOT / "sec_excel_factory/candidate_audit_fetched_2026-09-24.json").read_text())
    anchors = json.loads((ROOT / "docs/evidence/sec-ten-official-crosschecked-anchors-2026-09-25.json").read_text())
    ids = {int(r["cik"]) for r in direct["results"]} | {int(r["cik"]) for r in anchors["sources"]}
    if len(ids) != 28 or len(PUBLIC_WORKFLOWS) != 10:
        raise ValueError("public_development_inventory_changed; review the isolation registry")
    return ids


def screen(tasks: list[dict], public_ciks: set[int] | None = None,
           public_workflows: set[str] | None = None) -> dict:
    public_ciks = public_issuers() if public_ciks is None else public_ciks
    public_workflows = PUBLIC_WORKFLOWS if public_workflows is None else public_workflows
    errors: list[str] = []
    counts = Counter(t.get("split") for t in tasks)
    if any(counts.get(split, 0) != need for split, need in REQUIRED_SPLITS.items()):
        errors.append("split_counts_must_be_20_train_20_selection_100_final")
    if set(counts) - set(REQUIRED_SPLITS):
        errors.append("unknown_split")
    ids = [t.get("task_id") for t in tasks]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        errors.append("task_id_missing_or_reused")
    issuer_splits: dict[int, set[str]] = defaultdict(set)
    issuer_counts = Counter()
    accession_splits: dict[str, set[str]] = defaultdict(set)
    template_splits: dict[str, set[str]] = defaultdict(set)
    template_hashes: dict[str, set[str]] = defaultdict(set)
    semantic_hash_splits: dict[str, set[str]] = defaultdict(set)
    semantic_hash_families: dict[str, set[str]] = defaultdict(set)
    issuer_template_pairs = Counter()
    final_issuers: set[int] = set()
    final_templates: set[str] = set()
    for t in tasks:
        split = t.get("split")
        try:
            cik = int(t["issuer_cik"])
            if cik <= 0:
                raise ValueError("nonpositive")
        except (KeyError, TypeError, ValueError):
            errors.append("issuer_cik_missing_or_invalid")
            continue
        issuer_counts[cik] += 1
        issuer_splits[cik].add(split)
        if cik in public_ciks:
            errors.append("public_development_issuer_reused")
        accession = t.get("original_10k_accession")
        if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
            errors.append("original_10k_accession_missing_or_invalid")
        else:
            accession_splits[accession].add(split)
        template = t.get("template_family")
        semantic_hash = t.get("template_semantic_sha256")
        if not isinstance(template, str) or not template:
            errors.append("template_family_missing")
        else:
            template_splits[template].add(split)
            issuer_template_pairs[(cik, template)] += 1
            if template in public_workflows:
                errors.append("public_development_template_reused")
            if isinstance(semantic_hash, str):
                template_hashes[template].add(semantic_hash)
                semantic_hash_splits[semantic_hash].add(split)
                semantic_hash_families[semantic_hash].add(template)
        for key in ("source_excerpt_sha256", "template_semantic_sha256",
                    "actor_sha256", "reference_sha256"):
            if not isinstance(t.get(key), str) or not SHA256.fullmatch(t[key]):
                errors.append(f"{key}_missing_or_invalid")
        if t.get("source_provenance_tier") != "independently_verified_exact_facts":
            errors.append("source_provenance_not_independently_verified")
        if not isinstance(t.get("verified_canonical_fact_count"), int) or t["verified_canonical_fact_count"] < 3:
            errors.append("insufficient_verified_canonical_facts")
        if split == "final":
            final_issuers.add(cik)
            if isinstance(template, str):
                final_templates.add(template)
    if any(n > MAX_TASKS_PER_ISSUER for n in issuer_counts.values()):
        errors.append("more_than_five_tasks_per_issuer")
    if any(len(s) > 1 for s in issuer_splits.values()):
        errors.append("issuer_crosses_splits")
    if any(len(s) > 1 for s in accession_splits.values()):
        errors.append("accession_crosses_splits")
    if any(len(s) > 1 for s in template_splits.values()):
        errors.append("semantic_template_family_crosses_splits")
    if any(len(hashes) != 1 for hashes in template_hashes.values()):
        errors.append("template_family_has_inconsistent_semantic_hash")
    if any(len(splits) > 1 for splits in semantic_hash_splits.values()):
        errors.append("semantic_template_hash_crosses_splits")
    if any(len(families) > 1 for families in semantic_hash_families.values()):
        errors.append("semantic_template_hash_reused_under_alias")
    if any(n > 1 for n in issuer_template_pairs.values()):
        errors.append("issuer_template_pair_repeated")
    for key in ("actor_sha256", "reference_sha256"):
        digests = [t.get(key) for t in tasks]
        if len(set(digests)) != len(digests):
            errors.append(f"{key}_reused_across_tasks")
    if len(final_issuers) < 20:
        errors.append("fewer_than_twenty_final_issuer_families")
    if len(final_templates) < MIN_FINAL_WORKFLOWS:
        errors.append("fewer_than_ten_final_workflow_families")
    if len(issuer_counts) < 28:
        errors.append("fewer_than_twenty_eight_private_issuer_families")
    return {"schema": "sec-private-excel-split-structural-screen-v1",
            "status": "structural_candidate_only" if not errors else "blocked",
            "task_counts": {k: counts.get(k, 0) for k in REQUIRED_SPLITS},
            "registered_private_issuer_families": len(issuer_counts),
            "registered_final_issuer_families": len(final_issuers),
            "registered_final_workflow_families": len(final_templates),
            "public_development_issuer_families_excluded": len(public_ciks),
            "public_development_workflow_families_excluded": len(public_workflows),
            "max_tasks_per_issuer": MAX_TASKS_PER_ISSUER,
            "requirements": {"split_sizes": REQUIRED_SPLITS,
                             "minimum_private_issuer_families": 28,
                             "minimum_final_issuer_families": 20,
                             "minimum_final_workflow_families": MIN_FINAL_WORKFLOWS,
                             "source_issuer_and_template_isolation": True},
            "errors": sorted(set(errors)),
            "official_excel_web_admissions": 0,
            "boundary": "Passing this screen never substitutes for independent source review, saved/downloaded Excel-web readback, fresh-copy reset, or hidden answer custody."}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-manifest", type=Path,
                   help="Evaluator-held JSON with a tasks array; do not commit this manifest")
    p.add_argument("--public-out", type=Path, required=True)
    args = p.parse_args()
    tasks = [] if args.private_manifest is None else json.loads(args.private_manifest.read_text())["tasks"]
    result = screen(tasks)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "task_counts": result["task_counts"],
                      "errors": result["errors"]}))
    raise SystemExit(0 if result["status"] == "structural_candidate_only" else 1)


if __name__ == "__main__":
    main()
