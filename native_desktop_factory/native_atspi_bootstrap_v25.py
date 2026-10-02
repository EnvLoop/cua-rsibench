"""Offline, one-file AT-SPI typelib bootstrap for a fresh owned guest.

No apt/network, library/service replacement, UI configuration or task mutation.
The official package's libatspi bytes match the actual attested guest exactly.
This source operation does not qualify a native image/tree or actor path.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

SCHEMA='cua-native-atspi-offline-bootstrap-v25'
TYPELIB_SHA='210580f698add0a1607ee01e177d93d3b6bdb0fdcfc908e8c1b5c7ebbb503b62'
TYPELIB_BYTES=54164
PACKAGE_URL='https://archive.ubuntu.com/ubuntu/pool/main/a/at-spi2-core/gir1.2-atspi-2.0_2.44.0-3_amd64.deb'
PACKAGE_SHA='c471afd53d03216643cb5fb7d3e0587b27a6bda84d44bc67f566beadbd693781'
PACKAGE_VERSION='2.44.0-3'
REQUIRED={
 '/usr/lib/x86_64-linux-gnu/libatspi.so.0.0.1':'e1df48522f75baa048beb637c749708536bb6459d7dc8e9df12736f003fb2a88',
 '/usr/libexec/at-spi-bus-launcher':'f41a826d0eabf8a864afdebc9f4adfa7892e8a388e3b010b037078d7dcf72594',
 '/usr/libexec/at-spi2-registryd':'d924a5b8c44c1f8ee0b8c6e62c42a3b49c8bca53571346ae736b65ebf4306479',
 '/usr/lib/os-release':'594d5ddd35aedb47f00d9c34d140017907a5b9f93c975aba125fc924daac5c07',
}
PREFIX='/tmp/envloop-atspi-v25'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,code):
 if not ok:raise ValueError(code)
def write_new(path,raw):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as file:file.write(raw);file.flush();os.fsync(file.fileno())

def prerequisite(*,typelib,root=Path('/')):
 typelib=Path(typelib);require(typelib.is_file() and not typelib.is_symlink(),'Pinned official typelib file required')
 raw=typelib.read_bytes();require(len(raw)==TYPELIB_BYTES and sha(raw)==TYPELIB_SHA,'Pinned official typelib bytes changed')
 observed={}
 for name,expected in REQUIRED.items():
  path=Path(root)/name.lstrip('/');require(path.is_file() and not path.is_symlink(),'Attested native prerequisite missing')
  digest=sha(path.read_bytes());require(digest==expected,'Attested native prerequisite content changed');observed[name]=digest
 return {'schema':SCHEMA,'status':'source_prerequisites_match','official_package_url':PACKAGE_URL,'official_package_sha256':PACKAGE_SHA,'official_package_version':PACKAGE_VERSION,
  'typelib_sha256':TYPELIB_SHA,'typelib_bytes':TYPELIB_BYTES,'existing_native_dependencies':observed,'native_mutations':0,'native_image_qualified':False}

def apply(*,typelib,prefix=Path(PREFIX),root=Path('/'),require_fresh_profile=True):
 proof=prerequisite(typelib=typelib,root=root)
 if require_fresh_profile:require(not (Path(root)/'home/user/.config/libreoffice/4/user').exists(),'Bootstrap requires a fresh guest before task/profile preparation')
 prefix=Path(prefix);require(not prefix.exists() and not prefix.is_symlink() and prefix.parent.is_dir(),'Exclusive fresh trusted setup prefix required')
 prefix.mkdir(mode=0o700)
 write_new(prefix/'intent.private.json',json.dumps({'schema':SCHEMA,'typelib_sha256':TYPELIB_SHA,'one_use':True},sort_keys=True).encode())
 write_new(prefix/'Atspi-2.0.typelib',Path(typelib).read_bytes())
 record={**proof,'status':'official_typelib_installed_offline','added_files':['Atspi-2.0.typelib'],'native_dependency_files_replaced':False,'task_files_modified':False,'gui_configuration_changed':False,'gi_typelib_path':str(prefix)}
 write_new(prefix/'result.private.json',json.dumps(record,sort_keys=True).encode());return record


def namespace(*,prefix=Path(PREFIX),runner=subprocess.run):
 prefix=Path(prefix);raw=(prefix/'Atspi-2.0.typelib').read_bytes();require(sha(raw)==TYPELIB_SHA,'Installed typelib changed')
 # One child receives the additional typelib search prefix; the desktop
 # session/global environment is not overwritten or copied into receipts.
 environment=dict(os.environ);environment['GI_TYPELIB_PATH']=str(prefix)
 code="import gi,json;gi.require_version('Atspi','2.0');from gi.repository import Atspi;print(json.dumps({'schema':'cua-native-atspi-namespace-v25','namespace_available':True,'desktop_count':Atspi.get_desktop_count(),'native_mutations':0}))"
 result=runner([sys.executable,'-c',code],env=environment,capture_output=True,text=True,timeout=15)
 require(result.returncode==0 and not result.stderr and len(result.stdout.encode())<=16384,'Native Atspi namespace unavailable after exact prerequisite')
 value=json.loads(result.stdout);require(value.get('namespace_available') is True and type(value.get('desktop_count')) is int,'Actual GI namespace response missing')
 return {**value,'typelib_sha256':TYPELIB_SHA,'native_tree_qualified':False,'actual_focus_qualified':False}


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['check','apply','namespace']);parser.add_argument('--typelib',type=Path);parser.add_argument('--prefix',type=Path,default=Path(PREFIX));args=parser.parse_args()
 if args.mode=='namespace':value=namespace(prefix=args.prefix)
 elif args.mode=='check':value=prerequisite(typelib=args.typelib)
 else:value=apply(typelib=args.typelib,prefix=args.prefix)
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
