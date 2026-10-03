"""Actual Chromium recipe units; no native qualification or application calls.

Already-saved proof must be affirmative and stable. The local journal from
Ref5 is explicitly unguarded; these tests grant no benchmark credit.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from enterprise_fallback.odoo18 import native_reference_save_v6 as reference
from enterprise_fallback.odoo18.odoo_actor_clock_v1 import ActorClock
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from tests.test_odoo_native_reference_save_v5 import LocalRecipeJournal, form_html, list_html


class SaveV6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 1000})
        self.page.route("**/*", lambda route: route.abort())
        self.journal = LocalRecipeJournal()
        self.journal.trace = [{"fixture_prior_action": 0}, {"fixture_prior_action": 1}]

    def tearDown(self):
        self.page.close()

    def saved_form(self):
        self.page.set_content(form_html())
        self.page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.add('invisible')")

    def saved_list(self):
        self.page.set_content(list_html())
        self.page.evaluate("document.querySelectorAll('.o_list_button_save,.o_list_button_discard').forEach(element=>element.remove())")

    def save(self, **options):
        return reference.save_original_form(self.page, self.journal, "fixture",
            timeout_seconds=options.pop("timeout_seconds", .25),
            poll_seconds=options.pop("poll_seconds", .005),
            stable_seconds=options.pop("stable_seconds", .015), **options)

    def no_input(self):
        self.assertEqual(self.journal.actions, [])
        self.assertEqual(self.journal.trace, [{"fixture_prior_action": 0}, {"fixture_prior_action": 1}])
        self.assertEqual(self.page.evaluate("window.clickCount"), 0)

    def test_current_saved_form_is_positive_stable_proof_without_input(self):
        self.saved_form()
        started = time.monotonic()
        proof = self.save(stable_seconds=.025)
        self.assertGreaterEqual(time.monotonic() - started, .025)
        self.assertEqual(proof["status"], "already_saved_native_indicator")
        self.assertFalse(proof["one_native_save_click"])
        self.assertFalse(proof["gui_input_performed"])
        self.assertTrue(proof["positive_current_saved_indicator_verified"])
        self.assertTrue(proof["visible_save_controls_absent_verified"])
        self.assertTrue(proof["original_post_reload_and_independent_sql_readback_still_required"])
        self.assertEqual((proof["actor_action_count_before"], proof["actor_action_count_after"]), (2, 2))
        self.assertGreaterEqual(len(proof["samples"]), 2)
        self.assertTrue(all(sample["native"]["mode"] == "saved" for sample in proof["samples"]))
        self.no_input()

    def test_current_saved_list_requires_positive_original_list_state(self):
        self.saved_list()
        proof = self.save()
        self.assertEqual(proof["status"], "already_saved_native_indicator")
        self.assertEqual(proof["samples"][-1]["native"]["kind"], "list")
        self.assertEqual(proof["samples"][-1]["native"]["current_visible_list_count"], 1)
        self.assertEqual(proof["samples"][-1]["native"]["save_count"], 0)
        self.assertEqual(proof["samples"][-1]["native"]["discard_count"], 0)
        self.no_input()

    def test_saved_form_missing_invalid_ambiguous_or_unknown_refuses_without_input(self):
        mutations = {
            "no indicator": "document.querySelector('.o_form_status_indicator').remove()",
            "two indicators": "document.body.appendChild(document.querySelector('.o_form_status_indicator').cloneNode(true))",
            "no status buttons": "document.querySelector('.o_form_status_indicator_buttons').remove()",
            "two button wrappers": "document.querySelector('.o_form_status_indicator').appendChild(document.querySelector('.o_form_status_indicator_buttons').cloneNode(true))",
            "invalid warning": "document.querySelector('.o_form_status_indicator').insertAdjacentHTML('beforeend','<span class=\"text-danger\">Invalid fixture form</span>')",
            "CSS hidden without saved class": "document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible');document.querySelector('.o_form_status_indicator_buttons').style.visibility='hidden'",
            "entire indicator hidden": "document.querySelector('.o_form_status_indicator').hidden=true",
        }
        for label, mutation in mutations.items():
            with self.subTest(case=label):
                self.saved_form()
                self.page.evaluate(mutation)
                with self.assertRaises(RuntimeError):
                    self.save()
                self.no_input()

    def test_saved_list_missing_or_ambiguous_original_surface_refuses_without_input(self):
        mutations = {
            "no list view": "document.querySelector('.o_list_view').remove()",
            "hidden list view": "document.querySelector('.o_list_view').hidden=true",
            "two list views": "document.body.appendChild(document.querySelector('.o_list_view').cloneNode(true))",
            "no toolbar": "document.querySelector('.o_list_buttons').remove()",
            "two toolbars": "document.body.appendChild(document.querySelector('.o_list_buttons').cloneNode(true))",
            "one discard persists": "document.querySelector('.o_list_buttons').insertAdjacentHTML('beforeend','<button class=\"o_list_button_discard\">Discard</button>')",
        }
        for label, mutation in mutations.items():
            with self.subTest(case=label):
                self.saved_list()
                self.page.evaluate(mutation)
                with self.assertRaises(RuntimeError):
                    self.save()
                self.no_input()

    def test_saved_indicator_disagreement_with_visible_save_even_disabled_refuses(self):
        for name, disabled in (("Save", False), ("Save manually", False), ("Save", True)):
            with self.subTest(name=name, disabled=disabled):
                self.saved_form()
                self.page.evaluate("({name,disabled})=>{const button=document.createElement('button');button.textContent=name;button.disabled=disabled;document.body.appendChild(button)}", {"name": name, "disabled": disabled})
                with self.assertRaisesRegex(RuntimeError, "disagrees_with_visible_save"):
                    self.save()
                self.no_input()

    def test_dirty_original_form_and_list_keep_exactly_one_commit_click(self):
        for html in (form_html(), list_html()):
            with self.subTest(kind="form" if "status_indicator" in html else "list"):
                self.journal = LocalRecipeJournal()
                self.page.set_content(html)
                proof = self.save()
                self.assertEqual(proof["status"], "saved_native_indicator")
                self.assertTrue(proof["one_native_save_click"])
                self.assertEqual(len(self.journal.actions), 1)
                self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_dirty_form_without_save_and_dirty_timeout_are_never_already_saved(self):
        self.page.set_content(form_html())
        self.page.evaluate("document.querySelector('.o_form_button_save').remove()")
        with self.assertRaises(RuntimeError):
            self.save()
        self.no_input()
        self.page.set_content(form_html(saved_on_click=False))
        with self.assertRaisesRegex(RuntimeError, "dirty_timeout_after_single_click"):
            self.save(timeout_seconds=.04, stable_seconds=.005)
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_saved_to_dirty_instability_refuses_with_no_input(self):
        self.saved_form()
        actual_wait = self.page.wait_for_timeout

        def wait(milliseconds):
            self.page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible')")
            return actual_wait(milliseconds)

        with patch.object(self.page, "wait_for_timeout", side_effect=wait):
            with self.assertRaisesRegex(RuntimeError, "became_dirty_or_unknown"):
                self.save()
        self.no_input()

    def test_current_page_change_during_saved_proof_refuses_without_input(self):
        self.saved_form()
        actual_wait = self.page.wait_for_timeout

        def wait(milliseconds):
            self.page.evaluate("location.hash='different-current-document'")
            return actual_wait(milliseconds)

        with patch.object(self.page, "wait_for_timeout", side_effect=wait):
            with self.assertRaisesRegex(RuntimeError, "current_document_changed"):
                self.save()
        self.no_input()

    def test_original_typed_actor_deadline_prevents_even_initial_read(self):
        self.saved_form()
        started = time.monotonic()
        self.journal.adapter.actor_clock = ActorClock(task_id="local-fixture", package_sha256="a" * 64,
            started=started, clock=lambda: started + 720)
        with patch.object(self.page, "locator", wraps=self.page.locator) as locator:
            with self.assertRaises(ActorDeadlineReached) as caught:
                self.save()
        self.assertTrue(caught.exception.proof.actor_deadline_reached)
        self.assertEqual(locator.call_count, 0)
        self.no_input()

    def test_saved_wait_clock_error_propagates_without_further_reads_or_input(self):
        self.saved_form()
        sentinel = RuntimeError("fixture actor clock ended while waiting")
        actual_wait = self.page.wait_for_timeout
        read_count_at_wait = []
        with patch.object(self.page, "locator", wraps=self.page.locator) as locator:
            def wait(milliseconds):
                read_count_at_wait.append(locator.call_count)
                self.journal.clock.error = sentinel
                return actual_wait(milliseconds)

            with patch.object(self.page, "wait_for_timeout", side_effect=wait):
                with self.assertRaises(RuntimeError) as caught:
                    self.save()
            self.assertEqual(locator.call_count, read_count_at_wait[0])
        self.assertIs(caught.exception, sentinel)
        self.no_input()

    def test_dirty_guard_error_propagates_without_any_commit_retry(self):
        self.page.set_content(form_html())
        sentinel = RuntimeError("fixture native guard rejected")
        self.journal.error = sentinel
        with self.assertRaises(RuntimeError) as caught:
            self.save()
        self.assertIs(caught.exception, sentinel)
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 0)

    def test_saved_branch_rejects_action_count_change_during_read_only_proof(self):
        self.saved_form()
        actual_wait = self.page.wait_for_timeout

        def wait(milliseconds):
            self.journal.trace.append({"unexpected_fixture_action": True})
            return actual_wait(milliseconds)

        with patch.object(self.page, "wait_for_timeout", side_effect=wait):
            with self.assertRaisesRegex(RuntimeError, "already_saved_branch_performed_input"):
                self.save()
        self.assertEqual(self.journal.actions, [])
        self.assertEqual(self.page.evaluate("window.clickCount"), 0)

    def test_frozen_ref5_source_and_test_bytes_are_preserved(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(sha256((root / "enterprise_fallback/odoo18/native_reference_save_v5.py").read_bytes()).hexdigest(),
            "f8f2f9314d1375f6aaba04f3016d30172834dea0728a2da4f8d02b41cec0f053")
        self.assertEqual(sha256((root / "tests/test_odoo_native_reference_save_v5.py").read_bytes()).hexdigest(),
            "494e50357246ba3544bcabeba1909dc7617b8b49dfd17b2ab007680309ce75e9")


if __name__ == "__main__":
    unittest.main()
