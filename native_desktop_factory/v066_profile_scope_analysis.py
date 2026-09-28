"""Offline hypothesis test for content-neutral LibreOffice profile identity.

This never changes the frozen Desktop acceptance rule. It replaces only
document-specific names/content inside three exact history/recovery XML items,
while retaining entry counts, module/filter/state fields, every other XML
property, and every non-registry profile file hash. The two known prompt
timestamps receive the existing narrow numeric normalization.
Equality under this proposed scope is exploratory, not task admission.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .profile_canonical import canonical_registry, digest


OOR_PATH = "{http://openoffice.org/2001/registry}path"
OOR_NAME = "{http://openoffice.org/2001/registry}name"
PICKLIST_ITEMS = ("/org.openoffice.Office.Histories/Histories/"
                  "org.openoffice.Office.Histories:HistoryInfo['PickList']/ItemList")
PICKLIST_ORDER = ("/org.openoffice.Office.Histories/Histories/"
                  "org.openoffice.Office.Histories:HistoryInfo['PickList']/OrderList")
RECOVERY_LIST = "/org.openoffice.Office.Recovery/RecoveryList"
DOCUMENT_CONTENT_PROPS = {
    PICKLIST_ITEMS: frozenset({"Title", "Thumbnail"}),
    PICKLIST_ORDER: frozenset({"HistoryItemRef"}),
    RECOVERY_LIST: frozenset({"Title", "OriginalURL", "TempURL",
                              "TemplateURL"}),
}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _structural_node(node: ET.Element) -> object:
    children = [_structural_node(child) for child in node]
    children.sort(key=lambda child: json.dumps(
        child, sort_keys=True, separators=(",", ":")))
    return [node.tag, sorted(node.attrib.items()),
            node.text.strip() if node.text else "", children]


def scoped_registry(raw: bytes) -> object:
    root = ET.fromstring(canonical_registry(raw))
    counts = {path: 0 for path in DOCUMENT_CONTENT_PROPS}
    for item in root.iter():
        path = item.attrib.get(OOR_PATH)
        if path in counts:
            counts[path] += 1
            for node in item:
                if not node.tag.endswith("node"):
                    raise ValueError("History/recovery item contains another node type")
                if path in (PICKLIST_ITEMS, RECOVERY_LIST):
                    node.attrib[OOR_NAME] = "<document>"
                for prop in node:
                    if not prop.tag.endswith("prop"):
                        raise ValueError("History/recovery entry contains another property type")
                    if prop.attrib.get(OOR_NAME) in DOCUMENT_CONTENT_PROPS[path]:
                        if len(prop) != 1 or not prop[0].tag.endswith("value"):
                            raise ValueError("Document-content property shape changed")
                        prop[0].text = "<nonempty>" if prop[0].text else ""
    if set(counts.values()) != {1}:
        raise ValueError("Expected exactly three document/session history items")
    return _structural_node(root)


def scoped_profile(rows: list[dict], registry_raw: bytes) -> str:
    if type(rows) is not list or not 1 <= len(rows) <= 500:
        raise ValueError("Profile manifest is absent or unbounded")
    files = {}
    for row in rows:
        relative = row.get("path")
        sha = row.get("sha256")
        size = row.get("bytes")
        if (type(relative) is not str or not relative or
                relative.startswith("/") or ".." in Path(relative).parts or
                type(sha) is not str or not HEX64.fullmatch(sha) or
                type(size) is not int or size <= 0 or relative in files):
            raise ValueError("Profile file manifest row is unsafe")
        files[relative] = sha
    if files.pop("registrymodifications.xcu", None) != digest(registry_raw):
        raise ValueError("Profile registry bytes are not manifest-bound")
    value = {"nonregistry_files": sorted(files.items()),
             "scoped_registry": scoped_registry(registry_raw)}
    return digest(json.dumps(value, sort_keys=True,
                             separators=(",", ":")).encode())


def compare_captures(*, first_manifest: Path, first_registry: Path,
                     second_manifest: Path, second_registry: Path) -> dict:
    first_rows = json.loads(first_manifest.read_bytes())
    second_rows = json.loads(second_manifest.read_bytes())
    first_raw, second_raw = first_registry.read_bytes(), second_registry.read_bytes()
    first = scoped_profile(first_rows, first_raw)
    second = scoped_profile(second_rows, second_raw)
    files_a = {row["path"]: row["sha256"] for row in first_rows}
    files_b = {row["path"]: row["sha256"] for row in second_rows}
    common = set(files_a) & set(files_b)
    return {
        "schema": "cua-native-wdi-v066-profile-scope-analysis-v1",
        "scope": "offline_exploratory_not_a_frozen_acceptance_rule",
        "profile_paths_equal": set(files_a) == set(files_b),
        "common_profile_file_count": len(common),
        "identical_nonregistry_file_hashes": sum(
            files_a[path] == files_b[path] for path in common
            if path != "registrymodifications.xcu"),
        "scoped_fingerprints_equal": first == second,
        "historical_baseline_raw_reconstructed": False,
        "official_final_admissions": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-manifest", type=Path, required=True)
    parser.add_argument("--first-registry", type=Path, required=True)
    parser.add_argument("--second-manifest", type=Path, required=True)
    parser.add_argument("--second-registry", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare_captures(
        first_manifest=args.first_manifest,
        first_registry=args.first_registry,
        second_manifest=args.second_manifest,
        second_registry=args.second_registry),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
