"""Source-only, field-limited validation of evaluator-private SEC skill cards.

This module never opens a final workbook, case JSON, answer, or Office session.
The private registry supplies only the exact held-out graph reservations.  A
separate reviewer must approve the semantic mapping before the existing
transfer-source gate can accept the cards.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from tools.office_transfer_source_gate_v1 import EXCEL_SCHEMA, EXCEL_SPLIT_SHA
from ppt_wdi_factory import plan as ppt


SCHEMA = "envloop-sec-excel-transfer-skill-cards-audit-public-v1"
CARD_KEYS = {
    "final_graph_reservation", "causal_skill_atoms", "dependency_edges",
    "minimum_target_edits", "skill_signature_sha256",
    "final_template_sha256", "independent_skill_review",
    "source_code_evidence",
}
SOURCE_KEYS = {"path", "sha256", "assertions"}
FAULT_GUARD = re.compile(r"faults\.size\s*!==\s*9")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CELL = re.compile(r"\b[A-Z]{1,3}[1-9][0-9]{0,5}\b")
ACCESSION = re.compile(r"\b[0-9]{10}-[0-9]{2}-[0-9]{6}\b")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _canonical(value: object) -> bytes:
    return ppt.canonical(value)


def _connected_dag(atoms: list[str], edges: list[list[str]]) -> bool:
    if len(set(atoms)) != len(atoms) or len(set(map(tuple, edges))) != len(edges):
        return False
    vertices = set(atoms)
    if any(a == b or a not in vertices or b not in vertices for a, b in edges):
        return False
    if set(x for edge in edges for x in edge) != vertices:
        return False
    indegree = {atom: 0 for atom in atoms}
    children = {atom: [] for atom in atoms}
    undirected = {atom: set() for atom in atoms}
    for left, right in edges:
        indegree[right] += 1
        children[left].append(right)
        undirected[left].add(right)
        undirected[right].add(left)
    queue = [atom for atom, degree in indegree.items() if degree == 0]
    seen = 0
    longest = {atom: 0 for atom in atoms}
    while queue:
        node = queue.pop()
        seen += 1
        for child in children[node]:
            longest[child] = max(longest[child], longest[node] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    reachable = {atoms[0]}
    pending = [atoms[0]]
    while pending:
        for neighbor in undirected[pending.pop()] - reachable:
            reachable.add(neighbor)
            pending.append(neighbor)
    return (seen == len(atoms) and reachable == vertices and
            max(longest.values()) >= 3)


def validate(*, registry_path: Path, cards_path: Path,
             source_root: Path, expected_registry_sha: str = EXCEL_SPLIT_SHA,
             commitment_salt: bytes | None = None) -> dict:
    registry_raw = registry_path.read_bytes()
    _require(_sha(registry_raw) == expected_registry_sha,
             "private_140_slot_registry_hash_changed")
    registry = json.loads(registry_raw)
    slots = registry.get("slots", [])
    _require(registry.get("schema") == "private-excel-20-20-100-reservations-v1" and
             len(slots) == 140 and
             Counter(row.get("split") for row in slots) ==
             {"train": 20, "selection": 20, "final": 100},
             "private_140_slot_registry_shape_changed")
    final_graphs = {row.get("semantic_template_reservation") for row in slots
                    if row.get("split") == "final"}
    _require(len(final_graphs) == 13 and None not in final_graphs,
             "private_final_graph_set_not_13")

    cards_raw = cards_path.read_bytes()
    cards_doc = json.loads(cards_raw)
    cards = cards_doc.get("cards", [])
    _require(set(cards_doc) == {"schema", "registry_sha256", "cards"} and
             cards_doc.get("schema") == EXCEL_SCHEMA and
             cards_doc.get("registry_sha256") == expected_registry_sha and
             isinstance(cards, list) and len(cards) == 13,
             "private_skill_card_package_incomplete")
    _require({c.get("final_graph_reservation") for c in cards} == final_graphs,
             "private_skill_cards_do_not_cover_exact_final_graphs")

    all_source_paths: set[str] = set()
    signatures: set[str] = set()
    reviewed = 0
    source_guard_count = 0
    for card in cards:
        _require(set(card) == CARD_KEYS, "skill_card_has_unexpected_or_missing_field")
        atoms, edges = card["causal_skill_atoms"], card["dependency_edges"]
        _require(isinstance(atoms, list) and 3 <= len(atoms) <= 12 and
                 all(isinstance(a, str) and 12 <= len(a) <= 160 for a in atoms) and
                 isinstance(edges, list) and len(edges) >= len(atoms) - 1 and
                 all(isinstance(e, list) and len(e) == 2 and
                     all(isinstance(x, str) for x in e) for e in edges) and
                 _connected_dag(atoms, edges),
                 "skill_card_dependency_graph_invalid")
        _require(not CELL.search(" ".join(atoms)) and
                 not ACCESSION.search(" ".join(atoms)),
                 "skill_card_contains_cell_or_accession")
        _require(card["minimum_target_edits"] == 9,
                 "minimum_target_depth_not_nine_source_faults")
        signature = _sha(_canonical({"causal_skill_atoms": atoms,
                                     "dependency_edges": edges}))
        _require(card["skill_signature_sha256"] == signature and
                 signature not in signatures,
                 "skill_signature_missing_changed_or_duplicate")
        signatures.add(signature)
        sources = card["source_code_evidence"]
        _require(isinstance(sources, list) and sources,
                 "skill_card_lacks_generator_source")
        source_bindings = []
        for item in sources:
            _require(isinstance(item, dict) and set(item) == SOURCE_KEYS and
                     isinstance(item["path"], str) and
                     isinstance(item["sha256"], str) and
                     HEX64.fullmatch(item["sha256"]) is not None and
                     isinstance(item["assertions"], list) and
                     all(isinstance(s, str) and 4 <= len(s) <= 160
                         for s in item["assertions"]),
                     "source_evidence_entry_invalid")
            rel = Path(item["path"])
            _require(not rel.is_absolute() and ".." not in rel.parts and
                     rel.suffix == ".mjs" and
                     (rel.parts[:1] == ("sec_excel_factory",) or
                      rel.parts[:2] == ("work", "private-excel")),
                     "generator_path_outside_allowed_source_roots")
            source = source_root / rel
            raw = source.read_bytes()
            _require(_sha(raw) == item["sha256"],
                     "generator_source_hash_changed")
            decoded = raw.decode("utf-8")
            _require(FAULT_GUARD.search(decoded) is not None,
                     "generator_nine_fault_guard_missing")
            _require(all(fragment in decoded for fragment in
                         item["assertions"]),
                     "generator_semantic_source_assertion_missing")
            source_guard_count += 1
            all_source_paths.add(item["path"])
            source_bindings.append({"path": item["path"],
                                    "sha256": item["sha256"]})
        _require(sum(len(x["assertions"]) for x in sources) >= 3,
                 "graph_skill_lacks_three_source_assertions")
        _require(card["final_template_sha256"] ==
                 _sha(_canonical(source_bindings)),
                 "final_generator_bundle_commitment_changed")
        _require(type(card["independent_skill_review"]) is bool,
                 "independent_review_flag_invalid")
        reviewed += int(card["independent_skill_review"])

    _require(source_guard_count == len(all_source_paths),
             "generator_source_reused_across_distinct_graph_cards")
    status = "reviewed_source_bound" if reviewed == 13 else "independent_review_pending"
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "private_registry_sha256": expected_registry_sha,
        "exact_final_graphs_covered": 13,
        "source_code_modules_bound": source_guard_count,
        "nine_fault_guards_verified": source_guard_count,
        "unique_skill_signatures": len(signatures),
        "independently_reviewed_skill_cards": reviewed,
        "train_only_analogues_materialized": 0,
        "original_excel_gui_admitted": 0,
        "official_final_admitted": 0,
        "model_calls": 0,
    }
    if commitment_salt is not None:
        _require(len(commitment_salt) == 32,
                 "private_commitment_salt_must_be_32_bytes")
        receipt["private_skill_cards_salted_commitment_sha256"] = _sha(
            commitment_salt + cards_raw)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-registry", type=Path, required=True)
    parser.add_argument("--private-cards", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--private-commitment-salt", type=Path)
    parser.add_argument("--public-receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = validate(registry_path=args.private_registry,
                       cards_path=args.private_cards,
                       source_root=args.source_root,
                       commitment_salt=args.private_commitment_salt.read_bytes()
                       if args.private_commitment_salt else None)
    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.public_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
