"""Additive per-stage diagnostics around the pinned v27 native prototype.

No fallback, GUI/data mutation or partial metadata qualification. Native API
errors retain stage/domain/code/message hash, while task/window text remains
unpublished. This helper requires exact v23/v24/v27 peers beside it.
"""
from pathlib import Path
import hashlib,importlib.util,json,argparse

PIN='a91fa8664bc2c52c4d5d1232f502b9e91e2eacee8cad17ab6eb752c9f7c5a50e'
SCHEMA='cua-native-visible-query-diagnostic-v28'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load():
 path=Path(__file__).with_name('native_visible_surface_probe_v27.py');raw=path.read_bytes()
 if sha(raw)!=PIN:raise ValueError('Pinned v27 visible query source changed')
 spec=importlib.util.spec_from_file_location('envloop_visible_diagnostic_bound_v27',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def error_facts(error):
 return {'error_class':type(error).__name__,'error_domain':getattr(error,'domain',None),'error_code':getattr(error,'code',None),'error_message_sha256':sha(str(error).encode())}

def run(*,filename,viewport,loader=load):
 module=loader();trace=[];last_stage=None
 def instrument(name):
  original=getattr(module,name)
  def wrapped(*args,**kwargs):
   nonlocal last_stage
   last_stage=name;record={'stage':name,'status':'started'};trace.append(record)
   try:
    result=original(*args,**kwargs);record['status']='completed'
    if name=='collection_queries':record['visible_count']=len(result[0]);record['focus_present']=result[1] is not None
    if name=='native_record':record['native_pid']=result[1]['native_pid'];record['role']=result[1]['role'];record['native_enabled']=result[0]['enabled'];record['native_obscured']=result[0]['obscured']
    return result
   except Exception as error:record['status']='failed';record.update(error_facts(error));raise
  setattr(module,name,wrapped)
 for name in ['owner_module','owned_window','match_rule','collection_queries','ancestors','native_record']:instrument(name)
 try:result=module.run(filename=filename,viewport=viewport);status='native_prototype_returned_unqualified';failure=None
 except Exception as error:result=None;status='actual_native_stage_failed_unqualified';failure={'stage':last_stage,**error_facts(error)}
 return {'schema':SCHEMA,'status':status,'source_sha256':sha(Path(__file__).read_bytes()),'pinned_v27_sha256':PIN,'trace':trace,'failure':failure,'native_result':result,
  'native_mutations':0,'native_qualification_passed':False,'guard_or_query_relaxed':False}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 print(json.dumps(run(filename=args.filename,viewport=[args.width,args.height]),sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
