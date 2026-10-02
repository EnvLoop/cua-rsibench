"""Replay real TRAIN snapshots and post-freeze synthetic metadata controls."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from tools import office_single_account_train_pilot_v1 as manual
from tools import office_ppt_prospective_native_save_v1 as prospective
from tools import ppt_native_train_collection_proposal_v1 as prior
from tools.run_ppt_native_train_collection_proposal_v1 import adversarial_members,write_package


def mutate(members,part,fn):
    members[part]=prior.serialize_preserving_bindings(members[part],fn)


def added_controls(e):
    original=e.f.observed;positive={};negative={}
    def good(name,fn):
        m=copy.copy(original);fn(m);assert m!=original;positive[name]=m
    def bad(name,fn):
        m=copy.copy(original);fn(m);assert m!=original;negative[name]=m
    def metadata(m):
        raw=prospective.xml(m['ppt/revisionInfo.xml'])
        baseline=e.revision(e.f.before['ppt/revisionInfo.xml'])
        client=next(n for n in raw.iter(prospective.REV+'client') if n.get('id').lower() not in baseline)
        old=client.get('id');new='{11111111-2222-4333-8444-555555555555}'
        now=datetime.fromisoformat(e.policy['created_at_utc']);core_time=now.strftime('%Y-%m-%dT%H:%M:%SZ')
        log_time=now.strftime('%Y-%m-%dT%H:%M:%S.')+'123'
        def revisions(root):
            for n in root.iter(prospective.REV+'client'):
                if n.get('id')==old:n.set('id',new);n.set('v',str(int(n.get('v'))+1));n.set('dt',log_time)
        mutate(m,'ppt/revisionInfo.xml',revisions)
        def changes(root):
            for n in root.iter():
                if n.get('clId')=='Web-'+old:n.set('clId','Web-'+new)
                if n.get('dt'):n.set('dt',log_time)
                if n.get('v'):n.set('v',str(int(n.get('v'))+1))
                if n.get('actId'):n.set('actId',str(int(n.get('actId'))+1))
        mutate(m,prior.CHANGES,changes)
        def core(root):
            root.find(prior.DC+'modified').text=core_time
            revision=root.find(prior.CP+'revision');revision.text=str(int(revision.text)+1)
        mutate(m,'docProps/core.xml',core)
    good('fresh_typed_client_and_times',metadata)
    def rename(m):
        old=e.f.new;new='ppt/embeddings/'+Path(e.f.old).stem+'_103_A1B2C3D4.xlsx'
        m[new]=m.pop(old)
        mutate(m,'ppt/charts/_rels/chart1.xml.rels',lambda root:root[0].set('Target','../embeddings/'+Path(new).name))
    good('fresh_bijective_workbook_name',rename)
    def jfif(m):
        raw=bytearray(m[prior.THUMBNAIL]);pos=raw.index(b'\xff\xe0')+4
        raw[pos+8:pos+10]=(72).to_bytes(2,'big');raw[pos+10:pos+12]=(72).to_bytes(2,'big')
        m[prior.THUMBNAIL]=bytes(raw)
    good('same_thumbnail_pixels_new_jfif_density',jfif)
    def compound(m):metadata(m);rename(m);jfif(m)
    good('combined_fresh_save_metadata',compound)
    def add_client(m):
        def fn(root):
            client=copy.deepcopy(root[0][-1]);client.set('id','{AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE}')
            client.set('v','1');root[0].append(client)
        mutate(m,'ppt/revisionInfo.xml',fn)
    good('additional_typed_native_revision_client',add_client)
    def repeat(m):
        def fn(root):
            listing=root[0];listing.append(copy.deepcopy(next(n for n in listing if n.tag.endswith('}docChg'))))
        mutate(m,prior.CHANGES,fn)
    good('repeated_known_edit_log_records',repeat)
    def reorder(m):
        for name in list(m):
            if name.endswith(('.xml','.rels')):
                def fn(root):
                    for n in root.iter():n.attrib=dict(reversed(list(n.attrib.items())))
                mutate(m,name,fn)
    good('equivalent_xml_namespace_and_attribute_serialization',reorder)
    bad('invalid_calendar_date',lambda m:mutate(m,'docProps/core.xml',lambda r:setattr(r.find(prior.DC+'modified'),'text','2026-02-30T12:00:00Z')))
    bad('far_future_timestamp',lambda m:mutate(m,'docProps/core.xml',lambda r:setattr(r.find(prior.DC+'modified'),'text','2200-01-01T12:00:00Z')))
    bad('timestamp_before_document_creation',lambda m:mutate(m,'docProps/core.xml',lambda r:setattr(r.find(prior.DC+'modified'),'text','2000-01-01T12:00:00Z')))
    bad('counter_overflow',lambda m:mutate(m,'docProps/core.xml',lambda r:setattr(r.find(prior.CP+'revision'),'text','4294967296')))
    bad('unknown_last_modifier',lambda m:mutate(m,'docProps/core.xml',lambda r:ET.SubElement(r,prior.CP+'lastModifiedBy').__setattr__('text','unapproved identity payload')))
    bad('invalid_revision_guid',lambda m:mutate(m,'ppt/revisionInfo.xml',lambda r:r[0][-1].set('id','not-a-guid')))
    bad('duplicate_revision_client',lambda m:mutate(m,'ppt/revisionInfo.xml',lambda r:r[0].append(copy.deepcopy(r[0][0]))))
    baseline_clients=e.revision(e.f.before['ppt/revisionInfo.xml'])
    def regress(m):
        def fn(root):
            node=next(n for n in root[0] if n.get('id').lower() in baseline_clients)
            node.set('v',str(baseline_clients[node.get('id').lower()][0]-1))
        mutate(m,'ppt/revisionInfo.xml',fn)
    bad('revision_counter_regression',regress)
    bad('unknown_change_identity',lambda m:mutate(m,prior.CHANGES,lambda r:next(n for n in r.iter() if n.tag.endswith('}chgData')).set('userId','arbitrary payload')))
    bad('unbound_change_client',lambda m:mutate(m,prior.CHANGES,lambda r:next(n for n in r.iter() if n.tag.endswith('}chgData')).set('clId','Web-{99999999-8888-4777-8666-555555555555}')))
    bad('unknown_change_enum',lambda m:mutate(m,prior.CHANGES,lambda r:next(n for n in r.iter() if n.get('chg')).set('chg','arbitrary payload')))
    bad('marker_not_in_source',lambda m:mutate(m,prior.CHANGES,lambda r:next(n for n in r.iter() if n.tag.endswith('}sldMk')).set('sldId','999')))
    bad('tail_payload',lambda m:mutate(m,'docProps/core.xml',lambda r:setattr(r[0],'tail','hidden body payload')))
    bad('thumbnail_comment_payload',lambda m:m.update({prior.THUMBNAIL:m[prior.THUMBNAIL][:2]+b'\xff\xfe\x00\x09payload'+m[prior.THUMBNAIL][2:]}))
    bad('thumbnail_app_payload',lambda m:m.update({prior.THUMBNAIL:m[prior.THUMBNAIL][:2]+b'\xff\xe1\x00\x09payload'+m[prior.THUMBNAIL][2:]}))
    bad('thumbnail_trailing_payload',lambda m:m.update({prior.THUMBNAIL:m[prior.THUMBNAIL]+b'payload'}))
    bad('workbook_renamed_unknown_family',lambda m:(m.update({'ppt/embeddings/unapproved.xlsx':m[e.f.new]}),m.pop(e.f.new)))
    bad('external_chart_relationship',lambda m:mutate(m,'ppt/charts/_rels/chart1.xml.rels',lambda r:r[0].set('TargetMode','External')))
    bad('metadata_relationship_alias',lambda m:mutate(m,'_rels/.rels',lambda r:r.append(copy.deepcopy(r[0]))))
    bad('root_relationship_id_payload',lambda m:mutate(m,'_rels/.rels',lambda r:r[0].set('Id','untyped payload')))
    bad('unknown_metadata_relationship_id_change',lambda m:mutate(m,'ppt/_rels/presentation.xml.rels',lambda r:next(n for n in r if n.get('Target').startswith('slides/')).set('Id','rId999')))
    bad('unknown_namespace_payload',lambda m:m.update({prior.CHANGES:m[prior.CHANGES].replace(b'xmlns:',b'xmlns:unapproved="urn:unapproved-metadata-payload" xmlns:',1)}))
    return positive,negative


def run(collection,policy_path,policy_sha256,support,out,*,work_root):
    root=Path(work_root).resolve();out=Path(out).absolute()
    manual._require(not out.exists() and not out.is_symlink() and out.parent.resolve().is_relative_to(root),
                    'prospective_train_fresh_audit_output_required');out.mkdir(mode=0o700)
    e=prospective.ProspectiveTrainNativeSaveEvaluator(collection,policy_path,policy_sha256=policy_sha256,work_root=root)
    controls={}
    actual={'before':(e.f.before_path,0,True),'primary_positive':(e.f.saved_path,1,True),
        'older_positive':(support/'fresh-positive-web.pptx',1,True),
        'older_near_miss':(support/'fresh-near-miss-web.pptx',0,True),
        'older_collateral':(support/'fresh-collateral-web.pptx',0,False),
        'older_reset':(support/'fresh-reset-web.pptx',0,True),
        'older_same_file_restored':(support/'same-file-restored-web.pptx',0,True)}
    for role,(p,score,preserve) in actual.items():
        controls[role]=e.score(p);assert controls[role]['canonical_score']==score and controls[role]['preservation_pass']==preserve,role
    positive,additional_negative=added_controls(e)
    negative={**adversarial_members(e.f),**additional_negative}
    for name,members in {**positive,**negative}.items():
        p=out/(name+'.pptx');write_package(p,members)
        controls[name]=e.score(p);wanted=1 if name in positive else 0
        assert controls[name]['canonical_score']==wanted,name+' unexpected canonical score'
    receipt={'schema':'office-ppt-prospective-native-save-train-audit-v1',
        'policy_sha256':policy_sha256,'controls':controls,'real_train_snapshots_checked':len(actual),
        'simulated_fresh_metadata_controls_passed':len(positive),'adversarial_controls_rejected':len(negative),
        'native_student_save_executed':False,'generic_office_20_100_qualified':False,
        'model_calls':0,'provider_calls':0,'model_benchmark_score':None,'official_final_credit':0}
    sha=manual._write_new(out/'audit.private.json',manual._canonical(receipt))
    return {k:receipt[k] for k in receipt if k!='controls'}|{'private_audit_sha256':sha}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collection',type=Path,required=True);p.add_argument('--policy',type=Path,required=True)
    p.add_argument('--policy-sha256',required=True);p.add_argument('--train-support',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    print(json.dumps(run(args.collection,args.policy,args.policy_sha256,args.train_support,args.out,
                         work_root=Path.cwd()/'work'),sort_keys=True))


if __name__=='__main__':main()
