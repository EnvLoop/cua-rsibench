"""Prospective TRAIN diagnostic save policy; raw strict scoring stays separate.

Metadata grammar is derived from retained original Office TRAIN snapshots.
The policy is private, source-bound and frozen before a new candidate is read.
It does not admit tasks, award model benchmark scores or alter the strict core.
"""
from __future__ import annotations

import copy
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image
from ppt_wdi_factory import verify
from tools import office_single_account_train_pilot_v1 as manual
from tools import ppt_native_train_collection_proposal_v1 as prior
from tools import pptx_title_size_guard as guard

SCHEMA='office-ppt-prospective-native-save-train-policy-v1'
SUPPORT_RECEIPT_SHA='dc7f46e508ea54ddc437fa19cc3d4c705acf32eefc5e74984b672f7a6a6b5129'
GUID=re.compile(r'\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}\Z')
TIME=re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z?\Z')
REV='{http://schemas.microsoft.com/office/powerpoint/2015/10/main}'
SOURCE_FILES=('tools/office_ppt_prospective_native_save_v1.py',
    'tools/ppt_native_train_collection_proposal_v1.py','tools/office_single_account_train_pilot_v1.py',
    'ppt_wdi_factory/verify.py','ppt_wdi_factory/plan.py','tools/audit_ppt_wdi_web_train_triad_v1.py')


def require(ok,code):
    if not ok:raise prior.ProposalError(code)


def source_hashes():
    root=Path(__file__).resolve().parents[1]
    return {n:manual._sha((root/n).read_bytes()) for n in SOURCE_FILES}


def xml(raw):
    root=prior.semantic_xml(raw)
    require(all(not (n.tail or '').strip() for n in root.iter()),'native_save_xml_tail_payload')
    return root


def uint(value,bits=32):
    require(type(value) is str and bool(re.fullmatch(r'0|[1-9][0-9]{0,9}',value)) and
            int(value)<2**bits,'native_save_integer_invalid')
    return int(value)


def timestamp(value,*,ceiling=None,floor=None):
    require(type(value) is str and TIME.fullmatch(value),'native_save_timestamp_invalid')
    try:parsed=datetime.fromisoformat(value.removesuffix('Z')).replace(tzinfo=timezone.utc)
    except ValueError:raise prior.ProposalError('native_save_timestamp_invalid') from None
    require(2000<=parsed.year<=2100 and
            (ceiling is None or parsed<=ceiling) and
            (floor is None or parsed>=floor),'native_save_timestamp_outside_window')
    return parsed


def thumbnail_pixels(raw):
    require(0<len(raw)<=100_000 and raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9') and
        raw.find(b'\xff\xd9')==len(raw)-2 and
        re.search(br'\xff[\xe1-\xef\xfe]',raw) is None,'native_save_thumbnail_payload')
    # Only the standard 14-byte JFIF header is allowed as an APP segment.
    pos=2
    while pos+4<len(raw):
        require(raw[pos]==255,'native_save_thumbnail_encoding')
        marker=raw[pos+1];pos+=2
        if marker in (0xDA,0xD9):break
        require(marker not in (0xD8,0x01) and not 0xD0<=marker<=0xD7,
                'native_save_thumbnail_encoding')
        length=int.from_bytes(raw[pos:pos+2],'big')
        require(length>=2 and pos+length<=len(raw),'native_save_thumbnail_encoding')
        if marker==0xE0:
            payload=raw[pos+2:pos+length]
            require(length==16 and payload.startswith(b'JFIF\0\x01\x01') and payload[7]<=2 and
                    1<=int.from_bytes(payload[8:10],'big')<=600 and
                    payload[8:10]==payload[10:12] and payload[-2:]==b'\0\0',
                    'native_save_thumbnail_jfif_payload')
        pos+=length
    try:
        with Image.open(io.BytesIO(raw)) as im:
            require(im.format=='JPEG' and im.size==(256,144) and
                    set(im.info)<={'jfif','jfif_version','jfif_unit','jfif_density','dpi'},
                    'native_save_thumbnail_profile')
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:pixels=im.convert('RGB').tobytes()
    except (OSError,ValueError):raise prior.ProposalError('native_save_thumbnail_encoding') from None
    return manual._sha(pixels)


def material_mask(raw,locations,font):
    root=xml(raw)
    for location in locations:
        target=verify._target_node(root,location);verify._set_text(target,'__TARGET_TEXT__')
        for n in target.iter():
            if n.tag in {verify.A+'rPr',verify.A+'endParaRPr'} and n.get('dirty')=='0':n.attrib.pop('dirty')
            if location=='table:1:1' and n.tag in {verify.A+'rPr',verify.A+'endParaRPr'}:
                for child in list(n):
                    if child.tag in {verify.A+'latin',verify.A+'ea',verify.A+'cs'}:
                        require(child.attrib=={'typeface':font} and not len(child) and
                                not (child.text or '').strip(),'native_save_font_changed')
                        n.remove(child)
    if any(x.startswith('table:') for x in locations):
        for table in root.iter(verify.A+'tbl'):
            for n in table.iter(verify.A+'rPr'):
                if n.get('dirty')=='0':n.attrib.pop('dirty')
        for n in root.iter(verify.OFFICE_TABLE_MODID):
            require(set(n.attrib)=={'val'} and not len(n) and not (n.text or '').strip(),
                    'native_save_table_metadata_payload')
            uint(n.get('val'));n.set('val','__MOD_ID__')
    return guard.canonical(root)


def derive_policy(collection: Path,support: Path,out: Path,*,work_root: Path):
    root=Path(work_root).resolve();f=prior.FrozenTrainProposal(collection,work_root=root)
    support=Path(support).resolve();receipt,rr=manual._json(support/'complete-saved-audit.private.json',root)
    require(manual._sha(rr)==SUPPORT_RECEIPT_SHA and receipt['model_calls']==0 and
            receipt['registered_native_train_admissions']==0 and
            receipt['official_final_admissions']==0,'native_save_train_support_evidence_changed')
    task,tr=manual._json(support/'task.private.json',root)
    require(manual._sha(tr)==prior.TASK_SHA and task['split']=='train_policy_development',
            'native_save_train_support_task_changed')
    snapshots={'before':f.before_path,'primary_positive':f.saved_path}
    role_names={'positive':'fresh-positive-web.pptx','near_miss':'fresh-near-miss-web.pptx',
        'collateral':'fresh-collateral-web.pptx','fresh_reset':'fresh-reset-web.pptx',
        'same_file_restored':'same-file-restored-web.pptx'}
    for role,name in role_names.items():
        p=support/name;raw=manual._private(p,root)
        require(manual._sha(raw)==receipt['roles'][role]['artifact_sha256'],
                'native_save_train_support_artifact_changed')
        snapshots[role]=p
    schema={};identities={};markers={};namespaces=set();modifiers=set()
    for p in snapshots.values():
        _,members=guard.package(p)
        for name,raw in members.items():
            if name.endswith(('.xml','.rels')):namespaces.update(prior.namespace_uris(raw))
        for n in xml(members['docProps/core.xml']):
            if n.tag in {prior.CP+'lastModifiedBy','{http://purl.org/dc/elements/1.1/}creator'} and n.text:
                modifiers.add(n.text)
        if prior.CHANGES not in members:continue
        for n in xml(members[prior.CHANGES]).iter():
            record=schema.setdefault(n.tag,{'attribute_sets':set(),'children':set(),'enum_values':set()})
            record['attribute_sets'].add(tuple(sorted(n.attrib)));record['children'].update(c.tag for c in n)
            if n.get('chg'):record['enum_values'].add(n.get('chg'))
            if n.tag.endswith('}chgData'):
                for k in ('name','providerId','userId'):identities.setdefault(k,set()).add(n.get(k))
                modifiers.add(n.get('name'))
            if n.tag.endswith(('}sldMk','}spMk','}graphicFrameMk')):
                markers.setdefault(n.tag,set()).add(tuple(sorted(n.attrib.items())))
    policy={'schema':SCHEMA,'source_hashes':source_hashes(),'task_sha256':prior.TASK_SHA,
        'source_sha256':prior.SOURCE_SHA,'before_sha256':prior.BEFORE_SHA,
        'primary_collection_sha256':prior.COLLECTION_SHA,'train_support_receipt_sha256':SUPPORT_RECEIPT_SHA,
        'calibration_artifacts':{k:manual._sha(p.read_bytes()) for k,p in snapshots.items()},
        'namespaces':sorted(namespaces),'allowed_last_modifiers':sorted(modifiers),
        'change_schema':{tag:{'attribute_sets':[list(s) for s in sorted(v['attribute_sets'])],
            'children':sorted(v['children']),'enum_values':sorted(v['enum_values'])} for tag,v in schema.items()},
        'change_identity_values':{k:sorted(v) for k,v in identities.items()},
        'change_root_tag':xml(f.observed[prior.CHANGES]).tag,
        'marker_tuples':{k:[list(map(list,s)) for s in sorted(v)] for k,v in markers.items()},
        'thumbnail_pixel_sha256':thumbnail_pixels(f.observed[prior.THUMBNAIL]),
        'max_revision_clients':128,'max_change_nodes':4096,'max_change_xml_bytes':262144,
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'split':'train',
        'prospective_native_proof_completed':False,'generic_office_20_100_qualified':False,
        'registered':False,'model_benchmark_score':None,'official_final_credit':0}
    out=Path(out).absolute()
    require(not out.exists() and out.parent.resolve().is_relative_to(root),'native_save_fresh_policy_path_required')
    digest=manual._write_new(out,manual._canonical(policy))
    return {'status':'train_derived_policy_frozen_before_new_candidates','policy_sha256':digest,
        'calibration_artifact_count':len(snapshots),'model_calls':0,'official_final_credit':0}


class ProspectiveTrainNativeSaveEvaluator:
    def __init__(self,collection: Path,policy_path: Path,*,policy_sha256: str,work_root: Path):
        self.root=Path(work_root).resolve();self.f=prior.FrozenTrainProposal(collection,work_root=self.root)
        self.policy,raw=manual._json(policy_path,self.root);self.policy_sha256=manual._sha(raw)
        require(self.policy_sha256==policy_sha256 and self.policy['schema']==SCHEMA and
            self.policy['split']=='train' and self.policy['task_sha256']==prior.TASK_SHA and
            self.policy['before_sha256']==prior.BEFORE_SHA and self.policy['source_hashes']==source_hashes() and
            self.policy['registered'] is False and self.policy['model_benchmark_score'] is None,
            'native_save_prospective_policy_binding_changed')
        self.ceiling=datetime.now(timezone.utc)+timedelta(days=1)
        self.base_core=xml(self.f.before['docProps/core.xml'])
        self.created=timestamp(self.base_core.find(prior.DC+'created').text)

    def core_signature(self,raw):
        root=xml(raw);require(root.tag==self.base_core.tag and not root.attrib,'native_save_core_root_changed')
        for tag in (prior.CP+'revision',prior.DC+'modified'):
            nodes=root.findall(tag);require(len(nodes)==1 and not len(nodes[0]),'native_save_core_metadata_shape')
            if tag==prior.CP+'revision':uint(nodes[0].text)
            else:timestamp(nodes[0].text,ceiling=self.ceiling,floor=self.created)
            nodes[0].text='__TYPED_METADATA__'
        modifiers=root.findall(prior.CP+'lastModifiedBy')
        require(len(modifiers)<=1,'native_save_core_modifier_duplicate')
        for n in modifiers:
            require(not n.attrib and not len(n) and n.text in self.policy['allowed_last_modifiers'],
                    'native_save_core_modifier_unknown')
            root.remove(n)
        return guard.canonical(root)

    def revision(self,raw):
        root=xml(raw)
        require(root.tag==REV+'revInfo' and not root.attrib and not (root.text or '').strip() and
            len(root)==1 and root[0].tag==REV+'revLst' and not root[0].attrib and
            not (root[0].text or '').strip() and 1<=len(root[0])<=self.policy['max_revision_clients'],
            'native_save_revision_shape')
        clients={}
        for n in root[0]:
            require(n.tag==REV+'client' and set(n.attrib)=={'id','v','dt'} and not len(n) and
                    not (n.text or '').strip() and GUID.fullmatch(n.get('id')),
                    'native_save_revision_client_invalid')
            identity=n.get('id').lower();require(identity not in clients,'native_save_revision_duplicate_client')
            clients[identity]=(uint(n.get('v')),timestamp(n.get('dt'),ceiling=self.ceiling,floor=self.created))
        return clients

    def changes(self,raw,clients):
        require(len(raw)<=self.policy['max_change_xml_bytes'],'native_save_change_log_limit')
        root=xml(raw);nodes=list(root.iter());schema=self.policy['change_schema']
        require(root.tag==self.policy['change_root_tag'] and len(nodes)<=self.policy['max_change_nodes'],
                'native_save_change_log_root_or_limit')
        for n in nodes:
            require(n.tag in schema and sorted(n.attrib) in schema[n.tag]['attribute_sets'] and
                set(c.tag for c in n)<=set(schema[n.tag]['children']) and
                not (n.text or '').strip(),'native_save_change_log_unknown_payload')
            if n.get('chg'):require(n.get('chg') in schema[n.tag]['enum_values'],'native_save_change_enum_unknown')
            if n.tag.endswith('}chgData'):
                client=n.get('clId');require(client.startswith('Web-') and GUID.fullmatch(client[4:]) and
                    client[4:].lower() in clients,'native_save_change_client_unbound')
                for k,values in self.policy['change_identity_values'].items():
                    require(n.get(k) in values,'native_save_change_identity_unknown')
                for k in ('v','actId'):
                    if k in n.attrib:uint(n.get(k))
                if 'dt' in n.attrib:timestamp(n.get('dt'),ceiling=self.ceiling,floor=self.created)
            if n.tag in self.policy['marker_tuples']:
                require([list(x) for x in sorted(n.attrib.items())] in self.policy['marker_tuples'][n.tag],
                        'native_save_marker_not_source_bound')

    def normalize(self,members):
        base=self.f.before;old=self.f.old
        embedded=[n for n in members if n.startswith('ppt/embeddings/')]
        require(len(embedded)==1,'native_save_workbook_bijection')
        new=embedded[0];stem=Path(old).stem
        require(new==old or re.fullmatch(r'ppt/embeddings/'+re.escape(stem)+r'_[1-9][0-9]{0,8}_[A-F0-9]{8}\.xlsx',new),
                'native_save_workbook_part_name_invalid')
        require(members[new]==base[old] and prior.nested_zip(members[new])==prior.nested_zip(base[old]),
                'native_save_workbook_bytes_changed')
        extras={n for n in (prior.CHANGES,prior.THUMBNAIL) if n in members}
        require(set(members)==(set(base)-{old})|{new}|extras,'native_save_unknown_or_missing_part')
        for n,raw in members.items():
            if n.endswith(('.xml','.rels')):
                xml(raw);require(prior.namespace_uris(raw)<=set(self.policy['namespaces']),'native_save_unknown_namespace')
        require(self.core_signature(members['docProps/core.xml'])==self.core_signature(base['docProps/core.xml']),
                'native_save_material_core_property_changed')
        app=xml(members['docProps/app.xml']);original=xml(base['docProps/app.xml'])
        for r in (app,original):
            security=r.findall(prior.EP+'DocSecurity');require(len(security)<=1,'native_save_security_duplicate')
            for n in security:
                require(not n.attrib and not len(n) and n.text=='0','native_save_document_security_changed');r.remove(n)
        require(guard.canonical(app)==guard.canonical(original),'native_save_material_app_property_changed')
        clients=self.revision(members['ppt/revisionInfo.xml']);baseline_clients=self.revision(base['ppt/revisionInfo.xml'])
        require(set(baseline_clients)<=set(clients) and all(clients[k][0]>=v[0] for k,v in baseline_clients.items()),
                'native_save_revision_regression')
        if prior.CHANGES in extras:self.changes(members[prior.CHANGES],clients)
        if prior.THUMBNAIL in extras:
            require(thumbnail_pixels(members[prior.THUMBNAIL])==self.policy['thumbnail_pixel_sha256'],
                    'native_save_thumbnail_material_changed')
        chart='ppt/charts/_rels/chart1.xml.rels'
        before_rel=prior.relation_rows(base[chart]);after_rel=prior.relation_rows(members[chart])
        require(all(re.fullmatch(r'rId[1-9][0-9]{0,5}',r['Id']) for r in after_rel.values()),
                'native_save_relationship_id_untyped')
        require(len(before_rel)==len(after_rel)==1,'native_save_chart_relationship_bijection')
        br=next(iter(before_rel.values()));ar=next(iter(after_rel.values()))
        require(ar=={**br,'Target':'../embeddings/'+Path(new).name},'native_save_chart_relationship_changed')
        added_types=set()
        if prior.THUMBNAIL in extras:added_types.add((prior.CT+'Default',(('ContentType','image/jpeg'),('Extension','jpeg'))))
        if prior.CHANGES in extras:added_types.add((prior.CT+'Override',(('ContentType','application/vnd.ms-powerpoint.changesinfo+xml'),('PartName','/'+prior.CHANGES))))
        require(prior.content_rows(members['[Content_Types].xml'])==prior.content_rows(base['[Content_Types].xml'])|added_types,
                'native_save_content_type_bijection')
        for name,part,kind,renumber in (
            ('_rels/.rels',prior.THUMBNAIL,'http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail',True),
            ('ppt/_rels/presentation.xml.rels',prior.CHANGES,'http://schemas.microsoft.com/office/2016/11/relationships/changesInfo',False)):
            target=part if renumber else 'changesInfos/changesInfo1.xml'
            a=prior.relation_rows(base[name]);b=prior.relation_rows(members[name])
            require(all(re.fullmatch(r'rId[1-9][0-9]{0,5}',r['Id']) for r in b.values()),
                    'native_save_relationship_id_untyped')
            pairs={(r['Type'],r['Target']) for r in a.values()}
            require({(r['Type'],r['Target']) for r in b.values()}==pairs|({(kind,target)} if part in extras else set()),
                    'native_save_metadata_relationship_bijection')
            if not renumber:
                for r in a.values():
                    matches=[q for q in b.values() if (q['Type'],q['Target'])==(r['Type'],r['Target'])]
                    require(matches[0]['Id']==r['Id'] or r['Target']=='revisionInfo.xml','native_save_material_relationship_id')
        for n in set(base)-prior.META-{old}:
            if n in self.f.locations:
                require(material_mask(base[n],self.f.locations[n],self.f.ledger_font)==
                    material_mask(members[n],self.f.locations[n],self.f.ledger_font),'native_save_material_target_style_or_body')
            elif n.endswith(('.xml','.rels')):
                require(guard.canonical(xml(base[n]))==guard.canonical(xml(members[n])),'native_save_material_xml_changed')
            else:require(base[n]==members[n],'native_save_material_binary_changed')
        normalized=copy.copy(members);normalized.pop(new);normalized[old]=base[old]
        for n in prior.META:
            if n in base:normalized[n]=base[n]
            else:normalized.pop(n,None)
        return normalized

    def score(self,candidate: Path):
        candidate=Path(candidate)
        require(not candidate.is_symlink() and not any(x.lower() in
            {'selection','final','official','selection_candidate','final_candidate'} for x in candidate.parts),
            'native_save_train_candidate_required')
        raw=manual._private(candidate,self.root);strict=verify.verify(self.f.before_path,candidate,self.f.oracle)
        result={'schema':'office-ppt-prospective-native-save-train-diagnostic-v1',
            'policy_sha256':self.policy_sha256,'candidate_sha256':manual._sha(raw),
            'raw_strict_score':strict.get('score'),'raw_strict_result_sha256':manual._sha(manual._canonical(strict)),
            'model_benchmark_score':None,'registered':False,'selection_or_final_eligible':False,
            'generic_office_20_100_qualified':False,'official_final_credit':0}
        try:
            _,members=guard.package(candidate);normalized=self.normalize(members)
            with tempfile.TemporaryDirectory(prefix='prospective-native-train-') as tmp:
                p=Path(tmp)/'candidate.pptx'
                with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
                    for n,b in sorted(normalized.items()):z.writestr(n,b)
                score=verify.verify(self.f.before_path,p,self.f.oracle)
            return {**result,'canonical_score':score['score'],'preservation_pass':score['preservation_pass'],
                'target_correct':score['target_correct'],'per_target':score['per_target'],
                'status':'scored_train_diagnostic_only'}
        except (ValueError,guard.ArtifactUnavailable,ET.ParseError,zipfile.BadZipFile) as exc:
            return {**result,'canonical_score':0,'preservation_pass':False,'target_correct':strict.get('target_correct',False),
                'status':'rejected_train_native_save_candidate','error_code':str(exc)}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    freeze=sub.add_parser('freeze');freeze.add_argument('--collection',type=Path,required=True)
    freeze.add_argument('--train-support',type=Path,required=True);freeze.add_argument('--out',type=Path,required=True)
    score=sub.add_parser('score');score.add_argument('--collection',type=Path,required=True)
    score.add_argument('--policy',type=Path,required=True);score.add_argument('--policy-sha256',required=True)
    score.add_argument('--candidate',type=Path,required=True);score.add_argument('--out',type=Path,required=True)
    args=p.parse_args();root=Path.cwd()/'work'
    if args.command=='freeze':
        print(json.dumps(derive_policy(args.collection,args.train_support,args.out,work_root=root),sort_keys=True))
    else:
        evaluator=ProspectiveTrainNativeSaveEvaluator(args.collection,args.policy,
            policy_sha256=args.policy_sha256,work_root=root)
        result=evaluator.score(args.candidate)
        require(args.out.absolute().parent.resolve().is_relative_to(root.resolve()),
                'native_save_private_result_path_required')
        sha=manual._write_new(args.out,manual._canonical(result))
        print(json.dumps({'status':result['status'],'result_sha256':sha,
            'policy_sha256':args.policy_sha256,'raw_strict_score':result['raw_strict_score'],
            'canonical_score':result['canonical_score'],'preservation_pass':result['preservation_pass'],
            'model_benchmark_score':None,'official_final_credit':0},sort_keys=True))


if __name__=='__main__':main()
