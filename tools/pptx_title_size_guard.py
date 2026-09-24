"""Narrow independent guard for a direct title-run font-size task.

This guards paired PPTX artifacts. It neither drives nor proves Microsoft GUI
execution. Freeze the source contract in trusted evaluator storage before the
actor runs. A PowerPoint-normalized source must be frozen separately from a raw
download. A narrowly scoped Office metadata allowance can be enabled only for
such an evaluator-generated, normalized baseline.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import zipfile
import xml.etree.ElementTree as ET

MAX_PACKAGE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 5000
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
SCHEMA = 'pptx-direct-title-font-size-guard-v1'
CP = '{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}'
DCTERMS = '{http://purl.org/dc/terms/}'
P13_COMMAND = '{http://schemas.microsoft.com/office/powerpoint/2013/main/command}'
D13_COMMAND = '{http://schemas.microsoft.com/office/drawing/2013/main/command}'
P15 = '{http://schemas.microsoft.com/office/powerpoint/2015/10/main}'
OFFICE_DERIVED_PARTS = frozenset({
    'docProps/core.xml', 'docProps/thumbnail.jpeg',
    'ppt/changesInfos/changesInfo1.xml', 'ppt/revisionInfo.xml',
})


class ArtifactUnavailable(ValueError):
    """An artifact cannot be read or bound reliably; never a model zero."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def package(path):
    try:
        if Path(path).stat().st_size > MAX_PACKAGE_BYTES:
            raise ArtifactUnavailable('compressed PPTX package exceeds the byte bound')
        data = Path(path).read_bytes()
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or len(names) > MAX_MEMBERS:
                raise ArtifactUnavailable('duplicate or excessive PPTX package members')
            if sum(member.file_size for member in members) > MAX_PACKAGE_BYTES:
                raise ArtifactUnavailable('PPTX package exceeds the byte bound')
            result = {}
            for member in members:
                name = PurePosixPath(member.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in member.filename or member.file_size > MAX_MEMBER_BYTES:
                    raise ArtifactUnavailable('unsafe or oversized PPTX package member')
                if member.is_dir():
                    continue
                result[member.filename] = archive.read(member)
        if '[Content_Types].xml' not in result or 'ppt/presentation.xml' not in result:
            raise ArtifactUnavailable('required PPTX package parts are absent')
        return data, result
    except (OSError, zipfile.BadZipFile, RuntimeError, ET.ParseError) as error:
        raise ArtifactUnavailable(type(error).__name__) from error


def xml(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ArtifactUnavailable('DTD/entity declarations are not admitted')
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        raise ArtifactUnavailable('invalid XML package part') from error


def canonical(element):
    return ET.canonicalize(ET.tostring(element, encoding='unicode'), rewrite_prefixes=True)


def title_shape(slide, shape_id):
    matches = [shape for shape in slide.iter(P + 'sp')
               if (node := shape.find(P + 'nvSpPr/' + P + 'cNvPr')) is not None and node.get('id') == str(shape_id)]
    if len(matches) != 1:
        raise ArtifactUnavailable('target title shape identity is missing or ambiguous')
    shape = matches[0]
    placeholder = shape.find(P + 'nvSpPr/' + P + 'nvPr/' + P + 'ph')
    if placeholder is None or placeholder.get('type') not in ('title', 'ctrTitle'):
        raise ArtifactUnavailable('frozen target is not a title placeholder')
    return shape


def nonempty_runs(shape):
    return [run for run in shape.iter(A + 'r') if (run.findtext(A + 't') or '').strip()]


def erase_permitted_font_sizes(slide, shape_id):
    result = copy.deepcopy(slide)
    shape = title_shape(result, shape_id)
    for run in nonempty_runs(shape):
        props = run.find(A + 'rPr')
        if props is not None:
            props.attrib.pop('sz', None)
            if not props.attrib and not len(props) and not (props.text or '').strip():
                run.remove(props)
    return result


def office_derived_part_equal(name, left, right):
    """Ignore only observed Office save bookkeeping, never slide content.

    The thumbnail is a derived JPEG preview. Its bytes may change when the
    target title changes; all media, slides, relationships, and layouts remain
    strictly compared elsewhere in the package.
    """
    if name == 'docProps/thumbnail.jpeg':
        return all(data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9') for data in (left, right))
    before, after = xml(left), xml(right)
    if name == 'docProps/core.xml':
        for root in (before, after):
            for node in root.iter():
                if node.tag in (CP + 'revision', DCTERMS + 'modified'):
                    node.text = None
    elif name == 'ppt/changesInfos/changesInfo1.xml':
        for root in (before, after):
            for node in root.iter():
                if node.tag in (P13_COMMAND + 'chgData', D13_COMMAND + 'chgData'):
                    for key in ('clId', 'dt', 'v'):
                        node.attrib.pop(key, None)
    elif name == 'ppt/revisionInfo.xml':
        for root in (before, after):
            for node in root.iter():
                if node.tag == P15 + 'client':
                    for key in ('dt', 'id', 'v'):
                        node.attrib.pop(key, None)
    else:
        raise ArtifactUnavailable('unknown Office-derived part')
    return canonical(before) == canonical(after)


def freeze_contract(original, target_part, shape_id, target_size_pt, *, office_web_normalized=False):
    data, members = package(original)
    if target_part not in members or not target_part.startswith('ppt/slides/'):
        raise ArtifactUnavailable('target slide part is absent')
    shape = title_shape(xml(members[target_part]), shape_id)
    if not nonempty_runs(shape) or not 1 <= target_size_pt <= 400 or not math.isfinite(target_size_pt):
        raise ArtifactUnavailable('nonempty title and finite target size required')
    return {'schema': SCHEMA, 'original_sha256': sha(data),
            'original_member_sha256': {name: sha(content) for name, content in sorted(members.items())},
            'target_part': target_part, 'target_shape_id': str(shape_id), 'target_size_pt': target_size_pt,
            'permitted_mutation': 'only the sz attribute of nonempty target title a:r/a:rPr nodes',
            'office_web_normalized': bool(office_web_normalized),
            'normalization_boundary': ('Trusted evaluator-generated Office-saved baseline; only four specified derived package parts have narrow allowances.'
                                       if office_web_normalized else
                                       'No application metadata normalization is assumed; freeze a separate normalized baseline when using Microsoft PowerPoint.')}


def verify(original, modified, contract):
    try:
        if contract.get('schema') != SCHEMA:
            raise ArtifactUnavailable('unsupported guard contract')
        original_data, before = package(original)
        _, after = package(modified)
        if sha(original_data) != contract['original_sha256'] or {name: sha(data) for name, data in before.items()} != contract['original_member_sha256']:
            raise ArtifactUnavailable('trusted source artifact changed')
        target = contract['target_part']
        if target not in after:
            return {'status': 'scored', 'score': 0.0, 'target_correct': False,
                    'preservation_pass': False, 'unexpected_parts': [target], 'reason': 'target slide removed'}
        before_slide, after_slide = xml(before[target]), xml(after[target])
        try:
            changed_title = title_shape(after_slide, contract['target_shape_id'])
            runs = nonempty_runs(changed_title)
        except ArtifactUnavailable:
            runs = []
        sizes = []
        for run in runs:
            props = run.find(A + 'rPr')
            try:
                size = float(props.get('sz')) / 100 if props is not None else None
            except (TypeError, ValueError):
                size = None
            sizes.append(size)
        target_correct = bool(sizes) and all(size is not None and math.isfinite(size) and
                                             abs(size - contract['target_size_pt']) <= .5 for size in sizes)
        unexpected = set(before) ^ set(after)
        for name in set(before) & set(after):
            if name == target:
                try:
                    left = canonical(erase_permitted_font_sizes(before_slide, contract['target_shape_id']))
                    right = canonical(erase_permitted_font_sizes(after_slide, contract['target_shape_id']))
                    if left != right:
                        unexpected.add(name)
                except ArtifactUnavailable:
                    unexpected.add(name)
            elif before[name] != after[name]:
                # XML syntax/prefix differences are not semantic edits. Text,
                # attributes, relationships, object ordering and content remain.
                if contract.get('office_web_normalized') is True and name in OFFICE_DERIVED_PARTS:
                    if not office_derived_part_equal(name, before[name], after[name]):
                        unexpected.add(name)
                elif name.endswith(('.xml', '.rels')):
                    if canonical(xml(before[name])) != canonical(xml(after[name])):
                        unexpected.add(name)
                else:
                    unexpected.add(name)
        preservation = not unexpected
        return {'status': 'scored', 'score': float(target_correct and preservation),
                'target_correct': target_correct, 'preservation_pass': preservation,
                'unexpected_parts': sorted(unexpected), 'observed_title_sizes_pt': sizes,
                'scope': 'artifact-only direct-run font-size guard; no GUI execution claim'}
    except (ArtifactUnavailable, KeyError, TypeError) as error:
        return {'status': 'infrastructure_error', 'score': None, 'reason': str(error),
                'error_type': type(error).__name__}


def combine_upstream(upstream_score, guard_result, upstream_error_type=None):
    """A verifier/renderer exception must remain undefined, even if wrapped as 0."""
    if upstream_error_type or guard_result.get('status') != 'scored':
        return {'status': 'infrastructure_error', 'score': None, 'strict_success': None,
                'error_type': upstream_error_type or guard_result.get('error_type', 'GuardUnavailable')}
    if type(upstream_score) not in (int, float) or not math.isfinite(upstream_score) or not 0 <= upstream_score <= 1:
        return {'status': 'infrastructure_error', 'score': None, 'strict_success': None, 'error_type': 'InvalidUpstreamScore'}
    admitted = guard_result.get('score') == 1.0 and upstream_score == 1.0
    return {'status': 'scored', 'score': float(admitted), 'strict_success': admitted,
            'upstream_partial_score': upstream_score, 'independent_preservation_pass': guard_result.get('preservation_pass')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    freeze = modes.add_parser('freeze')
    freeze.add_argument('--original', type=Path, required=True)
    freeze.add_argument('--target-part', default='ppt/slides/slide1.xml')
    freeze.add_argument('--shape-id', required=True)
    freeze.add_argument('--target-size-pt', type=float, required=True)
    freeze.add_argument('--office-web-normalized', action='store_true',
                        help='baseline was independently saved by Office before the actor ran')
    freeze.add_argument('--out', type=Path, required=True)
    check = modes.add_parser('verify')
    check.add_argument('--original', type=Path, required=True)
    check.add_argument('--modified', type=Path, required=True)
    check.add_argument('--contract', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'freeze':
        if args.out.exists():
            raise ValueError('refuse to overwrite a frozen guard contract')
        contract = freeze_contract(args.original, args.target_part, args.shape_id, args.target_size_pt,
                                   office_web_normalized=args.office_web_normalized)
        args.out.write_text(json.dumps(contract, indent=2) + '\n')
        print(json.dumps({'contract_written': True, 'original_sha256': contract['original_sha256']}))
    else:
        print(json.dumps(verify(args.original, args.modified, json.loads(args.contract.read_text())), indent=2))


if __name__ == '__main__':
    main()
