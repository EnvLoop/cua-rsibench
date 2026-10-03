"""Local Chromium recipe tests only; no native qualification or application run.

The fixture journal deliberately uses ordinary locator.click. It tests the
reference's one-click/save-state logic, not Native14 guard admission or scoring.
"""
from __future__ import annotations

from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from enterprise_fallback.odoo18 import native_reference_save_v5 as reference


class LocalRecipeClock:
    def __init__(self):
        self.stages = []
        self.error = None

    def check(self, stage):
        self.stages.append(stage)
        if self.error is not None:
            raise self.error


class LocalRecipeJournal:
    """Explicitly unguarded fixture; never use its output as qualification."""
    def __init__(self):
        self.clock = LocalRecipeClock()
        self.adapter = SimpleNamespace(actor_clock=self.clock)
        self.actions = []
        self.error = None
        self.after_click = None

    def act(self, kind, *, phase, locator=None, **fields):
        self.actions.append((kind, phase, locator, fields))
        if self.error is not None:
            raise self.error
        if kind != "click" or locator is None or fields:
            raise AssertionError("save recipe must issue exactly one locator click")
        locator.click(timeout=1000)
        if self.after_click is not None:
            self.after_click()


def form_html(*, name="Save manually", saved_on_click=True):
    on_click = (
        "document.querySelector('.o_form_status_indicator_buttons').classList.add('invisible')"
        if saved_on_click else "void 0"
    )
    return f"""<!doctype html><html><head><style>
      .invisible {{ visibility: hidden; }}
      .o_form_status_indicator {{ width: 220px; height: 38px; }}
      button {{ width: 100px; height: 30px; }}
      </style></head><body>
      <div class="o_form_status_indicator">
        <div class="o_form_status_indicator_buttons">
          <button class="o_form_button_save" aria-label="{name}"
                  onclick="window.clickCount++;{on_click}">Icon</button>
          <button aria-label="Discard changes">Discard</button>
        </div>
      </div>
      <script>window.clickCount=0;</script>
      </body></html>"""


def list_html():
    return """<!doctype html><html><body>
      <div class="o_list_buttons">
        <button class="o_list_button_save" aria-label="Save"
                onclick="window.clickCount++;document.querySelector('.o_list_button_discard').remove();this.remove()">Save</button>
        <button class="o_list_button_discard" aria-label="Discard changes">Discard</button>
      </div>
      <div class="o_list_view" style="width:900px;height:250px">Local edited record</div>
      <script>window.clickCount=0;</script>
      </body></html>"""


class ReferenceSaveV5Tests(unittest.TestCase):
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
        # All observations are local; a mistaken navigation cannot fetch data.
        self.page.route("**/*", lambda route: route.abort())
        self.journal = LocalRecipeJournal()

    def tearDown(self):
        self.page.close()

    def save(self, **options):
        return reference.save_original_form(
            self.page, self.journal, "fixture",
            timeout_seconds=options.pop("timeout_seconds", .25),
            poll_seconds=options.pop("poll_seconds", .005),
            stable_seconds=options.pop("stable_seconds", .01), **options)

    def assert_no_click(self):
        self.assertEqual(self.journal.actions, [])
        self.assertEqual(self.page.evaluate("window.clickCount"), 0)

    def test_manual_save_is_one_click_and_requires_current_saved_indicator(self):
        self.page.set_content(form_html())
        proof = self.save()
        self.assertEqual(proof["status"], "saved_native_indicator")
        self.assertTrue(proof["one_native_save_click"])
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.journal.actions[0][:2], ("click", "fixture"))
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)
        self.assertTrue(self.page.locator(".o_form_status_indicator_buttons").evaluate(
            "element => element.classList.contains('invisible')"))
        self.assertGreaterEqual(len(self.journal.clock.stages), 3)

    def test_legacy_exact_save_is_still_one_click(self):
        self.page.set_content(form_html(name="Save"))
        self.assertEqual(self.save()["status"], "saved_native_indicator")
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_original_inventory_list_commits_once_and_reads_native_list_state(self):
        self.page.set_content(list_html())
        proof = self.save()
        self.assertEqual(proof["status"], "saved_native_indicator")
        self.assertEqual(proof["selected_name"], "Save")
        self.assertEqual(proof["samples"][-1]["native"]["kind"], "list")
        self.assertEqual(proof["samples"][-1]["native"]["current_visible_list_count"], 1)
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)
        self.assertEqual(self.page.locator(".o_list_button_save,.o_list_button_discard").count(), 0)

    def test_list_missing_duplicate_or_hidden_current_view_fails_before_click(self):
        mutations = {
            "missing view": "document.querySelector('.o_list_view').remove()",
            "hidden view": "document.querySelector('.o_list_view').hidden=true",
            "duplicate visible view": "document.body.appendChild(document.querySelector('.o_list_view').cloneNode(true))",
            "duplicate toolbar": "const duplicate=document.querySelector('.o_list_buttons').cloneNode(false);document.body.appendChild(duplicate)",
        }
        for label, mutation in mutations.items():
            with self.subTest(case=label):
                self.journal = LocalRecipeJournal()
                self.page.set_content(list_html())
                self.page.evaluate(mutation)
                with self.assertRaises(RuntimeError):
                    self.save()
                self.assert_no_click()

    def test_list_commit_requires_both_save_and_discard_removal(self):
        mutations = {
            "one discard remains": "document.querySelector('.o_list_buttons').insertAdjacentHTML('beforeend','<button class=\"o_list_button_discard\">Discard</button>')",
            "hidden controls remain": "document.querySelector('.o_list_buttons').insertAdjacentHTML('beforeend','<button hidden class=\"o_list_button_save\">Save</button><button hidden class=\"o_list_button_discard\">Discard</button>')",
            "current list removed": "document.querySelector('.o_list_view').remove()",
            "toolbar replaced by duplicate": "document.body.appendChild(document.querySelector('.o_list_buttons').cloneNode(true))",
        }
        for label, mutation in mutations.items():
            with self.subTest(case=label):
                self.journal = LocalRecipeJournal()
                self.page.set_content(list_html())
                self.journal.after_click = lambda mutation=mutation: self.page.evaluate(mutation)
                with self.assertRaises(RuntimeError):
                    self.save()
                self.assertEqual(len(self.journal.actions), 1)
                self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_missing_hidden_disabled_and_duplicate_visible_save_fail_before_click(self):
        mutations = {
            "missing": "document.querySelector('.o_form_button_save').remove()",
            "hidden": "document.querySelector('.o_form_button_save').hidden=true",
            "disabled": "document.querySelector('.o_form_button_save').disabled=true",
            "duplicate same name": "document.querySelector('.o_form_status_indicator_buttons').appendChild(document.querySelector('.o_form_button_save').cloneNode(true))",
            "duplicate alternate name": "const duplicate=document.querySelector('.o_form_button_save').cloneNode(true);duplicate.setAttribute('aria-label','Save');document.querySelector('.o_form_status_indicator_buttons').appendChild(duplicate)",
            "inexact name": "document.querySelector('.o_form_button_save').setAttribute('aria-label','Save manually later')",
        }
        for label, mutation in mutations.items():
            with self.subTest(case=label):
                self.journal = LocalRecipeJournal()
                self.page.set_content(form_html())
                self.page.evaluate(mutation)
                with self.assertRaises(RuntimeError):
                    self.save()
                self.assert_no_click()

    def test_dirty_indicator_times_out_after_one_click_without_retry(self):
        self.page.set_content(form_html(saved_on_click=False))
        with self.assertRaises(RuntimeError):
            self.save(timeout_seconds=.04, stable_seconds=.005)
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)
        self.assertFalse(self.page.locator(".o_form_status_indicator_buttons").evaluate(
            "element => element.classList.contains('invisible')"))

    def test_missing_or_ambiguous_current_indicator_is_never_saved_proof(self):
        mutations = {
            "indicator missing": "document.querySelector('.o_form_status_indicator').remove()",
            "duplicate indicator": "document.body.appendChild(document.querySelector('.o_form_status_indicator').cloneNode(true))",
            "buttons missing": "document.querySelector('.o_form_status_indicator_buttons').remove()",
            "duplicate buttons": "document.querySelector('.o_form_status_indicator').appendChild(document.querySelector('.o_form_status_indicator_buttons').cloneNode(true))",
        }
        for label, mutation in mutations.items():
            with self.subTest(case=label):
                self.journal = LocalRecipeJournal()
                self.page.set_content(form_html())
                self.journal.after_click = lambda mutation=mutation: self.page.evaluate(mutation)
                with self.assertRaises(RuntimeError):
                    self.save(timeout_seconds=.04, stable_seconds=.005)
                self.assertEqual(len(self.journal.actions), 1)
                self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_class_and_rendered_visibility_must_agree_on_saved_state(self):
        mutations = {
            "CSS hidden without saved class": "const buttons=document.querySelector('.o_form_status_indicator_buttons');buttons.classList.remove('invisible');buttons.style.visibility='hidden'",
            "saved class still visible": "document.querySelector('.o_form_status_indicator_buttons').style.visibility='visible'",
            "hidden entire indicator": "document.querySelector('.o_form_status_indicator').hidden=true",
            "visible invalid warning": "document.querySelector('.o_form_status_indicator').insertAdjacentHTML('beforeend','<span class=\"text-danger\">Invalid form</span>')",
        }
        for label, mutation in mutations.items():
            with self.subTest(case=label):
                self.journal = LocalRecipeJournal()
                self.page.set_content(form_html())
                self.journal.after_click = lambda mutation=mutation: self.page.evaluate(mutation)
                with self.assertRaises(RuntimeError):
                    self.save(timeout_seconds=.04, stable_seconds=.005)
                self.assertEqual(len(self.journal.actions), 1)
                self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_saved_state_is_observed_for_stability_interval(self):
        self.page.set_content(form_html())
        started = time.monotonic()
        proof = self.save(stable_seconds=.03)
        self.assertGreaterEqual(time.monotonic() - started, .03)
        self.assertEqual(proof["status"], "saved_native_indicator")
        self.assertEqual(len(self.journal.actions), 1)

    def test_transient_saved_indicator_is_not_accepted(self):
        self.page.set_content(form_html())
        self.journal.after_click = lambda: self.page.evaluate(
            "setTimeout(() => document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible'), 15)")
        with self.assertRaises(RuntimeError):
            self.save(timeout_seconds=.12, stable_seconds=.05)
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_changed_current_page_cannot_supply_saved_state_proof(self):
        self.page.set_content(form_html())
        self.journal.after_click = lambda: self.page.evaluate("location.hash='changed-form'")
        with self.assertRaises(RuntimeError):
            self.save()
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)

    def test_actor_deadline_after_click_stops_before_saved_state_read(self):
        self.page.set_content(form_html())
        sentinel = RuntimeError("fixture deadline after click")
        self.journal.after_click = lambda: setattr(self.journal.clock, "error", sentinel)
        with patch.object(self.page, "locator", wraps=self.page.locator) as locator:
            with self.assertRaises(RuntimeError) as caught:
                self.save()
        self.assertIs(caught.exception, sentinel)
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 1)
        # The helper must inspect the dirty indicator before dispatch, then
        # perform no further read after the deadline exception.
        self.assertEqual(sum(call.args == (".o_form_status_indicator",)
                             for call in locator.call_args_list), 1)

    def test_guard_exception_propagates_without_any_post_dispatch_observation(self):
        self.page.set_content(form_html())
        sentinel = RuntimeError("fixture native guard rejected")
        self.journal.error = sentinel
        with patch.object(self.page, "locator", wraps=self.page.locator) as locator:
            with self.assertRaises(RuntimeError) as caught:
                self.save()
        self.assertIs(caught.exception, sentinel)
        self.assertEqual(len(self.journal.actions), 1)
        self.assertEqual(self.page.evaluate("window.clickCount"), 0)
        # One pre-dispatch dirty read is expected; guard rejection propagates
        # without a subsequent saved-state read or another action.
        self.assertEqual(sum(call.args == (".o_form_status_indicator",)
                             for call in locator.call_args_list), 1)

    def test_actor_deadline_before_recipe_is_no_observation_or_action(self):
        self.page.set_content(form_html())
        sentinel = RuntimeError("fixture actor deadline")
        self.journal.clock.error = sentinel
        with patch.object(self.page, "get_by_role", wraps=self.page.get_by_role) as locator:
            with patch.object(self.page, "locator", wraps=self.page.locator) as indicator:
                with self.assertRaises(RuntimeError) as caught:
                    self.save()
        self.assertIs(caught.exception, sentinel)
        self.assertEqual(locator.call_count, 0)
        self.assertEqual(indicator.call_count, 0)
        self.assert_no_click()

    def test_every_poll_wait_has_immediate_actor_clock_check(self):
        self.page.set_content(form_html())
        stages_at_wait = []
        actual_wait = self.page.wait_for_timeout

        def wait(milliseconds):
            stages_at_wait.append(self.journal.clock.stages[-1])
            return actual_wait(milliseconds)

        with patch.object(self.page, "wait_for_timeout", side_effect=wait):
            self.save(stable_seconds=.03)
        self.assertTrue(stages_at_wait)
        self.assertTrue(all("wait" in stage for stage in stages_at_wait), stages_at_wait)
        self.assertEqual(len(self.journal.actions), 1)

    def test_invalid_wait_parameters_fail_before_browser_or_action(self):
        cases = (
            {"timeout_seconds": 31}, {"timeout_seconds": 0},
            {"poll_seconds": 0}, {"poll_seconds": .3},
            {"stable_seconds": 0}, {"stable_seconds": 3},
            {"timeout_seconds": .01, "stable_seconds": .02},
            {"timeout_seconds": float("nan")}, {"stable_seconds": True},
        )
        for options in cases:
            with self.subTest(options=options):
                self.journal = LocalRecipeJournal()
                self.page.set_content(form_html())
                with patch.object(self.page, "get_by_role", wraps=self.page.get_by_role) as locator:
                    with self.assertRaises(RuntimeError):
                        self.save(**options)
                self.assertEqual(locator.call_count, 0)
                self.assertEqual(self.journal.clock.stages, [])
                self.assert_no_click()


if __name__ == "__main__":
    unittest.main()
