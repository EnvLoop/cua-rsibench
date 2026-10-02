"""Portable typed-metadata guards; actual corpus audit is separate."""
from __future__ import annotations
from datetime import datetime,timezone
import io
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from tools import office_ppt_prospective_native_save_v1 as native
from tools import ppt_native_train_collection_proposal_v1 as prior


class ProspectiveNativeSaveGuards(unittest.TestCase):
    def test_unsigned_counter_boundary_and_payload_rejection(self):
        self.assertEqual(native.uint('0'),0);self.assertEqual(native.uint('4294967295'),2**32-1)
        for bad in ('-1','4294967296','01','1 payload',' 1','1.0','1e1',None):
            with self.subTest(bad=bad),self.assertRaises(prior.ProposalError):native.uint(bad)

    def test_timestamp_is_calendar_checked_and_bounded_by_document_and_run(self):
        floor=datetime(2020,1,1,tzinfo=timezone.utc);ceiling=datetime(2027,1,1,tzinfo=timezone.utc)
        self.assertEqual(native.timestamp('2026-09-30T12:00:00.123',floor=floor,ceiling=ceiling).year,2026)
        for bad in ('2026-02-30T12:00:00Z','2019-01-01T12:00:00Z','2030-01-01T12:00:00Z',
                    '2026-09-30T12:00:00Z payload','2026-09-30T12:00:60Z','2026-09-30T12:00:00+08:00'):
            with self.subTest(bad=bad),self.assertRaises(prior.ProposalError):
                native.timestamp(bad,floor=floor,ceiling=ceiling)

    def jpeg(self):
        stream=io.BytesIO();Image.new('RGB',(256,144),'white').save(stream,'JPEG',dpi=(96,96))
        return stream.getvalue()

    def test_thumbnail_allows_typed_density_repack_with_identical_pixels(self):
        original=self.jpeg();changed=bytearray(original);pos=changed.index(b'\xff\xe0')+4
        changed[pos+8:pos+10]=(72).to_bytes(2,'big');changed[pos+10:pos+12]=(72).to_bytes(2,'big')
        self.assertNotEqual(original,bytes(changed))
        self.assertEqual(native.thumbnail_pixels(original),native.thumbnail_pixels(bytes(changed)))

    def test_thumbnail_rejects_comment_exif_and_trailing_payload(self):
        raw=self.jpeg()
        for bad in (raw[:2]+b'\xff\xfe\x00\x09payload'+raw[2:],
                    raw[:2]+b'\xff\xe1\x00\x09payload'+raw[2:],raw+b'payload'):
            with self.assertRaises(prior.ProposalError):native.thumbnail_pixels(bad)

    def test_qname_semantics_and_xml_tail_payload_stay_visible(self):
        a=b'<r xmlns:d="urn:date" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="d:T"/>'
        b=a.replace(b'urn:date',b'urn:other')
        self.assertNotEqual(native.guard.canonical(native.xml(a)),native.guard.canonical(native.xml(b)))
        with self.assertRaises(prior.ProposalError):native.xml(b'<root><child/>payload</root>')

    def test_metadata_only_candidate_final_paths_are_refused_before_read(self):
        e=native.ProspectiveTrainNativeSaveEvaluator.__new__(native.ProspectiveTrainNativeSaveEvaluator)
        for path in ('work/final/actor.pptx','work/selection/actor.pptx','work/official/actor.pptx'):
            with self.assertRaisesRegex(prior.ProposalError,'train_candidate_required'):e.score(Path(path))


if __name__=='__main__':unittest.main()
