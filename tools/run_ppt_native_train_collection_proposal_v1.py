"""Replay one frozen private TRAIN proposal and adversarial saved controls."""
from __future__ import annotations
import argparse
import copy
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from ppt_wdi_factory import verify
from tools import office_single_account_train_pilot_v1 as manual
from tools.ppt_native_train_collection_proposal_v1 import (
    CHANGES, CT, REL, THUMBNAIL, FrozenTrainProposal, strict_xml,
    serialize_preserving_bindings,
)


def write_package(path: Path, members: dict, *, compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path,'w',compression) as z:
        for name,raw in sorted(members.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,9,30,0,0,0))
            info.compress_type=compression
            info.external_attr=0o600 << 16
            z.writestr(info,raw)
    path.chmod(0o600)


def mutate_xml(members, part, mutation):
    root=strict_xml(members[part])
    mutation(root)
    members[part]=ET.tostring(root,encoding='utf-8',xml_declaration=True)


def adversarial_members(proposal: FrozenTrainProposal) -> dict[str,dict]:
    original=proposal.observed
    variants={}
    def add(name,mutation):
        m=copy.copy(original)
        mutation(m)
        assert m != original, name+' did not change the candidate'
        variants[name]=m
    def xml(name,part,mutation):
        add(name,lambda m:mutate_xml(m,part,mutation))
    for key,target in proposal.oracle['targets'].items():
        xml('wrong_target_'+key,target['part'],lambda root,t=target:verify._set_text(
            verify._target_node(root,t['location']),'incorrect synthetic control'))
    xml('collateral_body','ppt/slides/slide3.xml',lambda root:verify._set_text(
        verify._shape(root,'chart_unit'),'incorrect collateral'))
    xml('source_visible_value','ppt/slides/slide2.xml',lambda root:setattr(next(root.iter(verify.A+'t')),'text','incorrect source'))
    target=proposal.oracle['targets']['summary']
    def target_run(root):
        return next(verify._target_node(root,target['location']).iter(verify.A+'rPr'))
    xml('target_font_size',target['part'],lambda r:target_run(r).set('sz','9900'))
    xml('target_bold',target['part'],lambda r:target_run(r).set('b','0'))
    xml('target_color',target['part'],lambda r:next(target_run(r).iter(verify.A+'srgbClr')).set('val','FFFFFF'))
    xml('target_body_inset',target['part'],lambda r:next(verify._target_node(r,target['location']).iter(verify.A+'bodyPr')).set('lIns','123456'))
    xml('target_geometry',target['part'],lambda r:next(verify._target_node(r,target['location']).iter(verify.A+'off')).set('x','1'))
    ledger=proposal.oracle['targets']['ledger']
    xml('ledger_font',ledger['part'],lambda r:next(verify._target_node(r,ledger['location']).iter(verify.A+'latin')).set('typeface','Times New Roman'))
    xml('table_collateral_color',ledger['part'],lambda r:next(r.iter(verify.A+'srgbClr')).set('val','ABCDEF'))
    xml('table_border',ledger['part'],lambda r:ET.SubElement(
        verify._target_node(r,ledger['location']).find(verify.A+'tcPr'),verify.A+'lnL',{'w':'999'}))
    xml('layout','ppt/slideLayouts/slideLayout1.xml',lambda r:r.set('unknown','payload'))
    xml('master_style','ppt/slideMasters/slideMaster1.xml',lambda r:r.set('unknown','payload'))
    xml('theme_font','ppt/theme/theme1.xml',lambda r:next(r.iter(verify.A+'latin')).set('typeface','Courier New'))
    xml('chart_cache','ppt/charts/chart1.xml',lambda r:setattr(next(r.iter(verify.C+'v')),'text','999'))
    xml('chart_unknown_attribute','ppt/charts/chart1.xml',lambda r:r.set('extra','payload'))
    def nested(m):
        with zipfile.ZipFile(io.BytesIO(m[proposal.new])) as z:
            inner={n:z.read(n) for n in z.namelist()}
        part=next(n for n in inner if n.startswith('xl/worksheets/'))
        inner[part]=inner[part].replace(b'</worksheet>',b'<unknown>payload</unknown></worksheet>')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            for n,raw in sorted(inner.items()):
                info=zipfile.ZipInfo(n,date_time=(2026,9,30,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o600 << 16
                z.writestr(info,raw)
        m[proposal.new]=stream.getvalue()
    add('embedded_workbook_data',nested)
    add('embedded_original_alias',lambda m:m.update({proposal.old:m[proposal.new]}))
    add('embedded_extra_alias',lambda m:m.update({'ppt/embeddings/extra.xlsx':m[proposal.new]}))
    add('embedded_missing',lambda m:m.pop(proposal.new))
    xml('chart_relationship_wrong','ppt/charts/_rels/chart1.xml.rels',lambda r:r[0].set('Target','../embeddings/wrong.xlsx'))
    xml('chart_relationship_duplicate_id','ppt/charts/_rels/chart1.xml.rels',lambda r:r.append(copy.deepcopy(r[0])))
    xml('chart_relationship_external','ppt/charts/_rels/chart1.xml.rels',lambda r:r[0].set('TargetMode','External'))
    xml('root_relationship_alias','_rels/.rels',lambda r:r.append(copy.deepcopy(r[0])))
    xml('content_type_duplicate','[Content_Types].xml',lambda r:r.append(copy.deepcopy(r[0])))
    xml('content_type_unknown','[Content_Types].xml',lambda r:r[0].set('ContentType','application/x-unapproved'))
    xml('changes_unknown_node',CHANGES,lambda r:ET.SubElement(r, r.tag.rsplit('}',1)[0]+'}unknown'))
    xml('changes_unknown_attribute',CHANGES,lambda r:r.set('id','payload'))
    xml('changes_extra_body',CHANGES,lambda r:setattr(r,'text','payload'))
    xml('revision_unknown_node','ppt/revisionInfo.xml',lambda r:ET.SubElement(r,'unknown'))
    xml('revision_unknown_attribute','ppt/revisionInfo.xml',lambda r:r.set('payload','1'))
    xml('core_extra_property','docProps/core.xml',lambda r:ET.SubElement(r,'unknown'))
    xml('app_extra_property','docProps/app.xml',lambda r:ET.SubElement(r,'unknown'))
    add('unused_namespace_payload',lambda m:m.update({CHANGES:m[CHANGES].replace(
        b'xmlns:',b'xmlns:unapproved="urn:unapproved-hidden-payload" xmlns:',1)}))
    def qname_rebinding(m):
        raw=m['docProps/core.xml']
        m['docProps/core.xml']=raw.replace(b'xmlns:dcterms="http://purl.org/dc/terms/"',
            b'xmlns:dcterms="http://purl.org/dc/elements/1.1/" xmlns:dtalias="http://purl.org/dc/terms/"').replace(
            b'<dcterms:',b'<dtalias:').replace(b'</dcterms:',b'</dtalias:')
    add('qname_namespace_rebinding',qname_rebinding)
    add('qname_unbound_prefix',lambda m:m.update({'docProps/core.xml':m['docProps/core.xml'].replace(
        b'xsi:type="dcterms:W3CDTF"',b'xsi:type="unbound:W3CDTF"')}))
    xml('notes_body','ppt/notesSlides/notesSlide1.xml',lambda r:r.set('unknown','payload'))
    add('thumbnail_binary',lambda m:m.update({THUMBNAIL:m[THUMBNAIL][:-2]+b'X'+m[THUMBNAIL][-1:]}))
    add('unknown_binary',lambda m:m.update({'ppt/media/unknown.bin':b'payload'}))
    add('unknown_xml',lambda m:m.update({'ppt/unknown.xml':b'<unknown/>'}))
    for name,payload in (('xml_comment',b'<!-- hidden -->'),('xml_pi',b'<?hidden payload?>'),('xml_dtd',b'<!DOCTYPE x>')):
        variants[name]=copy.copy(original)
        variants[name][CHANGES]=payload+original[CHANGES].replace(b'<?xml version="1.0" encoding="utf-8"?>',b'').replace(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',b'')
    return variants


def run(collection: Path, out: Path, *, work_root: Path) -> dict:
    proposal=FrozenTrainProposal(collection,work_root=work_root)
    manual._require(not out.exists() and not out.is_symlink() and
                    out.parent.resolve().is_relative_to(work_root.resolve()), 'fresh_private_proposal_output_required')
    out.mkdir(mode=0o700)
    controls={}
    controls['observed_positive']=proposal.score(proposal.saved_path)
    controls['before']=proposal.score(proposal.before_path)
    controls['reset']=proposal.score(collection/'downloads/reset-1.pptx')
    controls['raw_source']=proposal.score(proposal.source)
    assert controls['observed_positive']['score']==1 and all(controls[k]['score']==0 for k in ('before','reset','raw_source'))
    adverse=adversarial_members(proposal)
    for name,members in adverse.items():
        path=out/(name+'.pptx')
        write_package(path,members)
        controls[name]=proposal.score(path)
        assert controls[name]['score']==0, name+' incorrectly passed'
    for name,compression in (('equivalent_outer_repack',zipfile.ZIP_STORED),('equivalent_xml_attributes',zipfile.ZIP_DEFLATED)):
        members=copy.copy(proposal.observed)
        if name=='equivalent_xml_attributes':
            for part in members:
                if part.endswith(('.xml','.rels')):
                    def reverse_attributes(root):
                        for node in root.iter():node.attrib=dict(reversed(list(node.attrib.items())))
                    members[part]=serialize_preserving_bindings(members[part],reverse_attributes)
        path=out/(name+'.pptx')
        write_package(path,members,compression=compression)
        controls[name]=proposal.score(path)
        assert controls[name]['score']==1, name+' incorrectly failed'
    receipt={'schema':'ppt-native-one-collection-proposal-audit-private-v1','controls':controls,
             'source_semantics':proposal.source_check,'historical_raw_score':proposal.raw_score,
             'rejected_adversarial_count':len(adverse),'equivalent_controls_passed':2,
             'proposal_only':True,'registered':False,'model_calls':0,'official_final_credit':0}
    digest=manual._write_new(out/'audit.private.json',manual._canonical(receipt))
    return {'schema':'ppt-native-one-collection-proposal-audit-public-v1','private_audit_sha256':digest,
            'observed_positive_proposal_score':1,'historical_raw_score':0,
            'rejected_adversarial_count':len(adverse),'equivalent_controls_passed':2,
            'source_slide_count':7,'chart_cache_count':26,'proposal_only':True,
            'registered':False,'model_calls':0,'official_final_credit':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.collection,args.out,work_root=Path.cwd()/'work'),sort_keys=True))


if __name__=='__main__':
    main()
