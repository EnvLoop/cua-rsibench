"""Original session constructor and strict URI regressions; no app/runtime."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from gitlab_world import selection_worker_v066 as selection
from gitlab_world import v066_selection_reference_controls_v1 as old
from gitlab_world import v066_selection_reference_controls_v2 as current


class UriTests(unittest.TestCase):
    def setUp(self):
        self.project='bench-selection-unit/portfolio-unit'
        self.relative='/-/blob/main/security/release-policy.md'
        self.base=current.world.runtime.BASE
        self.rows=[]
        self.page=SimpleNamespace(url=self.base+'/'+self.project+self.relative)
        self.session=selection._RealSelectionSession(loop=None,page=self.page,
            task={'task_id':'local','package_sha256':'a'*64},
            original_task={'partition':'selection','project_family':self.project},
            project_path=self.project,baseline_semantic={})
        self.session.guard=SimpleNamespace(store=SimpleNamespace(json=lambda *args:self.rows.append(args)))

    def test_original_session_constructor_reproduces_old_failure_and_new_exact_success(self):
        self.assertEqual(self.session.project_path,'/'+self.project)
        with self.assertRaisesRegex(ValueError,'original_project_uri'):
            old._owned_uri(self.session,self.relative)
        current._owned_uri(self.session,self.relative)
        self.assertEqual(self.rows,[])

    def test_foreign_origin_project_credentials_extra_slash_and_other_source_refuse(self):
        changes=(self.base+'/foreign/project'+self.relative,
                 'https://example.invalid/'+self.project+self.relative,
                 self.base+'//'+self.project+self.relative,
                 self.base+'/'+self.project+'/-/blob/other/security/release-policy.md',
                 self.base.replace('://','://secret-user:secret-password@')+'/'+self.project+self.relative)
        for url in changes:
            self.page.url=url
            with self.subTest(url=url),self.assertRaisesRegex(ValueError,'original_project_uri') as caught:
                current._owned_uri(self.session,self.relative)
            self.assertFalse(caught.exception.uri_diagnostic['observed_uri_normalized_for_acceptance'])
        self.assertEqual(len(self.rows),5)
        self.assertNotIn('secret-password',str(self.rows))

    def test_noncanonical_session_path_and_task_project_mismatch_refuse(self):
        for value in (self.project,'//'+self.project,'/'+self.project+'/',
                      '/bench/../project','/foreign/project'):
            self.session.project_path=value
            with self.subTest(path=value),self.assertRaises(ValueError):
                current._owned_uri(self.session,self.relative)

    def test_unsupported_relative_or_changed_issue_path_refuse(self):
        for relative in ('/-/blob/main/other.md','//-/blob/main/security/release-policy.md',
                         '/-/issues/01','/-/issues/1?other=1','/-/issues/../1'):
            with self.subTest(relative=relative),self.assertRaises(ValueError):
                current._owned_uri(self.session,relative)
        self.page.url=self.base+'/'+self.project+'/-/issues/2'
        with self.assertRaises(ValueError):current._owned_uri(self.session,'/-/issues/1')
        current._owned_uri(self.session,'/-/issues/2')

    def test_diagnostic_failure_does_not_override_original_refusal(self):
        self.page.url=self.base+'/foreign/project'+self.relative
        self.session.guard.store.json=lambda *a:(_ for _ in ()).throw(OSError('fixture disk failure'))
        with self.assertRaisesRegex(ValueError,'original_project_uri') as caught:
            current._owned_uri(self.session,self.relative)
        self.assertEqual(caught.exception.uri_diagnostic_capture_error,'OSError')

    def test_consumed_v1_native146_recipes_and_function_defaults_unchanged(self):
        self.assertEqual(sha256(Path(old.__file__).read_bytes()).hexdigest(),current.PARENT_SHA)
        self.assertEqual(current.models.public_binding()['binding_sha256'],
                         '07c1520799c160d4394f9f943601a83f18da825f0ce87b2faa776c66878608be')
        self.assertEqual(current.workflow.__code__.co_code,old.workflow.__code__.co_code)
        self.assertEqual(current._readable.__kwdefaults__,old._readable.__kwdefaults__)
        self.assertEqual(current.run.__kwdefaults__,old.run.__kwdefaults__)
        self.assertNotEqual(current.source_binding()['binding_sha256'],old.source_binding()['binding_sha256'])


if __name__=='__main__':unittest.main()
