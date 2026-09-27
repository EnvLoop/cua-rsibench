"""v0.6.5 minimal output reaches only current native Odoo GUI controls."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_output_v065 import normalize_model_action, render_for_model


ODOO_DIR = Path(__file__).resolve().parents[1] / "enterprise_fallback/odoo18"
sys.path.insert(0, str(ODOO_DIR))
from odoo_native_adapter import OdooNativeAdapter, VIEWPORT  # noqa: E402


class OdooV065StaticTests(unittest.TestCase):
    def test_alias_click_applies_and_invented_ref_fails(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport=VIEWPORT)
                page.set_content('''<button onclick="document.querySelector('#result').textContent='1'">Open</button>
                    <span id="result">0</span>''')
                adapter = OdooNativeAdapter(page, task_id="odoo-train-synthetic",
                    task_binding_sha256="a" * 64, instruction="Click Open.")
                observation, _ = adapter.observe()
                rendered = json.loads(render_for_model(observation)["instruction"])
                self.assertEqual(rendered["output_version"], "scale-action-output-v0.6.5")
                ref = next(control.ref for control in observation.controls
                           if control.label == "Open")
                full = normalize_model_action(json.dumps({
                    "action": "click", "target": {"ref": ref},
                }), observation, current_frame_id=observation.frame_id)
                adapter.dispatch(full)
                self.assertEqual(page.locator("#result").inner_text(), "1")
                with self.assertRaisesRegex(ContractError, "stale_frame"):
                    adapter.dispatch(full)
                observation, _ = adapter.observe()
                with self.assertRaisesRegex(ContractError, "stale_frame"):
                    normalize_model_action('{"action":"click","target":{"ref":"visible-ref"}}',
                        observation, current_frame_id=observation.frame_id)
                self.assertEqual(page.locator("#result").inner_text(), "1")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
