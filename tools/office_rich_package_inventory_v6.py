"""Combine actual original WDI140 and CURRENT rich SEC140 evaluator metadata.

Legacy two-issuer SEC entries are excluded. Only verified package descriptors
enter the fresh private index; this operation creates no qualification.
"""
from collections import Counter
import argparse
import json
from pathlib import Path
from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_package_v5 import Package


def combine(*, ppt_metadata_index, rich_metadata_index, output_index):
    ppt=json.loads(office.private(ppt_metadata_index));rich=json.loads(office.private(rich_metadata_index))
    office.require(type(ppt) is list and type(rich) is list,'Execution metadata lists required')
    ppt=[row for row in ppt if row['cell_id']=='powerpoint-web']
    office.require(all(row['cell_id']=='excel-web' and
        row.get('package_adapter')=='tools.office_current_package_v5.Package' for row in rich),
        'Current rich SEC adapter required; legacy SEC is excluded')
    rows=ppt+rich
    expected=Counter({'train':20,'selection':20,'final_candidate':100})
    for cell in ('powerpoint-web','excel-web'):
        selected=[row for row in rows if row['cell_id']==cell]
        office.require(Counter(row['split'] for row in selected)==expected and
            len({row['task_id'] for row in selected})==140,'Exact unique original Office140 per cell required')
    output=[]
    for row in rows:
        package=Package(row['descriptor'],package_root=row['package_root'])
        office.require(package.binding_sha256==row['package_sha256'] and
            (package.actor.cell_id,package.actor.split,package.actor.task_id)==
            (row['cell_id'],row['split'],row['task_id']),'Actual frozen Office metadata binding changed')
        office.require(row['cell_id']!='excel-web' or package.rich is True,'Current rich SEC source required')
        output.append({key:row[key] for key in ('cell_id','split','task_id','package_sha256','package_root','descriptor')} |
            {'package_adapter':'tools.office_current_package_v5.Package'})
    office.write_new(Path(output_index),office.canonical(output))
    return {'schema':'office-current-rich-package-inventory-v6','packages':280,
        'counts':{cell:dict(expected) for cell in ('powerpoint-web','excel-web')},
        'legacy_excel_entries_included':0,'native_lifecycle_qualified':False,
        'gui_admitted_final_count':0,'model_calls':0,'native_calls':0,'official_final_credit':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('ppt-metadata-index','rich-metadata-index','output-index'):parser.add_argument('--'+key,required=True)
    print(json.dumps(combine(**vars(parser.parse_args())),sort_keys=True))


if __name__=='__main__':main()
