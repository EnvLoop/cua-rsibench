"""Evaluator-only current mode/medium metadata; never reads or edits contents."""
import hashlib,json,os,time,subprocess,stat,copy,re
from pathlib import Path
from types import SimpleNamespace
if __package__:
 from . import native_window_current_reader as current
 from .native_editor_capability_v42 import BUILD
else:
 import native_window_current_reader as current
 from native_editor_capability_v42 import BUILD

SEED=Path('/tmp/envloop-editor-v45-seed.private.json')

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

def checked_listener_rows(rows,owned_socket_inodes):
 if type(rows) is not list or not rows or len(rows)>64:raise ValueError('Evaluator pipe rows missing/unbounded')
 for row in rows:
  if type(row) is not dict or type(row.get('inode')) is not str or re.fullmatch(r'[0-9]+',row['inode']) is None or row.get('type')!='0001':raise ValueError('Evaluator pipe metadata unsupported')
  if row['inode'] not in owned_socket_inodes:raise ValueError('Evaluator pipe socket not held by current native PID')
 if len({row['inode'] for row in rows})!=len(rows):raise ValueError('Evaluator pipe socket rows duplicated')
 listeners=[row for row in rows if row.get('flags')=='00010000' and row.get('state')=='01']
 connections=[row for row in rows if row.get('flags')=='00000000' and row.get('state')=='03']
 if len(listeners)!=1 or len(listeners)+len(connections)!=len(rows):raise ValueError('Evaluator pipe listener missing/ambiguous or state unsupported')
 return {'listener':copy.deepcopy(listeners[0]),'owned_accepted_connections':copy.deepcopy(connections),'unique_current_owned_listener_checked':True}

def medium_metadata(pipe_name,filename,x11):
 expected_path='/tmp/OSL_PIPE_'+str(x11['uid'])+'_'+pipe_name
 rows=[line.split() for line in Path('/proc/net/unix').read_text().splitlines()[1:]]
 sockets=[{'flags':row[3],'type':row[4],'state':row[5],'inode':row[6]} for row in rows if len(row)>=8 and row[-1]==expected_path]
 pid_directory=Path('/proc')/str(x11['pid']);owned_socket_inodes=set()
 for fd in (pid_directory/'fd').iterdir():
  try:link=os.readlink(fd)
  except FileNotFoundError:continue
  match=re.fullmatch(r'socket:\[([0-9]+)\]',link)
  if match:owned_socket_inodes.add(match[1])
 listener=checked_listener_rows(sockets,owned_socket_inodes)
 path_stat=Path(expected_path).lstat()
 if not stat.S_ISSOCK(path_stat.st_mode) or path_stat.st_uid!=x11['uid']:raise ValueError('Application pipe owner/type differs')
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
 path=Path('/home/user')/filename;file_stat=path.stat()
 if file_stat.st_uid!=x11['uid'] or os.getuid()!=x11['uid']:raise ValueError('Original file actor ownership differs')
 return {'application_is_readonly':readonly,'original_medium_writable':not readonly,
  'original_file_writable':os.access(path,os.W_OK),'original_url_sha256':hashlib.sha256(expected.encode()).hexdigest(),
  'file_uid':file_stat.st_uid,'probe_uid':os.getuid(),'document_content_read':False,'application_store_called':False,
  'evaluator_pipe_owned_by_current_native_pid':True,'current_owned_listener_evidence':listener,'current_soffice_pid':x11['pid']}

def reopen_mode_path(window,path,pid,identity):
 if type(pid) is not int or pid<=0 or type(path) is not list or not 0<len(path)<=24:raise ValueError('Native mode path invalid/unbounded')
 def key(node):
  result=identity(node)
  if result.get('available') is not True or type(result.get('identity_sha256')) is not str or re.fullmatch(r'[0-9a-f]{64}',result['identity_sha256']) is None:raise ValueError('Native mode identity missing')
  if node.get_process_id()!=pid:raise ValueError('Native mode process differs')
  return result['identity_sha256']
 cursor=window;chain=[window]
 for edge in path:
  if type(edge) is not dict or set(edge)!={'parent_identity_sha256','child_index','child_identity_sha256'}:raise ValueError('Native mode edge shape invalid')
  if key(cursor)!=edge['parent_identity_sha256']:raise ValueError('Native mode parent identity changed')
  index=edge['child_index'];count=cursor.get_child_count()
  if type(index) is not int or type(count) is not int or not 0<=index<count<=128 or key(cursor)!=edge['parent_identity_sha256']:raise ValueError('Native mode parent/slot changed')
  first=cursor.get_child_at_index(index)
  if key(first)!=edge['child_identity_sha256'] or key(cursor)!=edge['parent_identity_sha256']:raise ValueError('Native mode first edge changed')
  count=cursor.get_child_count()
  if type(count) is not int or not 0<=index<count<=128:raise ValueError('Native mode second child set changed')
  second=cursor.get_child_at_index(index)
  if key(second)!=edge['child_identity_sha256'] or key(cursor)!=edge['parent_identity_sha256']:raise ValueError('Native mode second edge changed')
  cursor=second;chain.append(cursor)
 return cursor,chain

def current_mode_path(filename,seed,hooks):
 earlier=current.business.load_current();base=earlier.load_base();peer=base.load();reader=peer.load('native_visible_surface_probe_v31.py',peer.V31_SHA)
 identity=peer.load('native_hit_identity_diagnostic_v33.py',peer.V33_SHA).identity
 old=reader.namespace['peer']();owner0=old.owner_module();owner=SimpleNamespace(load=owner0.load,ownership=current.business.ownership)
 frozen,x11,wrapped=old.owned_window(owner,filename);window=wrapped.value
 from gi.repository import Atspi
 earlier.cache_owned_application(reader,Atspi,window,pid=x11['pid'],identity=identity)
 node,chain=reopen_mode_path(window,seed['native_forward_path'],x11['pid'],identity)
 flags=reader.state_flags(Atspi,node)
 parents=[n.get_name().replace('_','').replace('&','').strip() for n in chain if n.get_role_name()=='menu']
 if node.get_role_name()!='check menu item' or node.get_name().replace('_','').replace('&','').strip()!='Edit Mode' or 'Edit' not in parents or identity(node)['identity_sha256']!=seed['node_identity_sha256']:raise ValueError('Current native mode command changed')
 if frozen.x11()!=x11:raise ValueError('Current native document changed during mode path')
 binding=hashlib.sha256(json.dumps({k:x11[k] for k in ('window_id','pid','uid','title','wm_class')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 hooks.update(mode_node=node,Atspi=Atspi,frozen=frozen,window=window,identity=identity)
 return {'node_identity_sha256':identity(node)['identity_sha256'],'checked':bool(node.get_state_set().contains(Atspi.StateType.CHECKED)),
  'enabled':flags['ENABLED'],'sensitive':flags['SENSITIVE'],'stale':flags['STALE'],'defunct':flags['DEFUNCT'],'visible':flags['VISIBLE'],'showing':flags['SHOWING'],'name':'Edit Mode','parent_menu':'Edit','command':'.uno:EditDoc'},binding,x11

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
 pending=[(window,0,[])];seen=set();matches=[]
 while pending and len(seen)<1024:
  node,depth,path=pending.pop(0);key=identity(node)['identity_sha256']
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
    matches.append({'native_forward_path':path,'node_identity_sha256':key,'checked':bool(node.get_state_set().contains(Atspi.StateType.CHECKED)),
     'enabled':flags['ENABLED'],'sensitive':flags['SENSITIVE'],'stale':flags['STALE'],'defunct':flags['DEFUNCT'],
     'visible':flags['VISIBLE'],'showing':flags['SHOWING'],'name':'Edit Mode','parent_menu':'Edit','command':'.uno:EditDoc'})
  if depth>=24 or flags['MANAGES_DESCENDANTS']:continue
  count=node.get_child_count()
  if count>128:continue
  for index in range(count):
   if len(seen)+len(pending)>=1024:break
   child=node.get_child_at_index(index);pending.append((child,depth+1,path+[{'parent_identity_sha256':key,'child_index':index,'child_identity_sha256':identity(child)['identity_sha256']}]))
 if len(matches)!=1:raise ValueError('Current native Edit Mode missing/ambiguous')
 if frozen.x11()!=x11:raise ValueError('Current native document changed during mode query')
 binding=hashlib.sha256(json.dumps({k:x11[k] for k in ('window_id','pid','uid','title','wm_class')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return matches[0],binding,x11

class CurrentEvidence(dict):
 def refresh(self):
  refreshed,_=reopen_mode_path(self.hooks['window'],self.forward_path,self.x11['pid'],self.hooks['identity']);self.hooks['mode_node']=refreshed
  node=self.hooks['mode_node'];Atspi=self.hooks['Atspi']
  if 'frozen' in self.hooks and self.hooks['frozen'].x11()!=self.x11:raise ValueError('Current document changed before capability use')
  if hasattr(node,'get_process_id') and node.get_process_id()!=self.x11['pid']:raise ValueError('Native mode node process changed')
  node.clear_cache();flags=node.get_state_set()
  self['mode'].update(checked=bool(flags.contains(Atspi.StateType.CHECKED)),enabled=bool(flags.contains(Atspi.StateType.ENABLED)),sensitive=bool(flags.contains(Atspi.StateType.SENSITIVE)),stale=bool(flags.contains(Atspi.StateType.STALE)),defunct=bool(flags.contains(Atspi.StateType.DEFUNCT)))
  self['medium']=medium_metadata(self.pipe_name,self.filename,self.x11)
  now=time.monotonic();self['mode'].update(observed_at=now,expires_at=now+10)
  return self

def evidence(filename):
 seed=json.loads(SEED.read_bytes());hooks={};node,binding,x11=current_mode_path(filename,seed,hooks)
 if binding!=seed['document_binding_sha256']:raise ValueError('Mode seed belongs to another document')
 medium=medium_metadata(seed['pipe_name'],filename,x11);now=time.monotonic()
 mode={**node,'schema':'owned-current-edit-mode-evidence-v42','document_binding_sha256':binding,
  'observed_at':now,'expires_at':now+10,'visible_initial_native_proof':seed['visible_initial_native_proof'],
  'same_native_node_reopened':True,'current_native_state_read':True,'unique_current_command':True}
 result=CurrentEvidence(build=actual_build(x11['pid']),mode=mode,medium=medium,binding=binding,native_pid=x11['pid'],native_uid=x11['uid']);result.hooks=hooks;result.pipe_name=seed['pipe_name'];result.filename=filename;result.x11=x11;result.forward_path=seed['native_forward_path'];return result

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--filename',required=True);parser.add_argument('--bootstrap',action='store_true');parser.add_argument('--pipe');args=parser.parse_args()
 if args.bootstrap:
  node,binding,x11=native_menu_state(args.filename,bootstrap=True)
  result={**node,'document_binding_sha256':binding,'visible_initial_native_proof':node['visible'] and node['showing'],'pipe_name':args.pipe}
 else:result=evidence(args.filename)
 print(json.dumps(result,sort_keys=True,separators=(',',':')))
