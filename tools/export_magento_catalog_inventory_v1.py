"""Export a private read-only Magento sample-catalog candidate inventory.

This does not create tasks or touch the shared smoke container's state. It
retains source entity/SKU/price data only in an ignored evaluator directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = 'colima-cua-scale'
CONTAINER = 'cua-v06-magento-smoke'
IMAGE = 'sha256:d0531dd27ed98d0c459ff9e88118bf2ed8b660b0ed99c38837db46c065a5be13'
QUARANTINED_TRAIN_CHILD_IDS = {111, 114, 117, 120, 123}
PHP_READ = r'''<?php
$cfg=include '/var/www/magento2/app/etc/env.php';
$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$db->exec('START TRANSACTION READ ONLY');
$sql='SELECT p.entity_id parent_id,p.sku parent_sku,l.product_id child_id,c.sku child_sku,d.value child_price '
    .'FROM catalog_product_super_link l '
    .'JOIN catalog_product_entity p ON p.entity_id=l.parent_id AND p.type_id="configurable" '
    .'JOIN catalog_product_entity c ON c.entity_id=l.product_id AND c.type_id="simple" '
    .'LEFT JOIN catalog_product_entity_decimal d ON d.entity_id=c.entity_id AND d.attribute_id=77 AND d.store_id=0 '
    .'ORDER BY p.entity_id,l.product_id';
$rows=$db->query($sql)->fetchAll(PDO::FETCH_ASSOC);
$db->rollBack();echo json_encode($rows,JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
'''


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def export(out: Path) -> dict:
    out = Path(out).resolve()
    private_root = (ROOT / 'work').resolve()
    require(out.is_relative_to(private_root) and not out.exists(),
            'private new output under ignored work/ required')
    inspection = subprocess.run(
        ['docker', '--context', CONTEXT, 'inspect', CONTAINER],
        capture_output=True, text=True, check=True, timeout=30)
    container = json.loads(inspection.stdout)[0]
    require(container['Image'] == IMAGE and container['State']['Running'] and
            not container['Mounts'], 'shared catalog image/state changed')
    result = subprocess.run(
        ['docker', '--context', CONTEXT, 'exec', '-i', CONTAINER, 'php'],
        input=PHP_READ, capture_output=True, text=True, check=True, timeout=90)
    rows = json.loads(result.stdout)
    require(isinstance(rows, list) and len(rows) >= 1000,
            'configurable catalog appears incomplete')
    by_parent: dict[int, dict] = {}
    all_children: set[int] = set()
    for row in rows:
        parent_id, child_id = int(row['parent_id']), int(row['child_id'])
        require(parent_id != child_id and child_id not in all_children and
                isinstance(row['parent_sku'], str) and row['parent_sku'] and
                isinstance(row['child_sku'], str) and row['child_sku'] and
                row['child_price'] is not None,
                'missing, duplicate, or unpriced variant')
        all_children.add(child_id)
        parent = by_parent.setdefault(parent_id, {
            'parent_id': parent_id, 'parent_sku': row['parent_sku'],
            'children': []})
        require(parent['parent_sku'] == row['parent_sku'],
                'parent SKU changed across variant rows')
        parent['children'].append({'entity_id': child_id,
                                   'sku': row['child_sku'],
                                   'price': str(row['child_price'])})
    parents = [by_parent[key] for key in sorted(by_parent)]
    quarantine = [row['parent_id'] for row in parents
                  if any(child['entity_id'] in QUARANTINED_TRAIN_CHILD_IDS
                         for child in row['children'])]
    eligible = [row for row in parents
                if len(row['children']) >= 5 and row['parent_id'] not in quarantine]
    final_capacity = sum(len(row['children']) >= 10 for row in eligible)
    require(len(parents) >= 140 and len(eligible) >= 140 and
            final_capacity >= 100 and quarantine,
            'catalog cannot support disjoint 20/20/100 parent cohorts')
    document = {
        'schema': 'envloop-magento-catalog-private-inventory-v1',
        'application': 'Magento Open Source 2.4.6 sample catalog',
        'source_type': 'sample_data_not_authentic_customer_history',
        'docker_image_sha256': IMAGE,
        'container_id_sha256': sha(container['Id'].encode()),
        'rows_sha256': sha(json.dumps(rows, sort_keys=True,
                                      separators=(',', ':')).encode()),
        'quarantined_public_train_child_ids': sorted(QUARANTINED_TRAIN_CHILD_IDS),
        'quarantined_parent_ids': quarantine,
        'eligible_parent_count': len(eligible),
        'eligible_final_10_variant_parent_count': final_capacity,
        'parents': parents,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(document, sort_keys=True, indent=2) + '\n').encode()
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'inventory_sha256': sha(raw), 'parent_count': len(parents),
            'eligible_parent_count': len(eligible),
            'final_10_variant_capacity': final_capacity,
            'quarantined_parent_count': len(quarantine),
            'official_final_tasks_admitted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.out), sort_keys=True))


if __name__ == '__main__':
    main()
