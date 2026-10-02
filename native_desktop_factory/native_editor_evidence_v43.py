"""Evaluator-only current mode/medium metadata; never reads or edits contents."""
import hashlib,json,os,time,subprocess
from pathlib import Path
from types import SimpleNamespace
if __package__:
 from . import native_window_current_reader as current
 from .native_editor_capability_v42 import BUILD
else:
 import native_window_current_reader as current
 from native_editor_capability_v42 import BUILD

SEED=Path('/tmp/envloop-editor-v42-seed.private.json')

def actual_build(pid):
 packages=['libreoffice-core','libgtk-3-0','libatspi2.0-0','libatk1.0-0','libatk-bridge2.0-0']
 result=subprocess.run(['dpkg-query','-W','-f=${Package}\t${Version}\n',*packages],capture_output=True,text=True,timeout=5)
 if result.returncode or result.stderr:raise ValueError('Application build version unavailable')
 versions=dict(line.split('\t',1) for line in result.stdout.splitlines())
 plugin='/usr/lib/libreoffice/program/libvclplug_gtk3lo.so'
 if plugin not in (Path('/proc')/str(pid)/'maps').read_text():raise ValueError('Actual GTK bridge plugin unsupported')
 exe=Path(os.readlink(Path('/proc')/str(pid)/'exe'))
 build={'libreoffice_version':versions['libreoffice-core'],'gtk_version':versions['libgtk-3-0'],
  'atspi_version':versions['libatspi2.0-0'],'atk_version':versions['libatk1.0-0'],
  'atk_bridge_version':versions['libatk-bridge2.0-0'],'gtk_plugin_sha256':hashlib.sha256(Path(plugin).read_bytes()).hexdigest(),
  'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
 if str(exe)!=current.business.EXE_PATH or build!=BUILD:raise ValueError('Unsupported actual application build')
 return build

def medium_metadata(pipe_name,filename,x11):
 expected_path='/tmp/OSL_PIPE_'+str(x11['uid'])+'_'+pipe_name
 rows=[line.split() for line in Path('/proc/net/unix').read_text().splitlines()[1:]]
 sockets=[row for row in rows if len(row)>=8 and row[-1]==expected_path]
 if len(sockets)!=1:raise ValueError('Evaluator application pipe missing/ambiguous')
 inode=sockets[0][6];pid_directory=Path('/proc')/str(x11['pid'])
 if not any(os.readlink(fd)=='socket:['+inode+']' for fd in (pid_directory/'fd').iterdir()):raise ValueError('Application pipe not owned by current soffice PID')
 if Path(expected_path).stat().st_uid!=x11['uid']:raise ValueError('Application pipe owner differs')
 import uno
 local=uno.getComponentContext();resolver=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local)
 context=resolver.resolve('uno:pipe,name='+pipe_name+';urp;StarOffice.ComponentContext')
 desktop=context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',context)
 component=desktop.getCurrentComponent()
 if component is None:raise ValueError('Current application medium missing')
 expected=uno.systemPathToFileUrl('/home/user/'+filename)
 if component.getURL()!=expected or component.getLocation()!=expected or component.hasLocation() is not True:raise ValueError('Current original application medium differs')
 readonly=component.isReadonly()
 if type(readonly) is not bool:raise ValueError('Application medium state unknown')
 path=Path('/home/user')/filename;stat=path.stat()
 if stat.st_uid!=x11['uid'] or os.getuid()!=x11['uid']:raise ValueError('Original file actor ownership differs')
 return {'application_is_readonly':readonly,'original_medium_writable':not readonly,
  'original_file_writable':os.access(path,os.W_OK),'original_url_sha256':hashlib.sha256(expected.encode()).hexdigest(),
  'file_uid':stat.st_uid,'probe_uid':os.getuid(),'document_content_read':False,'application_store_called':False,
  'evaluator_pipe_owned_by_current_native_pid':True,'current_soffice_pid':x11['pid']}

def native_menu_state(filename,*,bootstrap=False,selected_identity=None,hooks=None):
 earlier=current.business.load_current();base=earlier.load_base();peer=base.load();reader=peer.load('native_visible_surface_probe_v31.py',peer.V31_SHA)
 identity=peer.load('native_hit_identity_diagnostic_v33.py',peer.V33_SHA).identity
 old=reader.namespace['peer']();owner0=old.owner_module();owner=SimpleNamespace(load=owner0.load,ownership=current.business.ownership)
 frozen,x11,wrapped=old.owned_window(owner,filename);window=wrapped.value
 from gi.repository import Atspi
 earlier.cache_owned_application(reader,Atspi,window,pid=x11['pid'],identity=identity)
 class Sink:
  def append(self,row):pass
 ancestry=base.forward_owned_paths(peer,Sink())(window,x11['pid'],identity)
 pending=[(window,0)];seen=set();matches=[]
 while pending and len(seen)<1024:
  node,depth=pending.pop(0);key=identity(node)['identity_sha256']
  if key in seen:continue
  seen.add(key);chain=ancestry.ancestors(node,window)
  if node.get_process_id()!=x11['pid']:raise ValueError('Foreign native mode node')
  flags=reader.state_flags(Atspi,node)
  if flags['DEFUNCT'] or flags['STALE']:continue
  role=node.get_role_name()
  if role=='check menu item' and node.get_name().replace('_','').replace('&','').strip()=='Edit Mode':
   parents=[p.get_name().replace('_','').replace('&','').strip() for p in chain if p.get_role_name()=='menu']
   if 'Edit' in parents and (bootstrap and flags['VISIBLE'] and flags['SHOWING'] or not bootstrap and key==selected_identity):
    if hooks is not None:hooks['mode_node']=node;hooks['Atspi']=Atspi;hooks['frozen']=frozen
    matches.append({'node_identity_sha256':key,'checked':bool(node.get_state_set().contains(Atspi.StateType.CHECKED)),
     'enabled':flags['ENABLED'],'sensitive':flags['SENSITIVE'],'stale':flags['STALE'],'defunct':flags['DEFUNCT'],
     'visible':flags['VISIBLE'],'showing':flags['SHOWING'],'name':'Edit Mode','parent_menu':'Edit','command':'.uno:EditDoc'})
  if depth>=24 or flags['MANAGES_DESCENDANTS']:continue
  count=node.get_child_count()
  if count>128:continue
  for index in range(count):
   if len(seen)+len(pending)>=1024:break
   pending.append((node.get_child_at_index(index),depth+1))
 if len(matches)!=1:raise ValueError('Current native Edit Mode missing/ambiguous')
 if frozen.x11()!=x11:raise ValueError('Current native document changed during mode query')
 binding=hashlib.sha256(json.dumps({k:x11[k] for k in ('window_id','pid','uid','title','wm_class')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return matches[0],binding,x11

class CurrentEvidence(dict):
 def refresh(self):
  node=self.hooks['mode_node'];Atspi=self.hooks['Atspi']
  if 'frozen' in self.hooks and self.hooks['frozen'].x11()!=self.x11:raise ValueError('Current document changed before capability use')
  if hasattr(node,'get_process_id') and node.get_process_id()!=self.x11['pid']:raise ValueError('Native mode node process changed')
  node.clear_cache();flags=node.get_state_set()
  self['mode'].update(checked=bool(flags.contains(Atspi.StateType.CHECKED)),enabled=bool(flags.contains(Atspi.StateType.ENABLED)),sensitive=bool(flags.contains(Atspi.StateType.SENSITIVE)),stale=bool(flags.contains(Atspi.StateType.STALE)),defunct=bool(flags.contains(Atspi.StateType.DEFUNCT)))
  self['medium']=medium_metadata(self.pipe_name,self.filename,self.x11)
  now=time.monotonic();self['mode'].update(observed_at=now,expires_at=now+10)
  return self

def evidence(filename):
 seed=json.loads(SEED.read_bytes());hooks={};node,binding,x11=native_menu_state(filename,selected_identity=seed['node_identity_sha256'],hooks=hooks)
 if binding!=seed['document_binding_sha256']:raise ValueError('Mode seed belongs to another document')
 medium=medium_metadata(seed['pipe_name'],filename,x11);now=time.monotonic()
 mode={**node,'schema':'owned-current-edit-mode-evidence-v42','document_binding_sha256':binding,
  'observed_at':now,'expires_at':now+10,'visible_initial_native_proof':seed['visible_initial_native_proof'],
  'same_native_node_reopened':True,'current_native_state_read':True,'unique_current_command':True}
 result=CurrentEvidence(build=actual_build(x11['pid']),mode=mode,medium=medium,binding=binding,native_pid=x11['pid'],native_uid=x11['uid']);result.hooks=hooks;result.pipe_name=seed['pipe_name'];result.filename=filename;result.x11=x11;return result

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--filename',required=True);parser.add_argument('--bootstrap',action='store_true');parser.add_argument('--pipe');args=parser.parse_args()
 if args.bootstrap:
  node,binding,x11=native_menu_state(args.filename,bootstrap=True)
  result={**node,'document_binding_sha256':binding,'visible_initial_native_proof':node['visible'] and node['showing'],'pipe_name':args.pipe}
 else:result=evidence(args.filename)
 print(json.dumps(result,sort_keys=True,separators=(',',':')))
