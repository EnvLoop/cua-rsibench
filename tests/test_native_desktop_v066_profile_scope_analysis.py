"""The exploratory scope drops only document/session churn."""

from __future__ import annotations

import unittest

from native_desktop_factory import v066_profile_scope_analysis as scope
from native_desktop_factory.profile_canonical import digest


def registry(*, document="one.xlsx", recovery="recovery_item_1",
             timestamp="123", setting="7", recovery_state="1",
             include_recovery=True):
    recovery_item = (
        '<item oor:path="/org.openoffice.Office.Recovery/RecoveryList">'
        f'<node oor:name="{recovery}">'
        f'<prop oor:name="Title"><value>{document}</value></prop>'
        f'<prop oor:name="DocumentState"><value>{recovery_state}</value></prop>'
        '</node></item>' if include_recovery else "")
    return ('''<?xml version="1.0"?>
<items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Histories/Histories/org.openoffice.Office.Histories:HistoryInfo['PickList']/ItemList"><node oor:name="file:///home/user/'''
            + document + '''"/></item>
<item oor:path="/org.openoffice.Office.Histories/Histories/org.openoffice.Office.Histories:HistoryInfo['PickList']/OrderList"><node oor:name="0"/></item>
''' + recovery_item + '''
<item oor:path="/org.openoffice.Setup/Product"><prop oor:name="LastTimeDonateShown"><value>'''
            + timestamp + '''</value></prop><prop oor:name="LastTimeGetInvolvedShown"><value>'''
            + timestamp + '''</value></prop><prop oor:name="ooSetupLastVersion"><value>'''
            + setting + '''</value></prop></item>
</items>''').encode()


def rows(raw: bytes, *, settings_sha="a" * 64):
    return [{"path": "registrymodifications.xcu", "sha256": digest(raw),
             "bytes": len(raw)},
            {"path": "config/settings.bin", "sha256": settings_sha,
             "bytes": 4}]


class ProfileScopeAnalysisTests(unittest.TestCase):
    def test_document_history_recovery_and_two_timestamps_are_scoped(self):
        first = registry()
        second = registry(document="two.xlsx", recovery="recovery_item_999",
                          timestamp="987")
        self.assertEqual(scope.scoped_profile(rows(first), first),
                         scope.scoped_profile(rows(second), second))

    def test_setting_or_nonregistry_file_change_is_detected(self):
        first = registry()
        changed_setting = registry(setting="8")
        changed_recovery_state = registry(recovery_state="2")
        self.assertNotEqual(scope.scoped_profile(rows(first), first),
                            scope.scoped_profile(rows(changed_setting),
                                                 changed_setting))
        self.assertNotEqual(scope.scoped_profile(rows(first), first),
                            scope.scoped_profile(rows(changed_recovery_state),
                                                 changed_recovery_state))
        self.assertNotEqual(scope.scoped_profile(rows(first), first),
                            scope.scoped_profile(rows(first, settings_sha="b" * 64),
                                                 first))

    def test_missing_scoped_item_or_unbound_registry_fails_closed(self):
        first = registry()
        missing = registry(include_recovery=False)
        with self.assertRaisesRegex(ValueError, "exactly three"):
            scope.scoped_profile(rows(missing), missing)
        with self.assertRaisesRegex(ValueError, "manifest-bound"):
            scope.scoped_profile(rows(first), missing)
