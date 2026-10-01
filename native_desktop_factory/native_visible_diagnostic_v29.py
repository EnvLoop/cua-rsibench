"""Additive first-failed-stage/private-error diagnostic; old V28 preserved.

Raw GI errors are written only to one fixed trusted guest path with mode600.
The returned diagnostic exposes stage/domain/code/hash, never raw error text.
No text/value query, GUI action, relaxation or native qualification exists.
"""
from pathlib import Path
import os,hashlib,importlib.util,json,argparse

V27_SHA='a91fa8664bc2c52c4d5d1232f502b9e91e2eacee8cad17ab6eb752c9f7c5a50e'
SCHEMA='cua-native-visible-query-diagnostic-v29'
PRIVATE_ERROR_PATH=Path('/tmp/envloop-visible-v29-errors.private.json')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load():
 path=Path(__file__).with_name('native_visible_surface_probe_v27.py');raw=path.read_bytes()
 if sha(raw)!=V27_SHA:raise ValueError('Pinned v27 visible query source changed')
 spec=importlib.util.spec_from_file_location('envloop_visible_diagnostic_bound_v29',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def error_facts(error):return {'error_class':type(error).__name__,'error_domain':getattr(error,'domain',None),'error_code':getattr(error,'code',None),'error_message_sha256':sha(str(error).encode())}

def private_errors(path,records):
 path=Path(path);raw=json.dumps({'schema':'cua-native-private-gi-errors-v29','errors':records,'actor_access_authorized':False,'public_release_authorized':False},sort_keys=True,separators=(',',':')).encode()
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
 return {'sha256':sha(raw),'bytes':len(raw),'mode':0o600,'raw_error_released':False}

def run(*,filename,viewport,loader=load,error_path=PRIVATE_ERROR_PATH):
 module=loader();trace=[];first_failed=None;raw_errors=[]
 def instrument(name):
  original=getattr(module,name)
  def wrapped(*args,**kwargs):
   nonlocal first_failed
   record={'stage':name,'status':'started'};trace.append(record)
   try:
    result=original(*args,**kwargs);record['status']='completed'
    if name=='collection_queries':record['visible_count']=len(result[0]);record['focus_present']=result[1] is not None
    if name=='native_record':record['native_pid']=result[1]['native_pid'];record['role']=result[1]['role'];record['native_enabled']=result[0]['enabled'];record['native_obscured']=result[0]['obscured']
    return result
   except Exception as error:
    if first_failed is None:first_failed=name
    facts=error_facts(error);record['status']='failed';record.update(facts)
    raw_errors.append({'stage':name,'error_class':type(error).__name__,'error_domain':getattr(error,'domain',None),'error_code':getattr(error,'code',None),'raw_error_string':str(error),'raw_error_sha256':facts['error_message_sha256']})
    raise
  setattr(module,name,wrapped)
 for name in ['owner_module','owned_window','match_rule','collection_queries','ancestors','native_record']:instrument(name)
 try:result=module.run(filename=filename,viewport=viewport);status='native_prototype_returned_unqualified';failure=None
 except Exception as error:
  result=None;status='actual_native_stage_failed_unqualified';failure={'stage':first_failed or 'unwrapped_native_run',**error_facts(error)}
  if not raw_errors:raw_errors.append({'stage':first_failed or 'unwrapped_native_run','error_class':type(error).__name__,'error_domain':getattr(error,'domain',None),'error_code':getattr(error,'code',None),'raw_error_string':str(error),'raw_error_sha256':sha(str(error).encode())})
 private_ref=private_errors(error_path,raw_errors)
 return {'schema':SCHEMA,'status':status,'source_sha256':sha(Path(__file__).read_bytes()),'pinned_v27_sha256':V27_SHA,'trace':trace,'failure':failure,'native_result':result,
  'private_error_file':private_ref,'first_failed_stage_preserved':True,'native_mutations':0,'native_qualification_passed':False,'guard_or_query_relaxed':False}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 print(json.dumps(run(filename=args.filename,viewport=[args.width,args.height]),sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
