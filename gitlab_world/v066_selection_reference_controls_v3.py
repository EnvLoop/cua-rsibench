"""Exact proved GitLab native CSV preview layout; consumed V1/V2 unchanged."""
import asyncio
from hashlib import sha256
from pathlib import Path
import time
from types import FunctionType, ModuleType
from . import v066_selection_reference_controls_v2 as prior

PARENT_SHA='aba6d8c84f53d19462a907d373709fc882d5f7630d178760c76e97d1d28205c6'
if sha256(Path(prior.__file__).read_bytes()).hexdigest()!=PARENT_SHA:
    raise ValueError('Frozen consumed selection V2 changed')
FIELDS=['asset_id','cve_id','vendor','product','site','disposition']
world,models=prior.world,prior.models
_scope=ModuleType('gitlab_world._selection_reference_controls_v3')
_scope.__dict__.update(vars(prior._scope));_scope.__file__=__file__
_scope.SCHEMA='gitlab-original-selection20-reference-authority-v3'
for name,value in list(vars(prior._scope).items()):
    if isinstance(value,FunctionType) and value.__globals__ is vars(prior._scope):
        clone=FunctionType(value.__code__,vars(_scope),value.__name__,value.__defaults__,value.__closure__)
        clone.__kwdefaults__=value.__kwdefaults__;clone.__annotations__=value.__annotations__
        setattr(_scope,name,clone)


def source_binding():
    value=prior.source_binding();value.pop('binding_sha256');root=Path(__file__).resolve().parents[1]
    for name in ('gitlab_world/v066_selection_reference_controls_v3.py','tests/test_gitlab_selection_reference_controls_v3.py'):
        value['source_sha256s'][name]=sha256((root/name).read_bytes()).hexdigest()
    value.update(schema='gitlab-selection20-reference-controller-source-v3',
        native_csv_preview_layout='numeric_0_to_5_columns_exact_first_body_csv_header',
        consumed_v2_control_credit=0,csv_generic_header_or_target_relaxation=False)
    return value|{'binding_sha256':models.common.digest(models.common.canonical(value))}


def csv_layout(headers,rows,native,target_row):
    """Two exact layouts; the proved preview header is never a data record."""
    layout=None;data=rows
    if headers==FIELDS:layout='semantic_csv_header'
    elif (headers==['0','1','2','3','4','5'] and rows and rows[0]==FIELDS and
          native.get('tag')=='TABLE' and native.get('role')=='table' and
          {'b-table','gl-table'}<=set(native.get('classes','').split())):
        layout='proved_native_numeric_preview';data=rows[1:]
    complete=bool(data) and all(len(row)==6 and all(row) for row in data)
    target=target_row is None or data.count(target_row)==1
    return {'layout':layout,'headers_match':layout is not None,'complete_nonempty_data_rows':complete,
        'unique_exact_public_target':target,'data_row_count':len(data),
        'ready':layout is not None and complete and target}


async def _readable(active,locator,expected,*,table=False,target_row=None,relative=None):
    if not table:
        return await prior._readable(active,locator,expected,table=False,target_row=target_row,relative=relative)
    deadline=min(time.monotonic()+30,active.guard.lease['expires_at'])
    uri=active.page.url;previous=None;stable=None;samples=[]
    try:
        while time.monotonic()<deadline:
            if relative is not None:prior._owned_uri(active,relative)
            world.require(active.page.url==uri,'selection_source_document_changed')
            async def sample():
                count=await locator.count();state={'native_table_count':count,'current_uri':active.page.url}
                if count!=1:return None,state
                state['visible']=await locator.is_visible()
                if not state['visible']:return None,state
                text=await locator.inner_text()
                state['headers']=[s.strip() for s in await locator.locator('tr').first.locator('th,td').all_text_contents()]
                rows=locator.locator('tbody tr');state['rows']=[]
                for i in range(await rows.count()):
                    state['rows'].append([s.strip() for s in await rows.nth(i).locator('th,td').all_text_contents()])
                state['native']=await locator.evaluate('e=>({tag:e.tagName,role:e.getAttribute("role"),classes:e.className,connected:e.isConnected,current_document:e.ownerDocument===document})')
                state['layout']=csv_layout(state['headers'],state['rows'],state['native'],target_row)
                state['visible_loading']=await locator.locator('.gl-skeleton-loader,[data-testid*="skeleton"],.gl-spinner').filter(visible=True).count()
                state['bounds']=await locator.bounding_box()
                state['expected_text_present']=all(value in text for value in expected)
                box=state['bounds']
                ready=(state['layout']['ready'] and state['native']['connected'] and state['native']['current_document'] and
                       state['visible_loading']==0 and state['expected_text_present'] and box and box['width']>0 and box['height']>0)
                return (text,box) if ready else None,state
            current,state=await asyncio.wait_for(sample(),max(.001,deadline-time.monotonic()))
            if relative is not None:prior._owned_uri(active,relative)
            world.require(active.page.url==uri,'selection_source_document_changed')
            tick=time.monotonic();samples.append({'monotonic':tick,'state':state})
            if current is not None and current==previous and stable is not None and tick-stable>=.1:return
            if current!=previous:previous,stable=current,tick if current is not None else None
            await asyncio.sleep(min(.05,max(0,deadline-time.monotonic())))
        raise ValueError('selection_source_content_not_stable_within_original_budget')
    except BaseException as error:
        error.csv_readiness_samples=samples
        try:
            sequence=getattr(active,'_csv_readiness_failure_sequence',0)
            active._csv_readiness_failure_sequence=sequence+1
            active.guard.store.json(f'reference-csv/refusal-{sequence:03d}.private.json',
                {'schema':'gitlab-selection-v3-exact-csv-readiness-refusal-v1','maximum_seconds':30,
                 'original_uri':uri,'samples':samples,'target_row':target_row,
                 'business_input_performed_by_readiness':False,'ready_rule_relaxed':False},'native_observation_envelope')
        except BaseException as capture_error:error.csv_diagnostic_capture_error=type(capture_error).__name__
        raise


_scope._owned_uri=prior._owned_uri
_scope._readable=_readable
_scope.source_binding=source_binding
def __getattr__(name):return getattr(_scope,name)
if __name__=='__main__':_scope.main()
