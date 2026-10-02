"""Narrow audit-only canonicalization of two LibreOffice prompt timestamps.

This does not mutate a live sandbox or create an official environment freeze.
It proves whether two captured profiles differ only in the two named numeric
fields and refuses any other XML or profile-file difference.
"""

from __future__ import annotations

import hashlib
import json
import re


VOLATILE_FIELDS = (b"LastTimeDonateShown", b"LastTimeGetInvolvedShown")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_registry(raw: bytes) -> bytes:
    if type(raw) is not bytes or not raw.startswith(b"<?xml"):
        raise ValueError("Expected LibreOffice registry XML bytes")
    result = raw
    for name in VOLATILE_FIELDS:
        pattern = re.compile(
            rb'(<prop oor:name="' + name + rb'"[^>]*><value>)([0-9]+)(</value></prop>)')
        if len(pattern.findall(result)) != 1:
            raise ValueError("Expected exactly one numeric LibreOffice prompt timestamp")
        result = pattern.sub(lambda match: match.group(1) + b"0" + match.group(3), result)
    return result


def canonical_profile_tree(file_rows: list[dict], registry_raw: bytes) -> str:
    files = {row["path"]: row["sha256"] for row in file_rows}
    if len(files) != len(file_rows) or files.get("registrymodifications.xcu") != digest(registry_raw):
        raise ValueError("Profile manifest does not bind the captured registry")
    files["registrymodifications.xcu"] = digest(canonical_registry(registry_raw))
    ordered = sorted(files.items())
    return digest(json.dumps(ordered, sort_keys=True,
                             separators=(",", ":")).encode())
