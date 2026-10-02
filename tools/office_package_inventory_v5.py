"""Materialize WDI packages and DEVELOPMENT-ONLY legacy SEC descriptors offline.

Existing WDI decks and SEC workbook pairs remain original source packages.
This tool grants no cloud lifecycle qualification or hidden/final admission.
The two-issuer SEC pool is excluded from the active rich140 Excel protocol.
Use sec_excel_factory.rich_private_replay_v1 for current Excel packages.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from tools import office_owned_folder_runtime_v2 as runtime
from tools.office_current_package_v4 import Package

COUNTS = {'train':20,'selection':20,'final_candidate':100}


def _copy(source, target):
    raw = runtime.private(source)
    runtime.write_new(target,raw)


def prepare(*, ppt_root, excel_cases, excel_workbooks, output_root):
    ppt_root, excel_workbooks, out = Path(ppt_root).resolve(), Path(excel_workbooks).resolve(), Path(output_root).resolve()
    runtime.require(not out.exists() and not out.is_symlink(),'Fresh Office package inventory required')
    ppt_plan = json.loads(runtime.private(ppt_root/'candidate-plan.private.json'))
    cases = json.loads(runtime.private(excel_cases))
    runtime.require(ppt_plan.get('schema')=='ppt-wdi-original-candidates-v1' and
        {key:len(ppt_plan['sets'][key]) for key in COUNTS}==COUNTS,'Exact original PPT20/20/100 required')
    mapping={'train_candidate':'train','selection_candidate':'selection','final_candidate':'final_candidate'}
    runtime.require(Counter(mapping[row['split']] for row in cases)==Counter(COUNTS) and
        len({row['case_id'] for row in cases})==140,'Exact unique SEC20/20/100 required')
    out.mkdir(mode=0o700,parents=True); metadata=[]
    for split in COUNTS:
        for task in ppt_plan['sets'][split]:
            source=ppt_root/'packages'/split/task['task_id']; package=out/'powerpoint-web'/split/task['task_id'];package.mkdir(mode=0o700,parents=True)
            for name in ('source.pptx','task.private.json','source-snapshot.private.json','source-provenance.private.json','source-country.private.zip'):
                if (source/name).is_file():_copy(source/name,package/name)
            runtime.descriptor(cell_id='powerpoint-web',split=split,task_id=task['task_id'],instruction=task['actor_task'],
                baseline=package/'source.pptx',task_spec=package/'task.private.json',out=package/'package.private.json')
            checked=Package(package/'package.private.json',package_root=package); score=checked.strict_score(checked.paths['baseline'])
            runtime.require(score['score']==0,'PPT actor baseline must remain unsolved')
            metadata.append({'cell_id':'powerpoint-web','split':split,'task_id':task['task_id'],'package_sha256':checked.binding_sha256,
                'package_root':str(package),'descriptor_ref':{'path':str(package/'package.private.json'),'sha256':checked.binding_sha256},'baseline_score':0})
    for case in cases:
        split=mapping[case['split']]; source=excel_workbooks/case['split']/case['case_id'];task_id='sec-'+case['case_id']
        package=out/'excel-web'/split/task_id;package.mkdir(mode=0o700,parents=True)
        for source_name,target_name in (('actor.xlsx','source.xlsx'),('reference.xlsx','reference.private.xlsx'),('task.md','task.md')):_copy(source/source_name,package/target_name)
        runtime.write_new(package/'case-manifest.private.json',runtime.canonical([case]))
        instruction=(package/'task.md').read_text()
        runtime.write_new(package/'task.private.json',runtime.canonical({'task_id':task_id,'split':split,'actor_task':instruction}))
        runtime.descriptor(cell_id='excel-web',split=split,task_id=task_id,instruction=instruction,baseline=package/'source.xlsx',
            task_spec=package/'task.private.json',out=package/'package.private.json',extra_refs={'case_manifest':package/'case-manifest.private.json'},case_id=case['case_id'])
        checked=Package(package/'package.private.json',package_root=package); baseline=checked.strict_score(checked.paths['baseline']);positive=checked.strict_score(package/'reference.private.xlsx')
        runtime.require(baseline['score']==0 and positive['score']==1,'Original SEC unsolved/positive offline controls required')
        metadata.append({'cell_id':'excel-web','split':split,'task_id':task_id,'package_sha256':checked.binding_sha256,
            'package_root':str(package),'descriptor_ref':{'path':str(package/'package.private.json'),'sha256':checked.binding_sha256},'baseline_score':0,'positive_offline_score':1})
    inventory={'schema':'office-package-inventory-private-v5','metadata':metadata,'counts':{cell:dict(Counter(row['split'] for row in metadata if row['cell_id']==cell)) for cell in runtime.CELLS},
        'excel_scope':'legacy-development-only; excluded from current rich140 protocol',
        'original_software_target':True,'native_lifecycle_qualified':False,'gui_admitted_final_count':0,'model_calls':0,'native_calls':0}
    runtime.write_new(out/'metadata-index.private.json',runtime.canonical(inventory))
    execution_rows=[{key:row[key] for key in ('cell_id','split','task_id','package_sha256','package_root')} |
        {'descriptor':row['descriptor_ref']['path']} for row in metadata]
    runtime.write_new(out/'execution-metadata-index.private.json',runtime.canonical(execution_rows))
    return {'schema':inventory['schema'],'counts':inventory['counts'],'packages':len(metadata),'excel_scope':inventory['excel_scope'],'native_lifecycle_qualified':False,'gui_admitted_final_count':0,'model_calls':0,'native_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('ppt-root','excel-cases','excel-workbooks','output-root'):parser.add_argument('--'+field,required=True)
    print(json.dumps(prepare(**vars(parser.parse_args())),sort_keys=True))


if __name__=='__main__':main()
