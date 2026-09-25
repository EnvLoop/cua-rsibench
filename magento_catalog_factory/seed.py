"""Install exactly one private quote page in an isolated Magento task clone.

This is trusted environment setup, not a student action or a GUI qualification.
The source plan and quote stay in ignored evaluator storage. The pinned shared
smoke container is deliberately rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from .plan import ROOT, SCHEMA, digest, require


IMAGE = 'sha256:d0531dd27ed98d0c459ff9e88118bf2ed8b660b0ed99c38837db46c065a5be13'
CONTEXT = 'colima-cua-scale'
CONTAINER_NAME = re.compile(r'envloop-magento-original-[a-z0-9-]{1,40}\Z')
PHP_SEED = r'''<?php
$case=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
$cfg=include '/var/www/magento2/app/etc/env.php';
$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$db->beginTransaction();
try {
  $existing=$db->query("SELECT COUNT(*) FROM cms_page WHERE identifier LIKE 'envloop-quote-%'")->fetchColumn();
  if ((int)$existing !== 0) throw new Exception('clone already contains an EnvLoop quote page');
  $parentQuery=$db->prepare('SELECT sku,type_id FROM catalog_product_entity WHERE entity_id=?');
  $parentQuery->execute([$case['parent_id']]);
  $parentRow=$parentQuery->fetch(PDO::FETCH_ASSOC);
  if ($parentRow===false || $parentRow['sku']!==$case['parent_sku'] ||
      $parentRow['type_id']!=='configurable') {
    throw new Exception('source configurable parent identity drifted');
  }
  $query=$db->prepare('SELECT e.sku,sl.parent_id,d.value FROM catalog_product_entity e '
      .'JOIN catalog_product_super_link sl ON sl.product_id=e.entity_id '
      .'JOIN catalog_product_entity_decimal d ON d.entity_id=e.entity_id '
      .'AND d.attribute_id=77 AND d.store_id=0 WHERE e.entity_id=?');
  foreach ($case['variants'] as $variant) {
    $query->execute([$variant['entity_id']]);
    $row=$query->fetch(PDO::FETCH_ASSOC);
    if ($row === false || $row['sku'] !== $variant['sku'] ||
        (int)$row['parent_id'] !== $case['parent_id'] ||
        (int)round((float)$row['value']*100) !== (int)round((float)$variant['initial_price']*100)) {
      throw new Exception('source variant identity or starting price drifted');
    }
  }
  $insert=$db->prepare('INSERT INTO cms_page '
      .'(title,identifier,content_heading,content,is_active,creation_time,update_time) '
      .'VALUES (?,?,?,?,1,?,?)');
  $insert->execute([$case['title'],$case['identifier'],$case['title'],$case['content'],
      '2026-09-25 00:00:00','2026-09-25 00:00:00']);
  $page=(int)$db->lastInsertId();
  $store=$db->prepare('INSERT INTO cms_page_store (page_id,store_id) VALUES (?,0)');
  $store->execute([$page]);
  $read=$db->prepare('SELECT p.title,p.identifier,p.content,s.store_id FROM cms_page p '
      .'JOIN cms_page_store s ON s.page_id=p.page_id WHERE p.page_id=?');
  $read->execute([$page]);
  $saved=$read->fetch(PDO::FETCH_ASSOC);
  if ($saved === false || $saved['title'] !== $case['title'] ||
      $saved['identifier'] !== $case['identifier'] ||
      $saved['content'] !== $case['content'] || (int)$saved['store_id'] !== 0) {
    throw new Exception('quote page readback differed');
  }
  $db->commit();
  echo json_encode(['page_id'=>$page,'variant_count'=>count($case['variants']),
      'quote_page_body_sha256'=>hash('sha256',$saved['content'])],JSON_THROW_ON_ERROR);
} catch(Throwable $error) { $db->rollBack(); throw $error; }
'''


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_case(plan_path: Path, expected_sha256: str, task_id: str) -> dict:
    path = plan_path.resolve()
    require(path.is_relative_to((ROOT / 'work').resolve()) and path.is_file() and
            re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is not None,
            'private plan path and pinned SHA-256 required')
    raw = path.read_bytes()
    require(_sha(raw) == expected_sha256, 'private plan bytes changed')
    plan = json.loads(raw)
    require(plan.get('schema') == SCHEMA and
            plan.get('status') == 'offline_candidates_not_gui_admitted' and
            plan.get('official_final_admitted_count') == 0,
            'candidate plan identity/status changed')
    matches = [case for cases in plan['cases'].values() for case in cases
               if case.get('task_id') == task_id]
    require(len(matches) == 1, 'task ID is missing or ambiguous')
    case = matches[0]
    require(case['package_sha256'] == digest({key: value for key, value in case.items()
                                               if key != 'package_sha256'}) and
            case['quote_page_body_sha256'] == _sha(case['quote_page_body'].encode()) and
            len(case['target_variants']) in (1, 2, 5),
            'task package or quote changed')
    return case


def check_clone(container: str, http_port: int, control_port: int) -> dict:
    require(CONTAINER_NAME.fullmatch(container) is not None and
            1024 <= http_port <= 65535 and 1024 <= control_port <= 65535 and
            http_port != control_port, 'dedicated clone identity/ports required')
    result = subprocess.run(['docker', '--context', CONTEXT, 'inspect', container],
                            capture_output=True, text=True, check=True, timeout=30)
    info = json.loads(result.stdout)[0]
    require(info['Image'] == IMAGE and info['State']['Running'] and not info['Mounts'],
            'dedicated no-mount clone must run the pinned image')
    ports = info['NetworkSettings']['Ports']
    require(ports.get('80/tcp') == [{'HostIp': '127.0.0.1', 'HostPort': str(http_port)}]
            and ports.get('8877/tcp') == [{'HostIp': '127.0.0.1',
                                          'HostPort': str(control_port)}],
            'clone must be bound to the declared loopback ports')
    return {'container_id_sha256': _sha(info['Id'].encode()),
            'image_sha256': info['Image'], 'mount_count': 0,
            'loopback_ports': [http_port, control_port]}


def seed(case: dict, container: str, http_port: int,
         control_port: int) -> dict:
    clone = check_clone(container, http_port, control_port)
    opaque = case['task_id'].removeprefix('magento-catalog-')
    require(re.fullmatch(r'[0-9a-f]{16}', opaque) is not None,
            'task identifier cannot form a quote page')
    payload = {
        'title': case['quote_page_title'],
        'identifier': 'envloop-quote-' + opaque,
        'content': case['quote_page_body'],
        'parent_id': case['parent_id'],
        'parent_sku': case['parent_sku'],
        'variants': ([{key: row[key] for key in ('entity_id', 'sku', 'initial_price')}
                      for row in case['target_variants']] +
                     [{'entity_id': row['entity_id'], 'sku': row['sku'],
                       'initial_price': row['price']}
                      for row in case['untouched_comparators']]),
    }
    result = subprocess.run(['docker', '--context', CONTEXT, 'exec', '-i',
                             container, 'php', '-r', PHP_SEED.removeprefix('<?php\n')],
                            input=json.dumps(payload, sort_keys=True),
                            capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, 'trusted Magento PHP setup failed')
    saved = json.loads(result.stdout)
    require(saved['variant_count'] == len(payload['variants']) and
            saved['quote_page_body_sha256'] == case['quote_page_body_sha256'] and
            type(saved['page_id']) is int and saved['page_id'] > 0,
            'trusted quote-page readback differed')
    return {'task_id': case['task_id'], 'page_id': saved['page_id'],
            'package_sha256': case['package_sha256'],
            'quote_page_body_sha256': saved['quote_page_body_sha256'],
            'clone': clone,
            'status': 'trusted_fixture_seeded_not_gui_admitted'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--http-port', type=int, required=True)
    parser.add_argument('--control-port', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'work').resolve()) and not out.exists(),
            'new ignored evaluator seed receipt under work/ required')
    case = load_case(args.plan, args.plan_sha256, args.task_id)
    receipt = seed(case, args.container, args.http_port, args.control_port)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': receipt['status'],
                      'receipt_sha256': _sha(raw),
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
