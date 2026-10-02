"""Only two named LibreOffice prompt timestamps may be ignored."""

from __future__ import annotations

import unittest

from native_desktop_factory.profile_canonical import canonical_registry


def registry(donate: int, involvement: int, setting: str = "keep") -> bytes:
    return (
        '<?xml version="1.0"?><items>'
        f'<prop oor:name="LastTimeDonateShown" oor:op="fuse"><value>{donate}</value></prop>'
        f'<prop oor:name="LastTimeGetInvolvedShown" oor:op="fuse"><value>{involvement}</value></prop>'
        f'<prop oor:name="RealSetting" oor:op="fuse"><value>{setting}</value></prop>'
        '</items>'
    ).encode()


class ProfileCanonicalTests(unittest.TestCase):
    def test_two_prompt_times_canonicalize_but_real_setting_does_not(self):
        first = canonical_registry(registry(1790473371, 1790473371))
        second = canonical_registry(registry(1790473415, 1790473415))
        self.assertEqual(first, second)
        self.assertNotEqual(first, canonical_registry(registry(1790473415, 1790473415, "changed")))

    def test_missing_or_duplicated_timestamp_fails_closed(self):
        with self.assertRaises(ValueError):
            canonical_registry(b'<?xml version="1.0"?><items/>')
        duplicate = registry(1, 2).replace(b'</items>',
            b'<prop oor:name="LastTimeDonateShown" oor:op="fuse"><value>3</value></prop></items>')
        with self.assertRaises(ValueError):
            canonical_registry(duplicate)


if __name__ == "__main__":
    unittest.main()
