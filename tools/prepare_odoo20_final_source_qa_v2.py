"""Saved-only frozen20 source QA; approval remains pending until reviewed.

Requires a terminal successful worker and all20 genuine saved controls. Copies
exact assets and native screenshots, renders every PDF page with Poppler, and
creates pairs without resizing source or native pixels. No API/GUI/Docker use.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont
from enterprise_fallback.odoo18 import twenty_task_trial_controls_v2 as controls
from enterprise_fallback.odoo18.partition_factory import source_asset

ROOT = Path(__file__).resolve().parents[1]
require = controls.require


def digest(raw): return sha256(raw).hexdigest()


def _write(path, raw):
    path = Path(path)
    require(path.parent.is_dir() and path.parent.stat().st_mode & 0o077 == 0 and not path.parent.is_symlink(),
            'qa_private_parent_required')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return {'path': str(path.resolve()), 'sha256': digest(raw)}


def _json(path, value): return _write(path, controls.workers.canonical(value))


def _png(path, image):
    raw = io.BytesIO(); image.save(raw, format='PNG')
    return _write(path, raw.getvalue())


def _pid_alive(pid):
    try: os.kill(pid, 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    return True


def _terminal(path, expected):
    terminal = controls.workers.private_json(path, expected)
    require(type(terminal.get('pid')) is int and terminal['pid'] > 0 and terminal.get('exit_code') == 0 and
            terminal.get('automatic_restarts') == 0 and
            type(terminal.get('started_at')) in (int, float) and type(terminal.get('ended_at')) in (int, float) and
            terminal['ended_at'] >= terminal['started_at'] and not _pid_alive(terminal['pid']),
            'qa_successful_terminal_worker_required_no_live_snapshot')
    return terminal


def _font(size):
    for candidate in ('/System/Library/Fonts/Menlo.ttc', '/System/Library/Fonts/Supplemental/Arial.ttf',
                      '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'):
        if Path(candidate).is_file(): return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def _text_image(raw):
    text = raw.decode('utf-8')
    font = _font(18)
    lines = []
    for line in text.splitlines():
        lines.extend(textwrap.wrap(line.expandtabs(4), width=90, break_long_words=True, replace_whitespace=False,
                                   drop_whitespace=False) or [''])
    require(bool(lines) and len(lines) <= 2048, 'qa_bounded_source_note_required')
    line_height = 27
    image = Image.new('RGB', (1080, max(240, 48+len(lines)*line_height)), 'white')
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines): draw.text((24, 24+index*line_height), line, font=font, fill='#18212b')
    return image


def _pdf_pages(path, output):
    poppler, info = shutil.which('pdftoppm'), shutil.which('pdfinfo')
    require(poppler is not None and info is not None, 'qa_poppler_required_no_render_fallback')
    try:
        result = subprocess.run([info, str(path)], capture_output=True, check=True, timeout=30)
        pages = next(int(line.split(':', 1)[1].strip()) for line in result.stdout.decode().splitlines() if line.startswith('Pages:'))
        require(0 < pages <= 32, 'qa_pdf_page_count_unbounded')
        prefix = output/'source-page'
        subprocess.run([poppler, '-png', '-r', '120', str(path), str(prefix)],
                       capture_output=True, check=True, timeout=120)
    except (subprocess.SubprocessError, UnicodeDecodeError, ValueError, StopIteration):
        raise ValueError('qa_poppler_render_failed_preserve_namespace') from None
    files = sorted(output.glob('source-page-*.png'), key=lambda item: int(item.stem.rsplit('-', 1)[1]))
    require(len(files) == pages and all(item.is_file() and not item.is_symlink() for item in files), 'qa_pdf_render_pages_missing')
    for item in files: item.chmod(0o600)
    images = []
    for item in files:
        with Image.open(item) as opened: images.append(opened.convert('RGB'))
    return images, [{'path': str(item.resolve()), 'sha256': digest(item.read_bytes())} for item in files]


def _source_panel(pages):
    gap = 16
    width = max(page.width for page in pages)
    height = sum(page.height for page in pages)+gap*(len(pages)-1)
    require(width*height <= 100_000_000, 'qa_source_panel_pixel_limit')
    image = Image.new('RGB', (width, height), '#e7ecf0')
    top = 0
    for page in pages:
        image.paste(page, (0, top)); top += page.height+gap
    return image


def _pair(source, native, metadata, ordinal):
    padding, header = 24, 88
    left, right = padding, source.width+2*padding
    pair = Image.new('RGB', (source.width+native.width+3*padding, max(source.height, native.height)+header+padding), '#edf1f5')
    draw = ImageDraw.Draw(pair)
    draw.text((padding, 12), f'{ordinal+1:02d}/20 | {metadata["family"]} | {metadata["task_id"]}', font=_font(18), fill='#172431')
    draw.text((left, 50), 'Frozen source render - original scale', font=_font(16), fill='#344253')
    draw.text((right, 50), 'Native screenshot - original pixels', font=_font(16), fill='#344253')
    pair.paste(source, (left, header)); pair.paste(native, (right, header))
    require(pair.crop((right, header, right+native.width, header+native.height)).tobytes() == native.tobytes(),
            'qa_native_panel_pixels_changed')
    return pair, [right, header]


def prepare(*, plan_path, plan_sha, worker_dir, run_dir, terminal_receipt_path, terminal_receipt_sha, output_root):
    terminal = _terminal(terminal_receipt_path, terminal_receipt_sha)
    plan = controls._load(plan_path, plan_sha)
    worker, run = Path(worker_dir).resolve(), Path(run_dir).resolve()
    result_path = run/'controls-result.private.json'
    result = controls.workers.private_json(result_path)
    require(result.get('status') == controls.PENDING and result.get('saved_control_count') == 20,
            'qa_all_twenty_terminal_controls_required')
    # Trusted saved-only evaluator opens source/gold internally; contents are
    # never printed, sent to a model, or changed by this preparation tool.
    audited = controls.audit(plan_path=plan_path, plan_sha=plan_sha, worker_dir=worker, run_dir=run)
    require(audited['status'] == controls.PENDING and audited['control_count'] == 20,
            'qa_genuine_twenty_saved_control_replay_required')
    world = controls.workers.private_json(worker/'private/partition_cases.json')
    cases = {case['id']: case for group in world['cases'].values() for case in group}
    require(world.get('split') == 'official_hidden' and len(cases) == 100, 'qa_original_hundred_world_required')
    out = Path(output_root)
    require(out.is_absolute() and out.resolve().is_relative_to(ROOT/'work') and not out.exists() and not out.is_symlink(),
            'qa_fresh_owned_private_namespace_required')
    out.mkdir(parents=True, mode=0o700)
    read = controls.finalizer.SavedReader()
    rows, pending_rows = [], []
    for ordinal, (metadata, entry) in enumerate(zip(plan['frozen_twenty_metadata'], result['entries'], strict=True)):
        require(entry['metadata'] == metadata, 'qa_frozen_twenty_order_changed')
        receipt_path, receipt_raw = read.ref(entry['attempt'], run)
        receipt = json.loads(receipt_raw)
        require(receipt['worker_pid'] == terminal['pid'] and
            controls.finalizer._stamp(receipt['finished_at_utc']).timestamp() <= terminal['ended_at'],
            'qa_terminal_worker_not_the_saved_control_owner')
        attempt = receipt_path.parent
        native_path, native_raw = read.ref(receipt['refs']['source_frame'], attempt)
        asset = source_asset(cases[metadata['task_id']], world)
        require(digest(asset) == metadata['source_asset_sha256'] and native_raw.startswith(b'\x89PNG\r\n\x1a\n'),
                'qa_exact_source_asset_or_native_png_changed')
        folder = out/f'{ordinal+1:02d}-{metadata["family"]}-{metadata["task_id"]}'
        folder.mkdir(mode=0o700)
        is_pdf = asset.startswith(b'%PDF-')
        asset_ref = _write(folder/('expected-source.pdf' if is_pdf else 'expected-source.txt'), asset)
        native_ref = _write(folder/'native-source-frame-unchanged.png', native_raw)
        if is_pdf: pages, render_refs = _pdf_pages(Path(asset_ref['path']), folder)
        else:
            pages = [_text_image(asset)]
            render_refs = [_png(folder/'source-note-render.png', pages[0])]
        source = _source_panel(pages)
        with Image.open(io.BytesIO(native_raw)) as opened: native = opened.convert('RGB')
        pair, origin = _pair(source, native, metadata, ordinal)
        pair_ref = _png(folder/'source-vs-native.png', pair)
        pending = {'task_id': metadata['task_id'], 'package_sha256': metadata['package_sha256'],
            'source_frame_sha256': digest(native_raw), 'native_frame_copy': native_ref,
            'exact_source_asset_copy': asset_ref, 'side_by_side_qa': pair_ref, 'native_crop_origin': origin,
            'source_attachment_readable': None, 'source_matches_package': None, 'reviewed_at_utc': None}
        pending_rows.append(pending)
        rows.append({'ordinal': ordinal, 'metadata': metadata, 'original_native_frame': {'path': str(native_path), 'sha256': digest(native_raw)},
            **pending, 'source_page_renders': render_refs, 'native_dimensions': [native.width, native.height],
            'pair_dimensions': [pair.width, pair.height], 'native_panel_pixels_equal': True,
            'source_asset_bytes_equal': True, 'independent_scores': [0, 1, 0], 'visual_approval': None})
    require(len(rows) == 20, 'qa_complete_frozen_twenty_required')
    read.unchanged(); controls._load(plan_path, plan_sha)
    manifest = {'schema': 'envloop-odoo20-final-source-qa-manifest-v2', 'status': 'saved_only_source_qa_prepared_review_pending',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'control_plan_ref': {'path': str(Path(plan_path).resolve()), 'sha256': plan_sha},
        'controls_result_ref': {'path': str(result_path), 'sha256': digest(controls.private(result_path))},
        'worker_terminal_ref': {'path': str(Path(terminal_receipt_path).resolve()), 'sha256': terminal_receipt_sha},
        'trial_plan_sha256': plan['trial_plan_ref']['sha256'], 'original_world_count': 100, 'control_count': 20,
        'native_binding_sha256': plan['native_core_plan']['native_worker_binding_sha256'],
        'reference_binding_sha256': plan['reference_binding']['reference_binding_sha256'], 'rows': rows,
        'reviewer_approval': None, 'model_calls': 0, 'native_calls': 0, 'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0}
    manifest_ref = _json(out/'qa-manifest.private.json', manifest)
    pending_review = {'schema': 'envloop-odoo20-native-controls-source-review-v2', 'control_plan_sha256': plan_sha,
        'controls_result_sha256': manifest['controls_result_ref']['sha256'], 'reviewer_independent_of_actor': None,
        'qa_manifest_ref': manifest_ref, 'rows': pending_rows}
    pending_ref = _json(out/'pending-source-review.private.json', pending_review)
    return {'status': manifest['status'], 'control_count': 20, 'qa_manifest_ref': manifest_ref,
            'pending_review_ref': pending_ref, 'all_visual_approvals_pending': True,
            'model_calls': 0, 'native_calls': 0, 'formal_large_study_credit': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path', 'plan-sha', 'worker-dir', 'run-dir', 'terminal-receipt-path', 'terminal-receipt-sha', 'output-root'):
        parser.add_argument('--'+field, required=True)
    print(json.dumps(prepare(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__': main()
