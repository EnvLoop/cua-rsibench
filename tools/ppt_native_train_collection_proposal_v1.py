"""One frozen TRAIN collection proposal; not a replacement PPT verifier.

Calibration is bound to exact private evidence. Candidate target text remains
independently scored. All other candidate data must match the observed native
profile, including full embedded ZIP bytes and the observed thumbnail. Only a
temporary evaluator copy is canonicalized. No registration or model credit.
"""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from ppt_wdi_factory import verify
from tools import office_single_account_train_pilot_v1 as manual
from tools import pptx_title_size_guard as guard
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal

COLLECTION_SHA = 'b3a6c0346450c096cdfbc66e548ed3b1767c00f1beda3ec82992c15fb2879d93'
BEFORE_SHA = '04565296c07bf324947e11576f4fb1a7f8d7f88361c0057e2cab6d0295a36aa4'
SAVED_SHA = '84e8d039d08a45c9a5497f212359192dab58f6c23f07992822c351192b494a3c'
SOURCE_SHA = 'bff494c39c7424762a11e4afd5a8a5f91962ab7f02e197f33b8787a7f25782fe'
TASK_SHA = '776cd3dc18917deadf0511f443d7d76c49aa5de0b33e3669935ca6c7959245bf'
CORE_VERIFIER_SHA = '2aef4513690984e965f59f7bb994aa3ba3ef3fbd342da566a10d0fb7a5e8fcc9'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
CP = '{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}'
DC = '{http://purl.org/dc/terms/}'
EP = '{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}'
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
XSI = '{http://www.w3.org/2001/XMLSchema-instance}'
CHANGES = 'ppt/changesInfos/changesInfo1.xml'
THUMBNAIL = 'docProps/thumbnail.jpeg'
META = frozenset({'[Content_Types].xml', '_rels/.rels', 'docProps/app.xml',
                 'docProps/core.xml', 'ppt/_rels/presentation.xml.rels',
                 'ppt/revisionInfo.xml', CHANGES, THUMBNAIL,
                 'ppt/charts/_rels/chart1.xml.rels'})


class ProposalError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ProposalError(code)


def strict_xml(raw: bytes) -> ET.Element:
    # ET normally discards comments/PIs. Reject them and DTDs rather than
    # accidentally admitting hidden payloads through canonical comparison.
    require(not re.search(br'<!DOCTYPE|<!ENTITY|<!--|<\?(?!xml(?:\s|\?))',
                          raw, re.IGNORECASE), 'proposal_extra_xml_payload')
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        raise ProposalError('proposal_invalid_xml') from None


def canon(raw: bytes) -> str:
    return guard.canonical(semantic_xml(raw))


def semantic_xml(raw: bytes) -> ET.Element:
    """Keep QName/prefix-list meaning before ElementTree drops declarations.

    Expanded element/attribute names alone do not protect xsi:type or markup
    compatibility attribute values. Rebinding an existing prefix must change
    this comparison; an unbound QName is never an equivalent serialization.
    """
    strict_xml(raw)
    pending=[];stack=[];root=None
    qnames={XSI+'type',MC+'ProcessContent',MC+'PreserveElements',MC+'PreserveAttributes'}
    prefixes={MC+'Ignorable',MC+'MustUnderstand'}
    for event,item in ET.iterparse(io.BytesIO(raw),events=('start-ns','start','end')):
        if event=='start-ns':
            pending.append(item)
        elif event=='start':
            bindings=dict(stack[-1]) if stack else {'xml':'http://www.w3.org/XML/1998/namespace'}
            bindings.update(pending);pending=[];stack.append(bindings)
            if root is None:root=item
            for key,value in list(item.attrib.items()):
                prefix_list=key in prefixes or (item.tag==MC+'Choice' and key=='Requires')
                if key not in qnames and not prefix_list:continue
                tokens=value.split();require(tokens,'proposal_empty_qname_value')
                if key==XSI+'type':require(len(tokens)==1,'proposal_invalid_qname_value')
                normalized=[]
                for token in tokens:
                    if prefix_list:
                        require(':' not in token and token in bindings,'proposal_unbound_namespace_prefix')
                        normalized.append('{'+bindings[token]+'}')
                    else:
                        parts=token.split(':')
                        require(len(parts) in (1,2) and all(parts),'proposal_invalid_qname_value')
                        if len(parts)==2:
                            require(parts[0] in bindings,'proposal_unbound_qname_prefix')
                            normalized.append('{'+bindings[parts[0]]+'}'+parts[1])
                        else:
                            normalized.append('{'+bindings.get('','')+'}'+parts[0])
                item.set(key,' '.join(normalized))
        else:
            stack.pop()
    require(root is not None,'proposal_invalid_xml')
    return root


def serialize_preserving_bindings(raw: bytes, mutation=None) -> bytes:
    """Create an equivalent control without dropping QName-only namespaces."""
    root=semantic_xml(raw)
    names={prefix for _event,(prefix,_uri) in ET.iterparse(
        io.BytesIO(ET.tostring(root)),events=('start-ns',))}
    bindings={}
    aware={XSI+'type',MC+'ProcessContent',MC+'PreserveElements',MC+'PreserveAttributes',MC+'Ignorable',MC+'MustUnderstand'}
    for node in root.iter():
        for key,value in list(node.attrib.items()):
            prefix_list=key in {MC+'Ignorable',MC+'MustUnderstand'} or (node.tag==MC+'Choice' and key=='Requires')
            if key not in aware and not prefix_list:continue
            tokens=re.findall(r'\{([^}]*)\}([^\s]*)',value)
            require(tokens,'proposal_control_serializer_invalid_qname')
            rewritten=[]
            for uri,local in tokens:
                if not uri:
                    rewritten.append(local);continue
                if uri not in bindings:
                    prefix='qbound'+str(len(bindings))
                    while prefix in names:prefix+='x'
                    names.add(prefix);bindings[uri]=prefix
                rewritten.append(bindings[uri]+(':'+local if not prefix_list else ''))
            node.set(key,' '.join(rewritten))
    if mutation is not None:mutation(root)
    for uri,prefix in bindings.items():root.set('xmlns:'+prefix,uri)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def namespace_uris(raw: bytes) -> set[str]:
    strict_xml(raw)
    return {uri for _event,(_prefix,uri) in ET.iterparse(io.BytesIO(raw),events=('start-ns',))}


def relation_rows(raw: bytes) -> dict[str, dict[str, str]]:
    root = strict_xml(raw)
    require(root.tag == REL+'Relationships' and not root.attrib and
            not (root.text or '').strip(), 'proposal_relationship_root')
    rows = {}
    for node in root:
        require(node.tag == REL+'Relationship' and
                set(node.attrib) == {'Id', 'Type', 'Target'} and
                not len(node) and not (node.text or '').strip() and
                not (node.tail or '').strip() and node.get('Id') not in rows,
                'proposal_relationship_alias_or_unknown')
        rows[node.get('Id')] = dict(node.attrib)
    require(len({(r['Type'], r['Target']) for r in rows.values()}) == len(rows),
            'proposal_relationship_conflicting_alias')
    return rows


def content_rows(raw: bytes) -> set[tuple]:
    root = strict_xml(raw)
    require(root.tag == CT+'Types' and not root.attrib and
            not (root.text or '').strip(), 'proposal_content_types_root')
    rows = set()
    identities = set()
    for node in root:
        attr = {'Extension', 'ContentType'} if node.tag == CT+'Default' else {'PartName', 'ContentType'}
        require(node.tag in {CT+'Default', CT+'Override'} and
                set(node.attrib) == attr and not len(node) and
                not (node.text or '').strip() and not (node.tail or '').strip(),
                'proposal_content_type_unknown')
        key = (node.tag, node.get('Extension') or node.get('PartName'))
        require(key not in identities, 'proposal_content_type_alias')
        identities.add(key)
        rows.add((node.tag, tuple(sorted(node.attrib.items()))))
    return rows


def nested_zip(raw: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            require(len(names) == len(set(names)), 'proposal_nested_zip_alias')
            return {name: z.read(name) for name in names}
    except zipfile.BadZipFile:
        raise ProposalError('proposal_embedded_zip_invalid') from None


def text_mask(raw: bytes, locations: list[str], *, editing_equivalence=False,
              ledger_inherited_font: str | None = None) -> str:
    root = semantic_xml(raw)
    for location in locations:
        node = verify._target_node(root, location)
        verify._set_text(node, '__TARGET_TEXT__')
        if editing_equivalence:
            for child in node.iter():
                if child.tag in {verify.A+'rPr', verify.A+'endParaRPr'} and child.get('dirty') == '0':
                    child.attrib.pop('dirty')
                if (location == 'table:1:1' and ledger_inherited_font and
                        child.tag in {verify.A+'rPr', verify.A+'endParaRPr'}):
                    for font in list(child):
                        if font.tag in {verify.A+'latin',verify.A+'ea',verify.A+'cs'}:
                            require(font.attrib == {'typeface':ledger_inherited_font} and
                                    not len(font) and not (font.text or '').strip(),
                                    'proposal_ledger_font_not_inherited_default')
                            child.remove(font)
    if editing_equivalence and any(x.startswith('table:') for x in locations):
        for table in root.iter(verify.A+'tbl'):
            for child in table.iter(verify.A+'rPr'):
                if child.get('dirty') == '0':
                    child.attrib.pop('dirty')
        for node in root.iter(verify.OFFICE_TABLE_MODID):
            require(set(node.attrib) == {'val'} and (node.get('val') or '').isdigit()
                    and not len(node) and not (node.text or '').strip(),
                    'proposal_table_metadata_unknown')
            node.set('val', '__MOD_ID__')
    return guard.canonical(root)


def ledger_font_binding(members: dict[str, bytes]) -> str:
    """Prove the frozen implicit cell default before comparing explicit fonts.

    The existing core target normalization already accepts this serialization.
    This proposal narrows it to one frozen cell, unchanged theme/default style,
    and the exact observed explicit font. It never permits a new candidate font.
    """
    a=verify.A
    theme=strict_xml(members['ppt/theme/theme1.xml'])
    minor=theme.find(a+'themeElements/'+a+'fontScheme/'+a+'minorFont')
    require(minor is not None and all(minor.find(a+k) is not None and
            minor.find(a+k).attrib=={'typeface':'Calibri'} for k in ('latin','ea','cs')),
            'proposal_ledger_theme_font_unknown')
    presentation=strict_xml(members['ppt/presentation.xml'])
    default=presentation.find(verify.P+'defaultTextStyle/'+a+'lvl1pPr/'+a+'defRPr')
    require(default is not None and all(default.find(a+k) is not None and
            default.find(a+k).attrib=={'typeface':token} for k,token in
            (('latin','+mn-lt'),('ea','+mn-ea'),('cs','+mn-cs'))),
            'proposal_ledger_presentation_font_unknown')
    cell=verify._target_node(strict_xml(members['ppt/slides/slide4.xml']),'table:1:1')
    require(not any(n.tag in {a+'latin',a+'ea',a+'cs',a+'defRPr'} for n in cell.iter()) and
            len(cell.find(a+'txBody/'+a+'lstStyle'))==0,
            'proposal_ledger_authored_font_override')
    styles=strict_xml(members['ppt/tableStyles.xml'])
    require(styles.tag==a+'tblStyleLst' and len(styles)==0,
            'proposal_ledger_authored_table_style_override')
    return 'Calibri'


def validate_observed_metadata(before: dict, after: dict, old: str, new: str) -> None:
    old_rel = relation_rows(before['ppt/charts/_rels/chart1.xml.rels'])
    new_rel = relation_rows(after['ppt/charts/_rels/chart1.xml.rels'])
    require(len(old_rel) == len(new_rel) == 1, 'proposal_chart_relationship_not_unique')
    old_row = next(iter(old_rel.values()))
    new_row = next(iter(new_rel.values()))
    require(old_row['Target'] == '../embeddings/'+Path(old).name and
            new_row == {**old_row, 'Target':'../embeddings/'+Path(new).name} and
            old_row['Type'] == 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/package',
            'proposal_workbook_relationship_mapping')
    additions = {
        (CT+'Default', (('ContentType','image/jpeg'),('Extension','jpeg'))),
        (CT+'Override', (('ContentType','application/vnd.ms-powerpoint.changesinfo+xml'),
                        ('PartName','/'+CHANGES))) }
    require(content_rows(after['[Content_Types].xml']) ==
            content_rows(before['[Content_Types].xml']) | additions,
            'proposal_content_type_mapping')
    for name, added_type, added_target, renumber in (
        ('_rels/.rels','http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail', THUMBNAIL, True),
        ('ppt/_rels/presentation.xml.rels','http://schemas.microsoft.com/office/2016/11/relationships/changesInfo','changesInfos/changesInfo1.xml', False)):
        a,b=relation_rows(before[name]),relation_rows(after[name])
        existing={(r['Type'],r['Target']) for r in a.values()}
        require({(r['Type'],r['Target']) for r in b.values()} == existing|{(added_type,added_target)},
                'proposal_metadata_relationship_mapping')
        if not renumber:
            for row in a.values():
                matches=[r for r in b.values() if (r['Type'],r['Target']) == (row['Type'],row['Target'])]
                require(matches[0]['Id'] == row['Id'] or row['Target']=='revisionInfo.xml',
                        'proposal_material_relationship_id_change')
    a,b=strict_xml(before['docProps/app.xml']),strict_xml(after['docProps/app.xml'])
    nodes=list(a.findall(EP+'DocSecurity'))
    require(len(nodes)==1 and not nodes[0].attrib and not len(nodes[0]) and nodes[0].text=='0',
            'proposal_doc_security_nonzero')
    a.remove(nodes[0])
    require(guard.canonical(a)==guard.canonical(b), 'proposal_app_property_unknown')
    a,b=semantic_xml(before['docProps/core.xml']),semantic_xml(after['docProps/core.xml'])
    for root in (a,b):
        for node in list(root):
            if node.tag in {DC+'modified', CP+'revision', CP+'lastModifiedBy'}:
                require(not len(node), 'proposal_core_metadata_nested_payload')
                root.remove(node)
    require(guard.canonical(a)==guard.canonical(b), 'proposal_core_property_unknown')
    # This one-case proposal pins all observed metadata values and structure;
    # schema inspection here additionally rejects unknown node/attribute data.
    p13='{http://schemas.microsoft.com/office/powerpoint/2013/main/command}'
    d13='{http://schemas.microsoft.com/office/drawing/2013/main/command}'
    p15='{http://schemas.microsoft.com/office/powerpoint/2015/10/main}'
    empty={frozenset()}
    changes_schema={p13+k:empty for k in ('chgInfo','docChgLst','docMkLst','docMk','sldMkLst')}
    changes_schema.update({p13+k:{frozenset({'chg'})} for k in ('docChg','sldChg','spChg','graphicFrameChg')})
    changes_schema[p13+'sldMk']={frozenset({'cId','sldId'})}
    change_fields={'clId','name','providerId','userId'}
    for ns in (p13,d13):
        changes_schema[ns+'chgData']={frozenset(change_fields),frozenset(change_fields|{'dt','v'}),
                                     frozenset(change_fields|{'dt','v','actId'})}
    for kind in ('sp','graphicFrame'):
        changes_schema[d13+kind+'MkLst']=empty
        changes_schema[d13+kind+'Mk']={frozenset({'creationId','id'})}
    revision_schema={p15+'revInfo':empty,p15+'revLst':empty,
                     p15+'client':{frozenset({'dt','id','v'})}}
    for name,schema in ((CHANGES,changes_schema),('ppt/revisionInfo.xml',revision_schema)):
        root=strict_xml(after[name])
        for node in root.iter():
            require(not (node.text or '').strip() and not (node.tail or '').strip(),
                    'proposal_edit_metadata_body_payload')
            require(node.tag in schema, 'proposal_edit_metadata_unknown_node')
            require(frozenset(node.attrib) in schema[node.tag], 'proposal_edit_metadata_attribute')


class FrozenTrainProposal:
    """Only the exact frozen collection can calibrate this evaluator."""
    def __init__(self, collection: Path, *, work_root: Path):
        self.root=work_root.resolve()
        self.collection=Path(collection).resolve()
        raw=manual._private(self.collection/'collection-audit.private.json',self.root,2_000_000)
        require(manual._sha(raw)==COLLECTION_SHA, 'proposal_collection_binding_changed')
        receipt=json.loads(raw)
        spec_raw=manual._private(self.collection/'spec.private.json',self.root,2_000_000)
        require(manual._sha(spec_raw)==receipt['spec_sha256'], 'proposal_spec_binding_changed')
        spec=json.loads(spec_raw)
        require(spec['cell_id']=='powerpoint-web' and spec['split']=='train' and
                spec['official_final_credit']==0 and receipt['dedicated_account_assertion'] is False and
                receipt['scope']=='existing_account_dedicated_disposable_folder', 'proposal_train_scope_changed')
        self.source,_=manual._ref(spec['source_ref'],self.root)
        task_path,task_raw=manual._ref(spec['task_ref'],self.root)
        require(manual._sha(task_raw)==TASK_SHA and manual._sha(self.source.read_bytes())==SOURCE_SHA and
                manual._sha(Path(verify.__file__).read_bytes())==CORE_VERIFIER_SHA,
                'proposal_source_or_core_binding_changed')
        self.task=json.loads(task_raw)
        require(manual._ppt_train_profile(self.task,spec['task_id'])=='transfer_wdi_four_target_train',
                'proposal_source_not_four_target_train')
        self.before_path=self.collection/'downloads/before-1.pptx'
        self.saved_path=self.collection/'downloads/saved-1.pptx'
        reset=self.collection/'downloads/reset-1.pptx'
        for path,expected in ((self.before_path,BEFORE_SHA),(self.saved_path,SAVED_SHA),(reset,BEFORE_SHA)):
            require(manual._sha(manual._private(path,self.root,50_000_000))==expected,
                    'proposal_native_hash_binding_changed')
        scorer=manual.OfficeTrainScorer(spec,{'task':task_path,'source':self.source})
        self.source_check=semantic_source_equal(self.source,self.before_path)
        require(self.source_check['slide_count']==7 and
                self.source_check['native_chart_cache_values_checked']==26,
                'proposal_source_semantics_changed')
        scorer.baseline(self.before_path)
        self.oracle=scorer.ppt_oracle
        self.before=guard.package(self.before_path)[1]
        self.observed=guard.package(self.saved_path)[1]
        self.raw_score=verify.verify(self.before_path,self.saved_path,self.oracle)
        require(self.raw_score['score']==0 and self.raw_score['target_correct'] is True and
                len(self.raw_score['unexpected_parts'])==10, 'proposal_historical_failure_changed')
        self.locations={}
        for target in self.oracle['targets'].values():
            require(target['kind']!='legend','proposal_legend_not_admitted')
            self.locations.setdefault(target['part'],[]).append(target['location'])
        old=[n for n in self.before if n.startswith('ppt/embeddings/')]
        new=[n for n in self.observed if n.startswith('ppt/embeddings/')]
        require(len(old)==len(new)==1 and old!=new, 'proposal_workbook_rename_not_bijective')
        self.old,self.new=old[0],new[0]
        require(self.before[self.old]==self.observed[self.new] and
                nested_zip(self.before[self.old])==nested_zip(self.observed[self.new]),
                'proposal_embedded_full_bytes_changed')
        require(set(self.observed)==(set(self.before)-{self.old})|{self.new,CHANGES,THUMBNAIL},
                'proposal_observed_unknown_part')
        validate_observed_metadata(self.before,self.observed,self.old,self.new)
        self.ledger_font=ledger_font_binding(self.before)
        for name in set(self.before)&set(self.observed)-META:
            if name in self.locations:
                require(text_mask(self.before[name],self.locations[name],editing_equivalence=True,
                                  ledger_inherited_font=self.ledger_font)==
                        text_mask(self.observed[name],self.locations[name],editing_equivalence=True,
                                  ledger_inherited_font=self.ledger_font),
                        'proposal_observed_material_style_or_body_change')
            else:
                require(self.before[name]==self.observed[name], 'proposal_observed_material_part_change')
        self.template={n:(text_mask(raw,self.locations[n]) if n in self.locations else
                          canon(raw) if n.endswith(('.xml','.rels')) else raw)
                       for n,raw in self.observed.items()}

    def score(self, candidate: Path) -> dict:
        candidate=Path(candidate)
        require(not candidate.is_symlink(), 'proposal_candidate_symlink')
        candidate=candidate.resolve()
        require(not any(p.lower() in {'selection','selection_candidate','final','final_candidate','official'}
                        for p in candidate.parts), 'proposal_non_train_candidate_path')
        candidate_raw=manual._private(candidate,self.root,50_000_000)
        raw_score=verify.verify(self.before_path,candidate,self.oracle)
        result={'schema':'ppt-native-one-collection-train-proposal-v1','proposal_only':True,
                'collection_sha256':COLLECTION_SHA,'candidate_sha256':manual._sha(candidate_raw),
                'historical_raw_score':self.raw_score['score'],'candidate_raw_score':raw_score.get('score'),
                'scope':'existing_account_dedicated_disposable_folder','dedicated_test_account':False,
                'registered':False,'model_calls':0,'selection_or_final_eligible':False,'official_final_credit':0}
        if candidate_raw==self.before_path.read_bytes():
            return {**result,'score':0,'preservation_pass':True,'target_correct':False,
                    'normalization_applied':False,'target_count':4,'source_slide_count':7,'chart_cache_count':26}
        try:
            _,members=guard.package(candidate)
            require(set(members)==set(self.observed), 'proposal_candidate_unknown_or_missing_part')
            require(members[self.new]==self.before[self.old] and
                    nested_zip(members[self.new])==nested_zip(self.before[self.old]),
                    'proposal_candidate_embedded_full_bytes_changed')
            validate_observed_metadata(self.before,members,self.old,self.new)
            for name,data in members.items():
                if name.endswith(('.xml','.rels')):
                    require(namespace_uris(data) <= namespace_uris(self.observed[name]),
                            'proposal_candidate_unknown_namespace_payload')
                value=(text_mask(data,self.locations[name]) if name in self.locations else
                       canon(data) if name.endswith(('.xml','.rels')) else data)
                require(value==self.template[name], 'proposal_candidate_data_changed')
            normalized=copy.copy(members)
            del normalized[self.new]
            normalized[self.old]=self.before[self.old]
            for name in META:
                if name in self.before:
                    normalized[name]=self.before[name]
                else:
                    normalized.pop(name,None)
            with tempfile.TemporaryDirectory(prefix='ppt-train-proposal-') as directory:
                path=Path(directory)/'candidate.pptx'
                with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                    for name,data in sorted(normalized.items()):
                        z.writestr(name,data)
                scored=verify.verify(self.before_path,path,self.oracle)
            return {**result,'score':scored['score'],'preservation_pass':scored['preservation_pass'],
                    'target_correct':scored['target_correct'],'normalization_applied':True,
                    'per_target':scored['per_target'],'target_count':4,'source_slide_count':7,'chart_cache_count':26}
        except (ProposalError,guard.ArtifactUnavailable,ValueError,ET.ParseError,zipfile.BadZipFile) as exc:
            return {**result,'score':0,'preservation_pass':False,'target_correct':raw_score.get('target_correct',False),
                    'normalization_applied':False,'error':str(exc),'target_count':4}
