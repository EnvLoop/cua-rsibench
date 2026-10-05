import copy
import unittest
import xml.etree.ElementTree as ET

from ppt_wdi_factory import office_revision_verifier_v2 as revision


class RevisionMetadataTests(unittest.TestCase):
    def parts(self):
        return {
            'ppt/_rels/presentation.xml.rels': (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="slide" Target="slides/slide1.xml"/>'
                '<Relationship Id="rId14" Type="' + revision.REL_TYPE + '" Target="revisionInfo.xml"/>'
                '</Relationships>').encode(),
            '[Content_Types].xml': (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Override PartName="/ppt/slides/slide1.xml" ContentType="slide"/>'
                '<Override PartName="/ppt/revisionInfo.xml" ContentType="' + revision.MIME + '"/>'
                '</Types>').encode(),
            revision.PART: (
                '<revInfo xmlns="http://schemas.microsoft.com/office/powerpoint/2015/10/main">'
                '<revLst><client id="{12345678-1234-1234-1234-123456789ABC}" v="1" '
                'dt="2026-10-05T01:14:59.380"/></revLst></revInfo>').encode(),
            'ppt/slides/slide1.xml': b'<slide>actual content</slide>',
            'ppt/charts/chart1.xml': b'<chart>protected data</chart>',
        }

    def test_only_bound_sidecar_removed(self):
        source = self.parts()
        frozen = copy.deepcopy(source)
        result = revision.revision_metadata(source)
        self.assertEqual(source, frozen)
        self.assertNotIn(revision.PART, result)
        for part in ('ppt/slides/slide1.xml', 'ppt/charts/chart1.xml'):
            self.assertEqual(result[part], source[part])
        self.assertEqual(len(ET.fromstring(result['ppt/_rels/presentation.xml.rels'])), 1)
        self.assertEqual(len(ET.fromstring(result['[Content_Types].xml'])), 1)

    def test_absent_sidecar_dangling_link_rejected(self):
        source = self.parts(); del source[revision.PART]
        with self.assertRaises(ValueError): revision.revision_metadata(source)

    def test_arbitrary_revision_content_rejected(self):
        for payload in (b'<payload>hidden slide</payload>',
                        self.parts()[revision.PART].replace(b'<revLst>', b'<revLst>unauthorized'),
                        self.parts()[revision.PART].replace(b'v="1"', b'v="1" secret="x"'),
                        self.parts()[revision.PART].replace(b'2026-10-05', b'2026-99-99')):
            with self.subTest(payload=payload):
                source = self.parts(); source[revision.PART] = payload
                with self.assertRaises(ValueError): revision.revision_metadata(source)

    def test_missing_duplicate_external_or_wrong_binding_rejected(self):
        for replacement in (b'Target="elsewhere.xml"',
                            b'Target="revisionInfo.xml" TargetMode="External"'):
            source = self.parts()
            source['ppt/_rels/presentation.xml.rels'] = source['ppt/_rels/presentation.xml.rels'].replace(
                b'Target="revisionInfo.xml"', replacement)
            with self.assertRaises(ValueError): revision.revision_metadata(source)
        source = self.parts()
        source['[Content_Types].xml'] = source['[Content_Types].xml'].replace(
            revision.MIME.encode(), b'application/unknown')
        with self.assertRaises(ValueError): revision.revision_metadata(source)
        source = self.parts()
        source['ppt/_rels/presentation.xml.rels'] = source['ppt/_rels/presentation.xml.rels'].replace(
            b'Id="rId14"', b'Id="rId1"')
        with self.assertRaises(ValueError): revision.revision_metadata(source)

    def test_no_revision_metadata_preserves_all_bytes(self):
        source = self.parts()
        normalized = revision.revision_metadata(source)
        self.assertEqual(revision.revision_metadata(normalized), normalized)

    def test_revision_counter_is_an_unsigned_integer(self):
        for value in ('0', '3', '4294967295'):
            source = self.parts()
            source[revision.PART] = source[revision.PART].replace(b'v="1"', ('v="' + value + '"').encode())
            self.assertNotIn(revision.PART, revision.revision_metadata(source))
        for value in ('-1', '4294967296', 'not-a-number'):
            source = self.parts()
            source[revision.PART] = source[revision.PART].replace(b'v="1"', ('v="' + value + '"').encode())
            with self.assertRaises(ValueError): revision.revision_metadata(source)


if __name__ == '__main__':
    unittest.main()
