"""Portable guard tests; native artifact corpus is replayed separately."""
from __future__ import annotations
import io
import tempfile
from pathlib import Path
import unittest
import warnings
import xml.etree.ElementTree as ET
import zipfile

from ppt_wdi_factory import verify
from tools.ppt_native_train_collection_proposal_v1 import (
    CT, REL, FrozenTrainProposal, ProposalError, canon, content_rows,
    namespace_uris, nested_zip, relation_rows, strict_xml, text_mask,
    semantic_xml,serialize_preserving_bindings,
)


class NormalizationGuards(unittest.TestCase):
    def test_extra_xml_payloads_fail(self):
        for payload in (b'<!-- secret -->',b'<?secret payload?>',b'<!DOCTYPE x>',b'<!ENTITY x "payload">'):
            with self.subTest(payload=payload), self.assertRaises(ProposalError):
                strict_xml(payload+b'<root/>')

    def test_xml_attribute_order_is_equivalent(self):
        self.assertEqual(canon(b'<root a="1" b="2"/>'),canon(b'<root b="2" a="1"/>'))

    def test_existing_qname_namespace_rebinding_changes_semantics(self):
        old=b'<r xmlns:d="urn:date" xmlns:t="urn:other" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="d:Type"/>'
        changed=old.replace(b'xmlns:d="urn:date"',b'xmlns:d="urn:other" xmlns:alias="urn:date"')
        self.assertNotEqual(canon(old),canon(changed))
        renamed=old.replace(b'xmlns:d=',b'xmlns:alias=').replace(b'xsi:type="d:Type"',b'xsi:type="alias:Type"')
        self.assertEqual(canon(old),canon(renamed))

    def test_unbound_qname_or_markup_compatibility_prefix_refused(self):
        for xml in (b'<r xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="missing:T"/>',
                    b'<r xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="missing"/>'):
            with self.assertRaises(ProposalError):canon(xml)

    def test_prefix_list_and_choice_requires_meaning_is_preserved(self):
        old=b'<mc:Choice xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:p="urn:p" xmlns:q="urn:q" Requires="p"/>'
        rebound=old.replace(b'xmlns:p="urn:p"',b'xmlns:p="urn:q" xmlns:alias="urn:p"')
        self.assertNotEqual(canon(old),canon(rebound))
        self.assertEqual(canon(old),canon(serialize_preserving_bindings(old)))

    def test_equivalent_serializer_does_not_drop_qname_only_binding(self):
        raw=b'<r xmlns:d="urn:date" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="d:Type"/>'
        self.assertEqual(canon(raw),canon(serialize_preserving_bindings(raw)))

    def test_unused_namespace_payload_stays_observable(self):
        self.assertEqual(namespace_uris(b'<root xmlns:e="urn:extra"/>'),{'urn:extra'})

    def relationships(self,children):
        return ('<Relationships xmlns="'+REL[1:-1]+'">'+children+'</Relationships>').encode()

    def test_relationship_duplicate_id_and_alias_fail(self):
        first='<Relationship Id="rId1" Type="package" Target="data.xlsx"/>'
        for second in (first,first.replace('rId1','rId2')):
            with self.subTest(second=second), self.assertRaises(ProposalError):
                relation_rows(self.relationships(first+second))

    def test_external_or_unknown_relationship_attribute_fails(self):
        for attr in ('TargetMode="External"','extra="payload"'):
            with self.subTest(attr=attr), self.assertRaises(ProposalError):
                relation_rows(self.relationships('<Relationship Id="rId1" Type="package" Target="data.xlsx" '+attr+'/>'))

    def test_relationship_body_payload_fails(self):
        with self.assertRaises(ProposalError):
            relation_rows(self.relationships('<Relationship Id="rId1" Type="package" Target="data.xlsx">payload</Relationship>'))

    def test_content_type_alias_and_extra_node_fail(self):
        one='<Default Extension="xlsx" ContentType="sheet"/>'
        for content in (one+one,one+'<unknown/>',one.replace('/>',' extra="payload"/>')):
            with self.subTest(content=content), self.assertRaises(ProposalError):
                content_rows(('<Types xmlns="'+CT[1:-1]+'">'+content+'</Types>').encode())

    def test_full_nested_zip_guard_detects_duplicate_members(self):
        stream=io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(stream,'w') as z:
                z.writestr('xl/workbook.xml',b'<one/>')
                z.writestr('xl/workbook.xml',b'<two/>')
        with self.assertRaises(ProposalError):
            nested_zip(stream.getvalue())

    def slide(self,text='baseline',size='2400',bold='1',x='10'):
        return (f'<p:sld xmlns:p="{verify.P[1:-1]}" xmlns:a="{verify.A[1:-1]}"><p:cSld><p:spTree><p:sp>'
                '<p:nvSpPr><p:cNvPr id="4" name="target__summary"/></p:nvSpPr><p:spPr><a:xfrm>'
                f'<a:off x="{x}" y="10"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:p><a:r>'
                f'<a:rPr sz="{size}" b="{bold}"/><a:t>{text}</a:t></a:r></a:p></p:txBody>'
                '</p:sp></p:spTree></p:cSld></p:sld>').encode()

    def test_target_text_is_independently_masked(self):
        self.assertEqual(text_mask(self.slide('before'),['target__summary']),
                         text_mask(self.slide('after'),['target__summary']))

    def test_target_style_and_layout_are_not_masked(self):
        baseline=text_mask(self.slide(),['target__summary'])
        for change in ({'size':'2500'},{'bold':'0'},{'x':'20'}):
            with self.subTest(change=change):
                self.assertNotEqual(baseline,text_mask(self.slide(**change),['target__summary']))

    def test_one_case_collection_binding_cannot_be_fabricated(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'collection-audit.private.json').write_bytes(b'{}')
            (root/'collection-audit.private.json').chmod(0o600)
            with self.assertRaisesRegex(ProposalError,'collection_binding_changed'):
                FrozenTrainProposal(root,work_root=root)

    def test_candidate_symlink_is_rejected_before_scoring(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/'native.pptx';target.write_bytes(b'fixture')
            link=root/'alias.pptx';link.symlink_to(target)
            proposal=FrozenTrainProposal.__new__(FrozenTrainProposal);proposal.root=root
            with self.assertRaisesRegex(ProposalError,'candidate_symlink'):
                proposal.score(link)

    def test_candidate_final_path_is_rejected_before_scoring(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);final=root/'final';final.mkdir()
            path=final/'native.pptx';path.write_bytes(b'fixture');path.chmod(0o600)
            proposal=FrozenTrainProposal.__new__(FrozenTrainProposal);proposal.root=root
            with self.assertRaisesRegex(ProposalError,'non_train_candidate_path'):
                proposal.score(path)


if __name__=='__main__':
    unittest.main()
