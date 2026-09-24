"""Evaluator-side admission for one nonvisual PPT-Eval PowerPoint-web task.

The evaluator must download and freeze an untouched Office-saved copy before
the actor sees the task. This tool does not operate the browser or prove who
performed an edit. It binds the source, baseline, rubric, candidate path and
time in evaluator-only storage, then combines the pinned upstream score with
the independent whole-package guard. Keep contracts and PPTX files private.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

import pptx_title_size_guard as guard

TASK_ID = '4._Pre-Colonial_Filipino_Culture-001'
UPSTREAM_COMMIT = '1b8b55a29e48fdc65d423689b6f2370ad91beeea'
SOURCE_SHA256 = 'cf4574ab7795d6ed17ca2bb731470fdd56f2c3e7aa426a6e0c39f46bdfe51e30'
RUBRIC_SHA256 = '5c7d73218073750ec0db320a895dd83d9dd4e20a37c876f68d3d8b0c41f7d602'
SCHEMA = 'ppt-eval-office-web-admission-v1'
TARGET_SLIDE = 'ppt/slides/slide1.xml'
TARGET_SHAPE_ID = '2'
TARGET_SIZE_PT = 48.0
RESET_SIZE_PT = 42.0
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
SHAPES = {P + name for name in ('sp', 'pic', 'graphicFrame', 'cxnSp')}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slide_number(name):
    match = re.fullmatch(r'ppt/slides/slide([1-9][0-9]*)\.xml', name)
    return int(match.group(1)) if match else None


def shape_records(data):
    root = guard.xml(data)
    records = []
    for shape in root.iter():
        if shape.tag not in SHAPES:
            continue
        cnv = next(shape.iter(P + 'cNvPr'), None)
        records.append((shape.tag, cnv.get('id') if cnv is not None else None,
                        ''.join(node.text or '' for node in shape.iter(A + 't'))))
    return records


def note_body_records(data):
    root = guard.xml(data)
    records = []
    for shape in root.iter(P + 'sp'):
        placeholder = shape.find(P + 'nvSpPr/' + P + 'nvPr/' + P + 'ph')
        kind = placeholder.get('type') if placeholder is not None else None
        if kind != 'sldNum':
            records.append((kind, ''.join(node.text or '' for node in shape.iter(A + 't'))))
    return records


def source_baseline_screen(source, baseline):
    """Reject obvious content loss while allowing Office's XML normalization.

    This is a structural screen, not proof of pixel-identical rendering. The
    evaluator must separately inspect the unchanged Office view before use.
    """
    _, raw = guard.package(source)
    _, saved = guard.package(baseline)
    raw_slides = {name for name in raw if slide_number(name) is not None}
    saved_slides = {name for name in saved if slide_number(name) is not None}
    if raw_slides != saved_slides or not raw_slides:
        raise guard.ArtifactUnavailable('Office baseline changed the slide set')
    for name in raw_slides:
        if shape_records(raw[name]) != shape_records(saved[name]):
            raise guard.ArtifactUnavailable('Office baseline changed slide shape text or identity')
    for prefix in ('ppt/media/', 'ppt/slides/_rels/'):
        raw_parts = {name: raw[name] for name in raw if name.startswith(prefix)}
        saved_parts = {name: saved[name] for name in saved if name.startswith(prefix)}
        if raw_parts != saved_parts:
            raise guard.ArtifactUnavailable('Office baseline changed media or slide relationships')
    raw_notes = {name for name in raw if re.fullmatch(r'ppt/notesSlides/notesSlide[1-9][0-9]*\.xml', name)}
    saved_notes = {name for name in saved if re.fullmatch(r'ppt/notesSlides/notesSlide[1-9][0-9]*\.xml', name)}
    if raw_notes != saved_notes or any(note_body_records(raw[name]) != note_body_records(saved[name]) for name in raw_notes):
        raise guard.ArtifactUnavailable('Office baseline changed speaker note bodies')
    diagrams = {name for name in raw if re.fullmatch(r'ppt/diagrams/(?:data|drawing)[1-9][0-9]*\.xml', name)}
    if diagrams != {name for name in saved if re.fullmatch(r'ppt/diagrams/(?:data|drawing)[1-9][0-9]*\.xml', name)}:
        raise guard.ArtifactUnavailable('Office baseline changed the diagram set')
    for name in diagrams:
        if ''.join(node.text or '' for node in guard.xml(raw[name]).iter(A + 't')) != ''.join(
                node.text or '' for node in guard.xml(saved[name]).iter(A + 't')):
            raise guard.ArtifactUnavailable('Office baseline changed diagram text')
    title = guard.title_shape(guard.xml(saved[TARGET_SLIDE]), TARGET_SHAPE_ID)
    sizes = []
    for run in guard.nonempty_runs(title):
        props = run.find(A + 'rPr')
        sizes.append(float(props.get('sz')) / 100 if props is not None and props.get('sz') is not None else None)
    if sizes and all(size is not None and abs(size - TARGET_SIZE_PT) <= .5 for size in sizes):
        raise guard.ArtifactUnavailable('normalized baseline already satisfies the task')
    return {'slides': len(raw_slides), 'media_parts': sum(name.startswith('ppt/media/') for name in raw),
            'notes': len(raw_notes), 'diagrams': len(diagrams), 'baseline_title_sizes_pt': sizes,
            'package_parts_changed_by_office': sum(raw.get(name) != saved.get(name) for name in set(raw) | set(saved)),
            'limit': 'structural content screen only; visually inspect unchanged Office render'}


def freeze(source, baseline, candidate, rubric, contract_path):
    contract_path = Path(contract_path)
    candidate = Path(candidate).resolve()
    if contract_path.exists() or candidate.exists():
        raise ValueError('contract or candidate already exists; freeze before the actor runs')
    if not Path(source).is_file() or not Path(baseline).is_file() or not Path(rubric).is_file():
        raise guard.ArtifactUnavailable('required source, baseline or rubric is absent')
    if digest(source) != SOURCE_SHA256 or digest(rubric) != RUBRIC_SHA256:
        raise guard.ArtifactUnavailable('source or rubric does not match the pinned PPT-Eval task')
    screen = source_baseline_screen(source, baseline)
    frozen = guard.freeze_contract(baseline, TARGET_SLIDE, TARGET_SHAPE_ID,
                                   TARGET_SIZE_PT, office_web_normalized=True)
    frozen.update({'admission_schema': SCHEMA, 'task_id': TASK_ID, 'source_sha256': digest(source),
                   'rubric_sha256': digest(rubric), 'candidate_path': str(candidate),
                   'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
                   'source_baseline_screen': screen})
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(contract_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(frozen, handle, indent=2)
        handle.write('\n')
    return {'status': 'frozen', 'task_id': TASK_ID, 'source_sha256': frozen['source_sha256'],
            'baseline_sha256': frozen['original_sha256'], 'candidate_path': str(candidate),
            'source_baseline_screen': screen}


@contextmanager
def no_network_or_provider_credentials():
    forbidden = {key: os.environ.pop(key) for key in list(os.environ)
                 if key.endswith('API_KEY') or key in ('CLIENT_ID', 'OPENAI_BASE_URL',
                                                      'ANTHROPIC_BASE_URL', 'RUBRIC_DEFAULT_LLM')}
    previous_flow = os.environ.get('PPTEVAL_ALLOW_DEVICE_FLOW')
    previous_cost_map = os.environ.get('LITELLM_LOCAL_MODEL_COST_MAP')
    os.environ['PPTEVAL_ALLOW_DEVICE_FLOW'] = '0'
    os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    connect, connect_ex = socket.socket.connect, socket.socket.connect_ex

    def denied(*args, **kwargs):
        raise RuntimeError('network disabled during PPT-Eval verification')

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
        os.environ.update(forbidden)
        if previous_flow is None:
            os.environ.pop('PPTEVAL_ALLOW_DEVICE_FLOW', None)
        else:
            os.environ['PPTEVAL_ALLOW_DEVICE_FLOW'] = previous_flow
        if previous_cost_map is None:
            os.environ.pop('LITELLM_LOCAL_MODEL_COST_MAP', None)
        else:
            os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = previous_cost_map


def official_score(upstream_root, rubric, baseline, candidate):
    commit = subprocess.run(['git', '-C', str(upstream_root), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    if commit != UPSTREAM_COMMIT:
        raise guard.ArtifactUnavailable('PPT-Eval source is not the pinned revision')
    changes = subprocess.run(['git', '-C', str(upstream_root), 'status', '--porcelain'],
                             capture_output=True, text=True, check=True).stdout
    if changes.strip():
        raise guard.ArtifactUnavailable('PPT-Eval source checkout is not clean')
    sys.path.insert(0, str(upstream_root))
    try:
        with no_network_or_provider_credentials():
            from ppteval.verify.ppt.verifier import PPTVerifier
            evaluator = PPTVerifier(str(rubric))
            if evaluator._requires_visual_evaluation():
                raise guard.ArtifactUnavailable('this task unexpectedly requires a visual judge')
            score, _ = evaluator.verify(str(baseline), str(candidate), include_reason=False,
                                        compute_strategy='default', non_critical_weight=.3,
                                        conversion_mode='libreoffice+poppler')
            leaves = [{'name': node.name, 'score': node.score}
                      for node in evaluator.rubric_tree.get_all_nodes() if node.is_leaf]
            return score, leaves
    finally:
        sys.path.remove(str(upstream_root))


def verify(source, baseline, candidate, rubric, contract_path, upstream_root):
    contract = json.loads(Path(contract_path).read_text())
    if contract.get('admission_schema') != SCHEMA or contract.get('task_id') != TASK_ID:
        raise guard.ArtifactUnavailable('unknown admission contract')
    if Path(candidate).resolve() != Path(contract['candidate_path']):
        raise guard.ArtifactUnavailable('candidate path differs from frozen evaluator contract')
    if digest(source) != contract['source_sha256'] or digest(rubric) != contract['rubric_sha256']:
        raise guard.ArtifactUnavailable('source or rubric differs from frozen evaluator contract')
    if datetime.fromtimestamp(Path(candidate).stat().st_mtime, timezone.utc) <= datetime.fromisoformat(contract['frozen_at_utc']):
        raise guard.ArtifactUnavailable('candidate predates evaluator freeze')
    guard_result = guard.verify(baseline, candidate, contract)
    if guard_result['status'] != 'scored':
        return {'status': 'infrastructure_error', 'score': None, 'guard': guard_result,
                'official_score': None, 'task_id': TASK_ID}
    try:
        upstream, leaves = official_score(upstream_root, rubric, baseline, candidate)
        combined = guard.combine_upstream(upstream, guard_result)
    except Exception as error:
        upstream, leaves = None, []
        combined = guard.combine_upstream(None, guard_result, type(error).__name__)
    return {'status': combined['status'], 'score': combined['score'],
            'strict_success': combined['strict_success'], 'task_id': TASK_ID,
            'official_score': upstream, 'official_leaves': leaves,
            'guard': guard_result, 'combined': combined,
            'baseline_sha256': contract['original_sha256'], 'candidate_sha256': digest(candidate),
            'scope': 'one PPT-Eval selection-task artifact; GUI and reset must be evidenced separately'}


def verify_reset(source, baseline, candidate, reset_artifact, rubric, contract_path, upstream_root):
    """Check a later GUI-exported rollback without treating it as a model trial."""
    contract = json.loads(Path(contract_path).read_text())
    if contract.get('admission_schema') != SCHEMA or Path(candidate).resolve() != Path(contract['candidate_path']):
        raise guard.ArtifactUnavailable('reset references a different frozen task or candidate')
    if digest(source) != contract['source_sha256'] or digest(rubric) != contract['rubric_sha256']:
        raise guard.ArtifactUnavailable('source or rubric differs from frozen task')
    if digest(baseline) != contract['original_sha256']:
        raise guard.ArtifactUnavailable('frozen Office baseline changed')
    if Path(reset_artifact).stat().st_mtime <= Path(candidate).stat().st_mtime:
        raise guard.ArtifactUnavailable('reset artifact does not follow the edited candidate')
    if digest(reset_artifact) == contract['original_sha256']:
        artifact_result = {'status': 'scored', 'score': 1.0, 'reason': 'byte-identical baseline restored'}
    else:
        reset_contract = guard.freeze_contract(baseline, TARGET_SLIDE, TARGET_SHAPE_ID,
                                               RESET_SIZE_PT, office_web_normalized=True)
        artifact_result = guard.verify(baseline, reset_artifact, reset_contract)
        if artifact_result['status'] == 'scored':
            sizes = artifact_result['observed_title_sizes_pt']
            # The frozen web UI showed 42 pt inherited from its layout. A
            # returned file may retain inherited runs around a newly explicit
            # 42-pt run after Office splits the title selection.
            effective_42 = bool(sizes) and all(
                size is None or abs(size - RESET_SIZE_PT) <= .5 for size in sizes)
            artifact_result['inherited_baseline_42pt_assumed_from_gui'] = True
            artifact_result['effective_reset_42pt'] = effective_42
            artifact_result['score'] = float(effective_42 and artifact_result['preservation_pass'])
    try:
        upstream, _ = official_score(upstream_root, rubric, baseline, reset_artifact)
        official_error = None
    except Exception as error:
        upstream, official_error = None, type(error).__name__
    if artifact_result['status'] != 'scored' or official_error:
        status, passed = 'infrastructure_error', None
    else:
        status = 'checked'
        passed = artifact_result['score'] == 1.0 and upstream == 0.0
    return {'status': status, 'reset_pass': passed, 'task_id': TASK_ID,
            'artifact_reset': artifact_result, 'official_target_score_after_reset': upstream,
            'official_error_type': official_error, 'reset_sha256': digest(reset_artifact),
            'scope': 'one artifact rollback check; cloud-file identity and GUI sequence need separate evidence'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    for mode in ('freeze', 'verify', 'reset'):
        command = modes.add_parser(mode)
        command.add_argument('--source', type=Path, required=True)
        command.add_argument('--baseline', type=Path, required=True)
        command.add_argument('--candidate', type=Path, required=True)
        command.add_argument('--rubric', type=Path, required=True)
        command.add_argument('--contract', type=Path, required=True)
        if mode in ('verify', 'reset'):
            command.add_argument('--upstream-root', type=Path, required=True)
            command.add_argument('--receipt', type=Path, required=True)
        if mode == 'reset':
            command.add_argument('--reset-artifact', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'freeze':
        result = freeze(args.source, args.baseline, args.candidate, args.rubric, args.contract)
    else:
        if args.mode == 'verify':
            result = verify(args.source, args.baseline, args.candidate, args.rubric,
                            args.contract, args.upstream_root)
        else:
            result = verify_reset(args.source, args.baseline, args.candidate, args.reset_artifact,
                                  args.rubric, args.contract, args.upstream_root)
        if args.receipt.exists():
            raise ValueError('refuse to overwrite an evaluation receipt')
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
