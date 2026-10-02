"""Scoped rich-SEC adapter across every original Office V4 execution role.

Original signed lifecycle, authority, model loop, paid reservation and600/24
gates remain intact. A fresh V5 source witness and actual native qualification
are required. No previous V4 receipt is promoted to V5 qualification.
"""
from contextlib import contextmanager, ExitStack
from importlib import import_module
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import patch

from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_package_v5 import Package

PARENT_SHA256S = {
 'tools/office_current_authority_v4.py':'1e7ab7c3357fc5e9b9ff73330bfed45ca8926f99d99ddc5cef397694d683273b',
 'tools/office_current_execution_v4.py':'5984bd8e49201618004adaf4d060f1738b4ee6e42bab2546c6a09dcc583c56ef',
 'tools/office_current_evidence_v4.py':'43959af616907bd7dc5f07834a3241df330b907ed758872de8b1a8dc9c3fc227',
 'tools/office_current_budget_performance_v4.py':'1df10793b6195b8fffdd1318a4201c72d09ff06ddba3b31074568a01f57a6b52',
 'tools/office_current_protocol_v4.py':'8b62828e190b8dcf25ab701984e9a57c97de6da54caaf12f604daca0ba3de7d2',
 'tools/office_current_workers_v4.py':'41c4cf3a4902d0ec369df53f797128f84f9fb86899b3dd273ed5aefae2b28ae4',
 'tools/office_current_teacher_v4.py':'a2decd8c2d5e0a91d3054d134bf14df942c2392b9a0393f0bce8e72be38d4389',
 'tools/office_current_worker_cli_v4.py':'c0737aeb1745ac882db4b06b2ef4c0581076e40b6e24b410b4a8cc49338aad2d',
 'tools/office_current_neutral_v4.py':'d5c981a89d4b8d1db52c702dfe74ed988b74303c1158469537aae9433977d8c6',
}
V5_FILES = ('tools/office_current_package_v5.py','tools/office_current_facade_v5.py',
 'tools/office_current_worker_cli_v5.py','tools/office_current_neutral_v5.py',
 'sec_excel_factory/rich_private_replay_v1.py','ppt_wdi_factory/build_portable_v1.py',
 'tools/office_rich_package_inventory_v6.py')
_LOCK = threading.RLock()


def checked_modules(repo=None):
    root=Path(repo or Path(__file__).resolve().parents[1])
    for name,digest in PARENT_SHA256S.items():
        office.require(office.sha((root/name).read_bytes())==digest,
                       'Original Office V4 source changed; rich facade review required')
    return {name:import_module(name.removesuffix('.py').replace('/','.')) for name in PARENT_SHA256S}


def current_sources(repo):
    modules=checked_modules(repo)
    authority=modules['tools/office_current_authority_v4.py']
    # Do not recurse when the authority module has this facade scoped into it.
    names=(*office.SOURCE_FILES,*authority.V4_FILES,*authority.ADAPTER_FILES,*V5_FILES)
    root=Path(repo)
    return {name:office.sha((root/name).read_bytes()) for name in names}


@contextmanager
def source_epoch():
    """Bind rich Package uniformly, then restore every historical module global."""
    with _LOCK, ExitStack() as stack:
        modules=checked_modules()
        protocol=modules['tools/office_current_protocol_v4.py']
        original_manifest=protocol.source_manifest
        def source_manifest(repo):
            value=original_manifest(repo)
            value['office_current_source_epoch']='original-office-current-rich-v5'
            value['office_native_qualification_claimed']=False
            return value
        for module in modules.values():
            if hasattr(module,'Package'):stack.enter_context(patch.object(module,'Package',Package))
            if hasattr(module,'current_sources'):stack.enter_context(patch.object(module,'current_sources',current_sources))
            if hasattr(module,'source_manifest'):stack.enter_context(patch.object(module,'source_manifest',source_manifest))
        yield modules


def neutral_module():
    original=checked_modules()['tools/office_current_neutral_v4.py']
    value=original.module()
    value.runtime=SimpleNamespace(**vars(value.runtime));value.runtime.Package=Package
    value.source_hashes=current_sources
    return value


def counterpart_registry(repo):
    with source_epoch() as modules:
        value=modules['tools/office_current_workers_v4.py'].counterpart_registry(repo)
        value['schema']='office-current-rich-counterpart-registration-v5'
        value['mandatory_execution_entrypoint']='tools.office_current_worker_cli_v5'
        value['source_epoch']='original-office-current-rich-v5'
        value['rich_excel_package_adapter']='tools.office_current_package_v5.Package'
        value['native_qualified']=False
        return value
