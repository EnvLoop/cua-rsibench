"""One supported preference in a fresh isolated guest, before document open."""
import hashlib,json,os,re,stat,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
OOR='http://openoffice.org/2001/registry'
CONFIG_PATH='/org.openoffice.Office.Common/Save/Document'
NAME='WarnAlienFormat'
PROFILE=Path('/home/user/.config/libreoffice/4/user')
SCHEMA_PATH=Path('/usr/lib/libreoffice/share/registry/main.xcd')
EXECUTABLE=Path('/usr/lib/libreoffice/program/soffice.bin')
EXECUTABLE_SHA='65bab645455ca7fe2f38e61f5d36b84dc02c229594d6c0598b5078a819d4f43a'
XML=('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="'+OOR+'" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><item oor:path="'+CONFIG_PATH+'"><prop oor:name="'+NAME+'" oor:op="fuse"><value>false</value></prop></item></oor:items>\n').encode()
POLICY={'schema':'native-isolated-format-startup-preference-v48','path':CONFIG_PATH,'property':NAME,'value':False,'applied_before_document_open':True,'scope':'all_seven_roles_and_distinct_reset','actor_document_api_exposed':False,'native_guards_unchanged':True,'old_results_reclassified':False}
def digest(raw):return hashlib.sha256(raw).hexdigest()

def installed_default(raw):
 root=ET.fromstring(raw);values=[]
 for component in root.iter():
  if component.tag.split('}')[-1]!='component-schema' or component.get('{'+OOR+'}name')!='Common' or component.get('{'+OOR+'}package')!='org.openoffice.Office':continue
  wrapped=[c for c in component if c.tag.split('}')[-1]=='component']
  if len(wrapped)!=1:raise ValueError('Installed preference component wrapper missing/ambiguous')
  level=wrapped
  for name in ('Save','Document',NAME):level=[c for n in level for c in n if c.get('{'+OOR+'}name')==name]
  for prop in level:
   if prop.tag.split('}')[-1]!='prop' or prop.get('{'+OOR+'}type')!='xs:boolean':raise ValueError('Installed preference schema type differs')
   values.extend(v.text for v in prop if v.tag.split('}')[-1]=='value')
 if values!=['true']:raise ValueError('Installed WarnAlienFormat schema/default differs')
 return True

def apply_local():
 if os.getuid()!=1000:raise ValueError('Isolated guest principal differs')
 if PROFILE.exists() or PROFILE.is_symlink():raise ValueError('Preset requires absent fresh profile')
 for p in (PROFILE.parent,PROFILE.parent.parent,PROFILE.parent.parent.parent,PROFILE.parent.parent.parent.parent):
  if p.is_symlink():raise ValueError('Preset profile ancestry is symlinked')
 probe=subprocess.run(['pgrep','-x','soffice.bin'],capture_output=True,text=True,timeout=5)
 if probe.returncode!=1 or probe.stdout.strip():raise ValueError('LibreOffice already running before startup preference')
 if digest(EXECUTABLE.read_bytes())!=EXECUTABLE_SHA:raise ValueError('Installed LibreOffice build differs')
 info=SCHEMA_PATH.stat()
 if SCHEMA_PATH.is_symlink() or info.st_uid!=0 or info.st_mode&0o022:raise ValueError('Installed schema ownership differs')
 raw=SCHEMA_PATH.read_bytes();installed_default(raw)
 PROFILE.mkdir(mode=0o700,parents=True)
 path=PROFILE/'registrymodifications.xcu';fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(XML);stream.flush();os.fsync(stream.fileno())
 if path.read_bytes()!=XML:raise ValueError('Startup preference readback differs')
 return {'schema':'native-format-startup-applied-v48','principal_uid':os.getuid(),'application_not_running':True,'profile_absent_before_apply':True,'installed_default_true_proved':True,'installed_schema_sha256':digest(raw),'executable_sha256':EXECUTABLE_SHA,'registry_sha256':digest(XML),'registry_mode':stat.S_IMODE(path.stat().st_mode),'policy':POLICY,'native_mutations_before_actor':0,'document_bytes_modified':False}

def parent_registry_projection(raw):
 """Require the declared false property, then compare every remaining byte/state."""
 root=ET.fromstring(raw);matches=[]
 for item in root:
  for prop in item:
   if prop.get('{'+OOR+'}name')==NAME:matches.append((item,prop))
 if len(matches)!=1:raise ValueError('Exactly one declared startup preference required')
 item,prop=matches[0]
 if item.get('{'+OOR+'}path')!=CONFIG_PATH or prop.get('{'+OOR+'}op')!='fuse' or len(prop)!=1 or prop[0].tag.split('}')[-1]!='value' or prop[0].text!='false':raise ValueError('Startup preference false/identity proof missing')
 pattern=rb'<item\b[^>]*\boor:path="'+CONFIG_PATH.encode()+rb'"[^>]*>.*?</item>'
 blocks=list(re.finditer(pattern,raw,re.S))
 if len(blocks)!=1:raise ValueError('Preference lexical path missing/ambiguous')
 block=blocks[0];body=block.group()
 field=rb'<prop\b[^>]*\boor:name="WarnAlienFormat"[^>]*>\s*<value>\s*false\s*</value>\s*</prop>'
 found=list(re.finditer(field,body,re.S))
 if len(found)!=1:raise ValueError('Preference lexical field missing/ambiguous')
 projected=body[:found[0].start()]+body[found[0].end():]
 inner=projected[projected.index(b'>')+1:projected.rindex(b'</item>')]
 if not inner.strip():projected=b''
 return raw[:block.start()]+projected+raw[block.end():]

def setup(guest):
 from . import common_native_guest_v31 as common
 source=Path(__file__).read_bytes();remote=common.REMOTE+'/native_format_startup_preset_v48.py'
 common.json_put(guest.root,guest.out/'format-startup-intent.private.json',{'policy':POLICY,'script_sha256':digest(source),'registry_sha256':digest(XML),'before_original_document_stage_and_open':True,'automatic_retries':0})
 installed=bytes(guest.sandbox.files.read(str(SCHEMA_PATH),format='bytes'))
 if not installed or len(installed)>8388608:raise ValueError('Installed schema snapshot absent/unbounded')
 common.put(guest.root,guest.out/'format-installed-main.private.xcd',installed)
 installed_default(installed)
 guest.sandbox.files.write(remote,source)
 result=guest.sandbox.commands.run('python3 '+remote,timeout=15,request_timeout=25)
 common.json_put(guest.root,guest.out/'format-startup-result.private.json',{'exit_code':result.exit_code,'stdout':result.stdout,'stderr':result.stderr})
 if result.exit_code!=0 or result.stderr:raise ValueError('Declared startup preference failed')
 row=json.loads(result.stdout)
 if row.get('schema')!='native-format-startup-applied-v48' or row.get('policy')!=POLICY or row.get('registry_sha256')!=digest(XML) or row.get('installed_schema_sha256')!=digest(installed):raise ValueError('Startup preference source/readback differs')
 guest.receipt['declared_format_startup_preference']=row;guest.persist()

if __name__=='__main__':print(json.dumps(apply_local(),sort_keys=True,separators=(',',':')))
