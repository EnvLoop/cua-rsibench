"""Freeze deterministic target timestamps after a neutral native Magento save.

This is trusted fixture setup on a dedicated clone, not a student action or
task result. It may run only after an independently checked neutral GUI save.
The pinned timestamp makes fresh-clone baseline hashes comparable bytewise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import CONTEXT, check_clone, load_case
from magento_catalog_factory.verify import read_snapshot


FROZEN_TIMESTAMP = '2026-09-25 00:00:00'
PHP_FINALIZE = r'''$request=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
$cfg=include '/var/www/magento2/app/etc/env.php';
$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$db->beginTransaction();
try {
  $query=$db->prepare('UPDATE catalog_product_entity SET updated_at=? WHERE entity_id=? AND type_id=?');
  foreach($request['target_ids'] as $id){
    $query->execute([$request['timestamp'],(int)$id,'simple']);
    if($query->rowCount()!==1)throw new Exception('target timestamp row missing');
  }
  $db->commit();echo json_encode(['updated_target_count'=>count($request['target_ids'])],JSON_THROW_ON_ERROR);
}catch(Throwable $e){$db->rollBack();throw $e;}'''


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_private(path: Path) -> tuple[dict, str]:
    path = path.resolve()
    require(path.is_relative_to((ROOT / 'work').resolve()) and path.is_file(),
            'ignored evaluator evidence path required')
    raw = path.read_bytes()
    return json.loads(raw), sha(raw)


def write_private(path: Path, value: dict) -> str:
    path = path.resolve()
    require(path.is_relative_to((ROOT / 'work').resolve()) and not path.exists(),
            'fresh ignored evaluator output required')
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
    return sha(raw)


def validate_only_timestamp_changed(case: dict, before: dict, after: dict) -> None:
    require(before['schema'] == after['schema'] and
            before['task_id'] == after['task_id'] == case['task_id'] and
            before['page_id'] == after['page_id'] and
            before['search'] == after['search'] and
            before['database']['quote'] == after['database']['quote'] and
            before['database']['prices'] == after['database']['prices'] and
            before['database']['hashes']['other_catalog'] ==
            after['database']['hashes']['other_catalog'] and
            before['database']['hashes']['target_nonprice'] ==
            after['database']['hashes']['target_nonprice'] and
            before['database']['hashes']['business'] ==
            after['database']['hashes']['business'],
            'timestamp finalization altered task or business semantics')
    for table, rows in before['database']['target_rows'].items():
        changed = after['database']['target_rows'][table]
        require(len(rows) == len(changed), 'target row count changed')
        if table != 'catalog_product_entity':
            require(rows == changed, 'non-entity target row changed')
        else:
            for old, new in zip(rows, changed):
                expected = dict(old)
                expected['updated_at'] = FROZEN_TIMESTAMP
                require(new == expected,
                        'target entity changed beyond deterministic timestamp')
    full_before = before['database']['hashes']['full']
    full_after = after['database']['hashes']['full']
    require(all(full_before[key] == full_after[key] for key in full_before
                if key != 'catalog_product_entity'),
            'unrelated full-table hash changed during finalization')


def finalize(case: dict, neutral: dict, neutral_after: dict,
             container: str, http_port: int, control_port: int,
             page_id: int) -> tuple[dict, dict]:
    clone = check_clone(container, http_port, control_port)
    require(neutral['status'] == 'neutral_fixture_normalization_development_only'
            and neutral['mode'] == 'neutral' and
            neutral['task_id'] == case['task_id'] and
            neutral['package_sha256'] == case['package_sha256'] and
            neutral['neutral_preserved_other_business_state'] is True and
            neutral['fresh_clone_reset_passed'] is False,
            'neutral native GUI control was not independently accepted')
    before = read_snapshot(case, container, http_port, control_port, page_id)
    require(before == neutral_after,
            'clone state moved since the accepted neutral GUI save')
    ids = [row['entity_id'] for row in case['target_variants']]
    payload = {'target_ids': ids, 'timestamp': FROZEN_TIMESTAMP}
    result = subprocess.run(['docker', '--context', CONTEXT, 'exec', '-i',
                             container, 'php', '-r', PHP_FINALIZE],
                            input=json.dumps(payload), capture_output=True,
                            text=True, timeout=120)
    require(result.returncode == 0 and
            json.loads(result.stdout)['updated_target_count'] == len(ids),
            'trusted target timestamp finalization failed')
    after = read_snapshot(case, container, http_port, control_port, page_id)
    validate_only_timestamp_changed(case, before, after)
    receipt = {'schema': 'envloop-magento-neutral-baseline-finalization-v1',
               'status': 'normalized_baseline_frozen_not_gui_admitted',
               'task_id': case['task_id'],
               'package_sha256': case['package_sha256'],
               'clone': clone, 'page_id': page_id,
               'frozen_timestamp': FROZEN_TIMESTAMP,
               'target_count': len(ids),
               'before_state_sha256': sha((json.dumps(before, sort_keys=True, indent=2) + '\n').encode()),
               'official_final_tasks_admitted': 0}
    return receipt, after


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--neutral-result', type=Path, required=True)
    parser.add_argument('--neutral-after', type=Path, required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--http-port', type=int, required=True)
    parser.add_argument('--control-port', type=int, required=True)
    parser.add_argument('--page-id', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline-out', type=Path, required=True)
    args = parser.parse_args()
    case = load_case(args.plan, args.plan_sha256, args.task_id)
    neutral, neutral_sha = read_private(args.neutral_result)
    after, after_sha = read_private(args.neutral_after)
    receipt, baseline = finalize(case, neutral, after, args.container,
                                 args.http_port, args.control_port,
                                 args.page_id)
    receipt.update(neutral_result_sha256=neutral_sha,
                   neutral_after_sha256=after_sha)
    baseline_sha = write_private(args.baseline_out, baseline)
    receipt['normalized_baseline_sha256'] = baseline_sha
    receipt_sha = write_private(args.out, receipt)
    print(json.dumps({'status': receipt['status'],
                      'receipt_sha256': receipt_sha,
                      'normalized_baseline_sha256': baseline_sha,
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
