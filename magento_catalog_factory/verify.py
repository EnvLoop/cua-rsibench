"""Independent saved-state readback for original Magento catalog tasks.

The actor never receives this module, source facts, or target prices. A saved
price is necessary but insufficient: source page, non-target catalog records,
other business tables, and unrelated search documents must be preserved.
"""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import subprocess

from .plan import require
from .seed import CONTEXT, check_clone


PHP_READ = r'''<?php
$request=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
$ids=array_map('intval',$request['variant_ids']);
$target=array_map('intval',$request['target_ids']);
$parent=(int)$request['parent_id'];$page=(int)$request['page_id'];
$cfg=include '/var/www/magento2/app/etc/env.php';
$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$db->exec('START TRANSACTION READ ONLY');
$catalog=['catalog_product_entity','catalog_product_entity_decimal',
  'catalog_product_entity_int','catalog_product_entity_varchar',
  'catalog_product_entity_text','catalog_product_entity_datetime',
  'catalog_product_index_price','catalog_product_index_price_replica',
  'cataloginventory_stock_item'];
$business=['sales_order','sales_order_item','customer_entity',
  'customer_address_entity','quote','cms_page','cms_page_store'];
$hashes=['full'=>[],'other_catalog'=>[],'target_nonprice'=>[],'business'=>[]];
foreach(array_merge($catalog,$business) as $table){
  $all=[];$other=[];$nonprice=[];
  foreach($db->query('SELECT * FROM `'.$table.'`') as $row){
    $canonical=[];foreach($row as $key=>$value){if(is_string($key))$canonical[$key]=$value;}
    ksort($canonical);$rowHash=hash('sha256',json_encode($canonical,JSON_UNESCAPED_SLASHES));
    $all[]=$rowHash;
    if(in_array($table,$catalog,true)){
      $key=$table==='cataloginventory_stock_item'?'product_id':'entity_id';
      $entity=(int)$canonical[$key];
      $isTarget=in_array($entity,$target,true);
      $isDerivedParent=($entity===$parent && str_starts_with($table,'catalog_product_index_price'));
      if(!$isTarget && !$isDerivedParent)$other[]=$rowHash;
      if($isTarget && !str_starts_with($table,'catalog_product_index_price')){
        if($table==='catalog_product_entity_decimal' &&
           (int)$canonical['attribute_id']===77 && (int)$canonical['store_id']===0)continue;
        if($table==='catalog_product_entity')unset($canonical['updated_at']);
        $nonprice[]=hash('sha256',json_encode($canonical,JSON_UNESCAPED_SLASHES));
      }
    }
  }
  sort($all);$hashes['full'][$table]=hash('sha256',implode("\n",$all));
  if(in_array($table,$catalog,true)){
    sort($other);sort($nonprice);
    $hashes['other_catalog'][$table]=hash('sha256',implode("\n",$other));
    $hashes['target_nonprice'][$table]=hash('sha256',implode("\n",$nonprice));
  }else{$hashes['business'][$table]=$hashes['full'][$table];}
}
$list=implode(',',$ids);
$sql='SELECT e.entity_id,e.sku,sl.parent_id,d.value FROM catalog_product_entity e '
    .'JOIN catalog_product_super_link sl ON sl.product_id=e.entity_id '
    .'JOIN catalog_product_entity_decimal d ON d.entity_id=e.entity_id '
    .'AND d.attribute_id=77 AND d.store_id=0 WHERE e.entity_id IN ('.$list.') ORDER BY e.entity_id';
$prices=[];foreach($db->query($sql) as $row){
  $prices[(string)$row['entity_id']]=['sku'=>$row['sku'],
      'parent_id'=>(int)$row['parent_id'],'price'=>$row['value']];
}
$query=$db->prepare('SELECT p.title,p.identifier,p.content,p.is_active,s.store_id '
    .'FROM cms_page p JOIN cms_page_store s ON s.page_id=p.page_id WHERE p.page_id=?');
$query->execute([$page]);$quote=$query->fetch(PDO::FETCH_ASSOC);
if($quote===false)throw new Exception('trusted quote page disappeared');
$quote['content_sha256']=hash('sha256',$quote['content']);unset($quote['content']);
$db->rollBack();
echo json_encode(['hashes'=>$hashes,'prices'=>$prices,'quote'=>$quote],JSON_THROW_ON_ERROR);
'''


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def _docker(container: str, *args: str, input_text: str | None = None,
            timeout: int = 180) -> str:
    result = subprocess.run(['docker', '--context', CONTEXT, 'exec',
                             *(['-i'] if input_text is not None else []),
                             container, *args], input=input_text,
                            capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, 'read-only Magento snapshot failed')
    return result.stdout


def read_snapshot(case: dict, container: str, http_port: int,
                  control_port: int, page_id: int) -> dict:
    check_clone(container, http_port, control_port)
    target_ids = [int(row['entity_id']) for row in case['target_variants']]
    comparator_ids = [int(row['entity_id']) for row in case['untouched_comparators']]
    require(target_ids and len(set(target_ids + comparator_ids)) ==
            len(target_ids) + len(comparator_ids) and page_id > 0,
            'task variant/page binding is invalid')
    request = {'target_ids': target_ids, 'variant_ids': target_ids + comparator_ids,
               'parent_id': case['parent_id'], 'page_id': page_id}
    db = json.loads(_docker(container, 'php', '-r',
                            PHP_READ.removeprefix('<?php\n'),
                            input_text=json.dumps(request, sort_keys=True)))
    search = json.loads(_docker(container, 'curl', '-fsS', '--max-time', '30',
                                'http://127.0.0.1:9200/magento2_product_1/_search?size=1000',
                                timeout=45))
    hits = search['hits']['hits']
    require(search['hits']['total']['value'] == len(hits) and len(hits) > 100,
            'Magento search snapshot was truncated or unavailable')
    documents = {row['_id']: row['_source'] for row in hits}
    parent_id = str(case['parent_id'])
    require(parent_id in documents and len(documents) == len(hits),
            'parent product is absent from search index')
    return {'schema': 'envloop-magento-catalog-saved-state-v1',
            'task_id': case['task_id'], 'page_id': page_id,
            'database': db,
            'search': {'document_count': len(documents),
                       'full_sha256': canonical_sha(documents),
                       'other_documents_sha256': canonical_sha({key: value for key, value
                                                                in documents.items()
                                                                if key != parent_id}),
                       'parent_document_sha256': canonical_sha(documents[parent_id])}}


def _cents(value: str) -> int:
    number = Decimal(str(value))
    require(number.is_finite() and number >= 0 and number.as_tuple().exponent >= -6,
            'price is not a bounded finite decimal')
    cents = number * 100
    require(cents == cents.to_integral_value(), 'price has fractional cents')
    return int(cents)


def check_baseline(case: dict, state: dict) -> None:
    require(state['task_id'] == case['task_id'] and
            state['database']['quote']['content_sha256'] ==
            case['quote_page_body_sha256'] and
            int(state['database']['quote']['is_active']) == 1 and
            int(state['database']['quote']['store_id']) == 0,
            'task/source baseline changed')
    variants = case['target_variants'] + [
        {'entity_id': row['entity_id'], 'sku': row['sku'],
         'initial_price': row['price']} for row in case['untouched_comparators']]
    got = state['database']['prices']
    require(len(got) == len(variants), 'baseline variant count changed')
    for row in variants:
        saved = got[str(row['entity_id'])]
        require(saved['sku'] == row['sku'] and
                saved['parent_id'] == case['parent_id'] and
                _cents(saved['price']) == _cents(row['initial_price']),
                'baseline variant identity/price changed')


def score_saved_state(case: dict, before: dict, after: dict) -> dict:
    check_baseline(case, before)
    require(after['schema'] == before['schema'] and
            after['task_id'] == before['task_id'] and
            after['page_id'] == before['page_id'],
            'attempt state binding changed')
    failures = []
    prior = before['database']
    current = after['database']
    if current['quote'] != prior['quote']:
        failures.append('source_quote_changed')
    for row in case['target_variants']:
        entity = str(row['entity_id'])
        saved = current['prices'].get(entity)
        if (saved is None or saved['sku'] != row['sku'] or
                saved['parent_id'] != case['parent_id'] or
                _cents(saved['price']) != _cents(row['target_price'])):
            failures.append('target_price_or_identity_mismatch')
            break
    for row in case['untouched_comparators']:
        entity = str(row['entity_id'])
        if current['prices'].get(entity) != prior['prices'][entity]:
            failures.append('untouched_variant_changed')
            break
    for field in ('other_catalog', 'target_nonprice', 'business'):
        if current['hashes'][field] != prior['hashes'][field]:
            failures.append(field + '_changed')
    if (after['search']['document_count'] != before['search']['document_count'] or
            after['search']['other_documents_sha256'] !=
            before['search']['other_documents_sha256']):
        failures.append('unrelated_search_documents_changed')
    return {'schema': 'envloop-magento-catalog-score-v1',
            'task_id': case['task_id'], 'passed': not failures,
            'score': 1.0 if not failures else 0.0,
            'failure_codes': failures,
            'checked_target_count': len(case['target_variants']),
            'independent_saved_state': True}


def check_exact_reset(before: dict, restored: dict) -> None:
    require(restored == before, 'full monitored SQL/search state failed exact reset')
