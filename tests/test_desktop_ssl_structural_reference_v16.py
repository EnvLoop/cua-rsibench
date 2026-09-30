from copy import deepcopy
import unittest
from tools.audit_desktop_ssl_archive_evidence_v16 import canonical_members


class StructuralTests(unittest.TestCase):
    def fixture(self):
        return {'members': [{'name': './root.pem', 'type': '0', 'mode': 420, 'uid': 0, 'gid': 0, 'size': 10,
                'linkname': '', 'pax_header_names': [], 'is_regular_file': True, 'payload_sha256': 'a' * 64,
                'contains_private_key_pem': False, 'certificate_pem_blocks': 1, 'mtime': 100}]}

    def test_only_declared_timestamp_variation_is_ignored(self):
        expected = self.fixture(); changed = deepcopy(expected); changed['members'][0]['mtime'] = 200
        self.assertEqual(canonical_members(expected), canonical_members(changed))

    def test_payload_structure_owner_mode_and_key_changes_are_not_ignored(self):
        expected = self.fixture()
        for field, value in [('payload_sha256', 'b' * 64), ('mode', 493), ('uid', 1), ('type', '1'),
                             ('linkname', '../other'), ('size', 11), ('contains_private_key_pem', True), ('pax_header_names', ['unexpected'])]:
            changed = deepcopy(expected); changed['members'][0][field] = value
            self.assertNotEqual(canonical_members(expected), canonical_members(changed), field)

    def test_extra_or_duplicate_member_does_not_match(self):
        expected = self.fixture(); changed = deepcopy(expected); changed['members'].append(deepcopy(changed['members'][0]))
        with self.assertRaises(ValueError):canonical_members(changed)
        changed['members'][1]['name'] = './other.pem'
        self.assertNotEqual(canonical_members(expected), canonical_members(changed))


if __name__ == '__main__':unittest.main()
