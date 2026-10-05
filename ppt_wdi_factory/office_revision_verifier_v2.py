"""Allow the web editor's validated, metadata-only revision sidecar.

The original WDI verifier is unchanged. Task text, slide geometry, charts,
workbooks, and all other package parts keep its existing comparison rules.
"""
from datetime import datetime
import argparse
import json
from pathlib import Path
import re
from types import FunctionType, SimpleNamespace
import xml.etree.ElementTree as ET

from . import verify as original

PART = 'ppt/revisionInfo.xml'
REV = '{http://schemas.microsoft.com/office/powerpoint/2015/10/main}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
REL_TYPE = 'http://schemas.microsoft.com/office/2015/10/relationships/revisionInfo'
MIME = 'application/vnd.ms-powerpoint.revisioninfo+xml'
# Microsoft MS-PPTX section 5.5 specifies v as xsd:unsignedInt:
# https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/e5047fb0-5d6d-421f-bfe9-ce8cd549843f
GUID = re.compile(r'\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}')


def revision_metadata(members):
    """Remove only a complete, strictly validated revision metadata triple."""
    parts = dict(members)
    relationships = original.package_guard.xml(parts['ppt/_rels/presentation.xml.rels'])
    content_types = original.package_guard.xml(parts['[Content_Types].xml'])
    refs = [n for n in relationships if n.get('Type') == REL_TYPE or
            n.get('Target') == 'revisionInfo.xml']
    overrides = [n for n in content_types if n.get('PartName') == '/' + PART or
                 n.get('ContentType') == MIME]
    if PART not in parts:
        if refs or overrides:
            raise ValueError('Revision metadata references an absent part')
        return parts
    if len(parts[PART]) > 32768 or len(refs) != 1 or len(overrides) != 1:
        raise ValueError('Revision metadata triple is incomplete or ambiguous')
    ref, override = refs[0], overrides[0]
    if (ref.tag != REL + 'Relationship' or set(ref.attrib) != {'Id', 'Type', 'Target'} or
            ref.get('Type') != REL_TYPE or ref.get('Target') != 'revisionInfo.xml' or
            not re.fullmatch(r'rId[1-9][0-9]*', ref.get('Id', '')) or
            sum(n.get('Id') == ref.get('Id') for n in relationships) != 1 or
            override.tag != CT + 'Override' or override.attrib !=
            {'PartName': '/' + PART, 'ContentType': MIME}):
        raise ValueError('Revision metadata package binding changed')
    root = original.package_guard.xml(parts[PART])
    if (root.tag != REV + 'revInfo' or root.attrib or len(root) != 1 or
            root[0].tag != REV + 'revLst' or root[0].attrib or not 1 <= len(root[0]) <= 256):
        raise ValueError('Unsupported revision metadata structure')
    for node in root.iter():
        if (node.text or '').strip() or (node.tail or '').strip():
            raise ValueError('Revision metadata contains text content')
    for client in root[0]:
        if (client.tag != REV + 'client' or len(client) or
                set(client.attrib) != {'id', 'v', 'dt'} or
                GUID.fullmatch(client.get('id', '')) is None or
                re.fullmatch(r'0|[1-9][0-9]{0,9}', client.get('v', '')) is None or
                int(client.get('v', '0')) > 4294967295):
            raise ValueError('Unsupported revision client metadata')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?', client.attrib['dt']):
            raise ValueError('Invalid revision client timestamp')
        datetime.fromisoformat(client.attrib['dt'])
    relationships.remove(ref)
    content_types.remove(override)
    parts['ppt/_rels/presentation.xml.rels'] = ET.tostring(relationships, encoding='utf-8')
    parts['[Content_Types].xml'] = ET.tostring(content_types, encoding='utf-8')
    del parts[PART]
    return parts


def verify(source, attempt, oracle):
    if oracle.get('office_web_normalized') is not True:
        return original.verify(source, attempt, oracle)
    def package(path):
        raw, members = original.package_guard.package(path)
        return raw, revision_metadata(members)
    guard = SimpleNamespace(**{**vars(original.package_guard), 'package': package})
    fn = original.verify
    checked = FunctionType(fn.__code__, {**fn.__globals__, 'package_guard': guard},
                           fn.__name__, fn.__defaults__, fn.__closure__)
    result = checked(source, attempt, oracle)
    return {**result, 'revision_metadata_policy': 'validated-web-revision-sidecar-only-v2'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--oracle', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.baseline, args.candidate,
                           json.loads(args.oracle.read_bytes())), sort_keys=True))


if __name__ == '__main__':
    main()
