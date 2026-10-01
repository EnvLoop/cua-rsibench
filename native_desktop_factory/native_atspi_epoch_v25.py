"""Fresh supplemental native guest-content epoch for the official typelib."""
from pathlib import Path
import hashlib,json
from . import native_atspi_bootstrap_v25 as bootstrap

FILES=('native_desktop_factory/native_atspi_bootstrap_v25.py','native_desktop_factory/native_atspi_epoch_v25.py',
 'native_desktop_factory/native_runtime_assets/Atspi-2.0.typelib','native_desktop_factory/native_runtime_assets/Atspi-2.0.typelib.COPYRIGHT','native_desktop_factory/native_runtime_assets/Atspi-2.0.typelib.PROVENANCE.json',
 'native_desktop_factory/native_accessibility_probe_v23.py','native_desktop_factory/native_accessibility_probe_v24.py',
 'tests/test_native_desktop_atspi_bootstrap_v25.py')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def proposal(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);sources={name:sha((root/name).read_bytes()) for name in FILES}
 if sources[FILES[2]]!=bootstrap.TYPELIB_SHA:raise ValueError('Pinned official Atspi typelib changed')
 return {'schema':'cua-native-atspi-supplemental-source-epoch-v25','source_sha256s':sources,'official_package':{'url':bootstrap.PACKAGE_URL,'sha256':bootstrap.PACKAGE_SHA,'version':bootstrap.PACKAGE_VERSION,'architecture':'amd64'},
  'supplemental_native_content':{'Atspi-2.0.typelib':{'sha256':bootstrap.TYPELIB_SHA,'bytes':bootstrap.TYPELIB_BYTES}},
  'required_existing_native_dependency_sha256s':bootstrap.REQUIRED,'native_setup_prefix':bootstrap.PREFIX,
  'actor_paths':['teacher','control','shared-base','astra','sol56','sol6','luna6'],'all_actor_paths_same_guest_content':True,
  'task_policy':{'max_actions':90,'actor_seconds':720,'lease_seconds':1200},'task_files_modified':False,'gui_configuration_changed':False,
  'requires_fresh_base_and_supplemental_attestation':True,'legacy_projection_alone_can_qualify':False,'actual_namespace_tree_focus_qualified':False,
  'native_image_qualified':False,'provider_dispatch_enabled':False,'old_epoch_reclassified':False}

def supplemental_attestation(*,prefix,base_content_tree_sha256,source_manifest_sha256):
 prefix=Path(prefix)
 for value in [base_content_tree_sha256,source_manifest_sha256]:
  if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Actual new guest/source content binding required')
 raw=(prefix/'Atspi-2.0.typelib').read_bytes();record_raw=(prefix/'result.private.json').read_bytes();record=json.loads(record_raw)
 if sha(raw)!=bootstrap.TYPELIB_SHA or len(raw)!=bootstrap.TYPELIB_BYTES or record.get('status')!='official_typelib_installed_offline' or record.get('task_files_modified') is not False or record.get('gui_configuration_changed') is not False:
  raise ValueError('Actual offline supplemental native content attestation missing')
 body={'schema':'cua-native-atspi-supplemental-guest-content-v25','base_content_tree_sha256':base_content_tree_sha256,'source_manifest_sha256':source_manifest_sha256,
  'typelib_sha256':sha(raw),'typelib_bytes':len(raw),'bootstrap_receipt_sha256':sha(record_raw),'prefix':str(prefix),'legacy_projection_only':False,
  'native_tree_qualified':False,'actual_native_window_focus_required':True,'old_results_reclassified':False}
 return {**body,'supplemental_content_epoch_sha256':sha(canonical(body))}


def prepare_host_bundle(*,output,root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);output=Path(output);output.mkdir(mode=0o700,exist_ok=False)
 names={'native_atspi_bootstrap_v25.py':FILES[0],'Atspi-2.0.typelib':FILES[2],'native_accessibility_probe_v23.py':FILES[5],'native_accessibility_probe_v24.py':FILES[6]}
 for name,relative in names.items():bootstrap.write_new(output/name,(root/relative).read_bytes())
 manifest=proposal(root);bootstrap.write_new(output/'source-manifest.private.json',canonical(manifest))
 return {'schema':'cua-native-atspi-host-bundle-v25','source_manifest_sha256':sha(canonical(manifest)),'copied_source_count':len(names),'provider_calls':0,'native_qualification_claimed':False}


def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['source','prepare-host-bundle']);parser.add_argument('--out',type=Path);args=parser.parse_args()
 print(json.dumps(proposal() if args.mode=='source' else prepare_host_bundle(output=args.out),sort_keys=True))

if __name__=='__main__':main()
