"""Selection-aware GUI constructor; historical three-target final code unchanged.

This is trusted evaluator code, never a model action policy. Its grammar and
layout preflight run before any new intent; private answer text is not logged.
"""
from __future__ import annotations

from collections import Counter
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from . import calibrate_sweep as historical
from . import factory_v2
from .verify import xlsx_cells,pptx_slide_shapes,docx_content
from .v066_control_plan import compile_script


SELECTION_PROFILES={
 'calc-growth':{'targets':2,'sheets':3,'sheet':'Two-factor review','cells':['B5','B6']},
 'calc-risk':{'targets':2,'sheets':3,'sheet':'Two-factor review','cells':['B5','B6']},
 'impress-deck':{'targets':2,'slides':5,'target_slide':4},
 'writer-brief':{'targets':2,'tables':1,'source_years':3},
}
SAVE=['screen edited','press ctrl,s','wait 2','click 789,519','wait 3','readback','stop']


def _namebox(value:str)->list[str]:
 return ['click 52,170','press ctrl,a','write '+value,'press enter','wait 1']


def calc_cell_reference(sheet:str,cell:str)->str:
 """Calc A1 reference: quote the sheet and double embedded apostrophes."""
 if not sheet or any(char in sheet for char in '\r\n') or not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]*',cell):
  raise ValueError('Calc Name Box requires a single-sheet A1 cell reference')
 return "'"+sheet.replace("'","''")+"'."+cell


def script_from_layout(*,workflow:str,targets:dict,attempt:str,cells=None,slides=None,paragraphs=None,target_slide=None)->str:
 if attempt=='cold-reset':return 'stop\n'
 if attempt not in ['positive','near-miss'] or len(targets) not in [1,2]:raise ValueError('Selection constructor requires one/two target positive/near-miss profile')
 lines=['wait 7','press esc','wait 1']
 if workflow.startswith('calc-'):
  ordered=list(targets.items());sheets={address.split('!',1)[0] for address,_ in ordered}
  if len(sheets)!=1:raise ValueError('Selection Calc targets must share one authored sheet')
  sheet=sheets.pop()
  expected=['B4'] if len(targets)==1 else ['B5','B6']
  if [address.split('!',1)[1] for address,_ in ordered]!=expected or sheet not in ['Review','Two-factor review']:
   raise ValueError('Selection Calc target layout changed')
  # One full Calc sheet.cell reference per target avoids a separate sheet
  # navigation step. Enter uses v9 neutral settling and a new frame before
  # the plain formula write begins in the focused grid cell.
  for index,(address,rule) in enumerate(ordered):
   cell=address.split('!',1)[1];formula=rule['formula']
   if attempt=='near-miss' and index==len(ordered)-1:formula='='+cells[sheet][cell]['formula'].lstrip('=')
   lines+=_namebox(calc_cell_reference(sheet,cell))+['write '+historical._formula_for_calc(formula),'press enter']
 elif workflow.startswith('impress-'):
  if target_slide not in [3,4] or slides is None or not 1<=target_slide<=len(slides):raise ValueError('Selection Impress slide layout changed')
  order=[text for text in slides[target_slide-1] if text in targets]
  if len(order)!=len(targets):raise ValueError('Selection Impress target text count/layout changed')
  if len(targets)==1 and target_slide==3:
   # Proven one-target TRAIN analogue geometry.
   lines+=['click 105,420','wait 2']
   coordinates=[(353,390)]
  else:
   if len(slides)!=5 or target_slide!=4 or len(targets)!=2:raise ValueError('Selection Impress five-slide/two-factor profile required')
   lines+=['click 81,455','wait 2'];coordinates=[(430,454),(430,504)]
  for index,(old,(x,y)) in enumerate(zip(order,coordinates)):
   text=old if attempt=='near-miss' and index==len(order)-1 else targets[old]
   lines += [f'double {x},{y}','press ctrl,a','write '+text,'click 780,604']
 elif workflow.startswith('writer-'):
  order=[text for text in paragraphs if text in targets]
  if len(order)!=len(targets):raise ValueError('Selection Writer target paragraph count/layout changed')
  for index,old in enumerate(order):
   text=old if attempt=='near-miss' and index==len(order)-1 else targets[old]
   lines+=['assert_window LibreOffice Writer','press ctrl,h','wait 1','assert_window Find and Replace',
    'click 570,253','wait 1','press ctrl,a','write '+old,'click 570,340','wait 1','press ctrl,a','write '+text,
    'assert_window Find and Replace','click 877,390','wait 1','assert_window Find and Replace',
    f'screen replace-step-{index+1}','click 892,656','wait 1','assert_window LibreOffice Writer']
 else:raise ValueError('Selection workflow unsupported')
 script='\n'.join(lines+SAVE)+'\n';compile_script(script);return script


def actor_script(package_dir:Path,oracle:dict,attempt:str)->str:
 if oracle.get('split')=='final_candidate':
  return historical.actor_script(package_dir,oracle,attempt)
 if oracle.get('split') not in ['selection','train']:raise ValueError('No matching selection/TRAIN structural profile')
 workflow=oracle['workflow']
 if workflow.startswith('calc-'):
  return script_from_layout(workflow=workflow,targets=oracle['targets'],attempt=attempt,
   cells=xlsx_cells(next(package_dir.glob('*.xlsx')).read_bytes()))
 if workflow.startswith('impress-'):
  return script_from_layout(workflow=workflow,targets=oracle['targets'],attempt=attempt,target_slide=oracle.get('target_slide'),
   slides=pptx_slide_shapes(next(package_dir.glob('*.pptx')).read_bytes()))
 return script_from_layout(workflow=workflow,targets=oracle['targets'],attempt=attempt,
  paragraphs=docx_content(next(package_dir.glob('*.docx')).read_bytes())['paragraphs'])


def selection_layout_metadata(directory:Path,row:dict)->dict:
 """Read actor-visible input structure only; do not open any oracle/prompt."""
 workflow=row['workflow'];profile=SELECTION_PROFILES[workflow]
 if workflow.startswith('calc-'):
  sheets=xlsx_cells(next(directory.glob('*.xlsx')).read_bytes())
  if len(sheets)!=3 or profile['sheet'] not in sheets or any(sheets[profile['sheet']].get(c,{}).get('formula') is None for c in profile['cells']):
   raise ValueError('Authored selection Calc three-sheet/two-formula input layout invalid')
 elif workflow.startswith('impress-'):
  slides=pptx_slide_shapes(next(directory.glob('*.pptx')).read_bytes())
  if len(slides)!=5 or len(slides[3])<4:raise ValueError('Authored selection Impress five-slide/two-factor input layout invalid')
 else:
  content=docx_content(next(directory.glob('*.docx')).read_bytes())
  if len(content['tables'])!=1 or len(content['tables'][0])!=4:raise ValueError('Authored selection Writer one-table/three-year input layout invalid')
 result={'package_sha256':row['package_sha256'],'workflow':workflow,'template_group':row['template_group'],'profile':profile,'layout_checked_without_oracle':True}
 if workflow.startswith('calc-'):
  result['namebox_cell_references']=[calc_cell_reference(profile['sheet'],cell) for cell in profile['cells']]
 return result


def metadata_readiness(candidate_root:Path)->dict:
 inventory=json.loads((candidate_root/'candidate-inventory.json').read_bytes());rows=inventory['tasks']
 if Counter(r['split'] for r in rows)!={'train':20,'selection':20,'final_candidate':100}:raise ValueError('Full120 successor cohort split counts changed')
 selection=[r for r in rows if r['split']=='selection']
 checks=[]
 for row in selection:
  if row['template_group']!=factory_v2.TEMPLATES['selection'][row['workflow']]:raise ValueError('Selection authored template identity changed')
  checks.append(selection_layout_metadata(candidate_root/row['split']/row['task_id'],row))
 return {'selection_inputs_layout_checked':len(checks),'workflow_counts':dict(Counter(r['workflow'] for r in selection)),
  'source_family_count':len({tuple(r['source_groups']) for r in selection}),'checks':checks,
  'other_selection_final_oracles_opened':0,'historical_final_script_source_unchanged':True}
