"""Record one private train-only Odoo GUI trajectory under the common v0.6 contract.

The trace directory contains actor-visible screenshots, visible control labels
and normalized actions only. Independent SQL/gold verification is written to
a separate host QA directory and is never mixed into the training trajectory.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from factory import CODE_DIR, PRIVATE, local_config
from gui_controls import browser_login
from reset import file_hash, restore
from verify import score
from worker_lease import exclusive_worker_operation

CONTROLS_JS = r"""() => {
  const all = Array.from(document.querySelectorAll('button,a,input,textarea,[role="tab"],td[name]'));
  const visible = all.filter(el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && r.right > 0 && r.bottom > 0 &&
      r.left < innerWidth && r.top < innerHeight && s.visibility !== 'hidden' &&
      s.display !== 'none';
  });
  return visible.slice(0, 120).map((el, index) => ({
    ref: 'c' + String(index).padStart(3, '0'),
    role: (el.getAttribute('role') || el.tagName.toLowerCase()).slice(0, 80),
    label: (el.getAttribute('aria-label') || el.getAttribute('title') ||
      el.getAttribute('placeholder') || el.innerText || el.getAttribute('name') || '')
      .trim().replace(/\s+/g, ' ').slice(0, 220),
    visible: true,
    enabled: !el.disabled
  }));
}"""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TraceSession:
    def __init__(self, page, case: dict, binding_sha256: str, directory: Path):
        from cursibench.scale_action_contract import VERSION

        self.page = page
        self.case = case
        self.binding = binding_sha256
        self.directory = directory
        self.version = VERSION
        self.step = 0
        self.rows: list[dict] = []
        self.memory = "Locate the RFQ and inspect its attached supplier confirmation."
        directory.mkdir(parents=True, exist_ok=False)

    def action(self, kind: str, *, locator=None, text: str | None = None,
               key: str | None = None, dy: int | None = None,
               memory: str | None = None) -> None:
        from cursibench.scale_action_contract import (
            make_observation, public_receipt, validate_action,
        )

        if memory is not None:
            self.memory = memory
        if locator is not None:
            locator.wait_for(state="visible")
            bounds = self.page.viewport_size
            if bounds is None:
                raise RuntimeError("A fixed actor viewport is required")
            for _ in range(8):
                box = locator.bounding_box()
                if box is not None:
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    if 0 <= x < bounds["width"] and 0 <= y < bounds["height"]:
                        break
                    direction = 600 if y >= bounds["height"] else -600
                else:
                    direction = 600
                self.action("scroll", dy=direction)
            else:
                raise RuntimeError("Target did not enter the recorded viewport")
        screenshot = self.page.screenshot(type="png")
        controls = self.page.evaluate(CONTROLS_JS)
        visible_text = "\n".join(
            f"{row['role']}: {row['label']}" for row in controls if row["label"]
        )[:12000]
        previous = None if self.step == 0 else {"status": "applied", "code": "ok"}
        observation = make_observation(
            task_id=self.case["id"], task_binding_sha256=self.binding,
            instruction=self.case["prompt"], step=self.step,
            screenshot_bytes=screenshot, a11y_text=visible_text,
            controls=controls, previous_action_result=previous,
            memory=self.memory,
        )
        action = {"version": self.version, "task_id": self.case["id"],
                  "task_binding_sha256": self.binding, "step": self.step,
                  "frame_id": observation.frame_id, "type": kind,
                  "memory": self.memory}
        if kind in ("click", "type"):
            if locator is None:
                raise RuntimeError("A visible GUI target is required")
            box = locator.bounding_box()
            if box is None:
                raise RuntimeError("GUI target has no visible bounding box")
            action["target"] = {"x": int(box["x"] + box["width"] / 2),
                                "y": int(box["y"] + box["height"] / 2)}
        if kind == "type":
            if not text:
                raise RuntimeError("Type action needs text")
            action.update({"text": text, "mode": "fill"})
        elif kind == "key":
            action["key"] = key
        elif kind == "wait":
            action["duration_ms"] = 500
        elif kind == "scroll":
            bounds = self.page.viewport_size
            if bounds is None:
                raise RuntimeError("A fixed actor viewport is required")
            action.update({"dx": 0, "dy": dy,
                           "target": {"x": int(bounds["width"] * 0.82),
                                      "y": int(bounds["height"] * 0.75)}})
        validated = validate_action(action, observation,
                                    current_frame_id=observation.frame_id)
        screenshot_name = f"{self.step:02d}.png"
        (self.directory / screenshot_name).write_bytes(screenshot)
        self.rows.append({
            "step": self.step, "screenshot": screenshot_name,
            "screenshot_sha256": _digest(screenshot),
            "visible_text": visible_text, "controls": controls,
            "action": validated, "public_contract_receipt": public_receipt(
                observation, action=validated),
        })
        if kind == "click":
            self.page.mouse.click(validated["target"]["x"], validated["target"]["y"])
        elif kind == "type":
            self.page.mouse.click(validated["target"]["x"], validated["target"]["y"])
            self.page.keyboard.press("Meta+A")
            self.page.keyboard.type(validated["text"])
        elif kind == "key":
            self.page.keyboard.press(validated["key"])
        elif kind == "wait":
            self.page.wait_for_timeout(validated["duration_ms"])
        elif kind == "scroll":
            self.page.mouse.move(validated["target"]["x"], validated["target"]["y"])
            self.page.mouse.wheel(validated["dx"], validated["dy"])
        self.page.wait_for_timeout(350)
        self.step += 1

    def save(self) -> dict:
        payload = {
            "schema": "envloop-odoo-train-only-actor-visible-v0.6",
            "contract_version": self.version,
            "contract_sha256": file_hash(
                CODE_DIR.parents[1] / "src/cursibench/scale_action_contract.py"),
            "task_id": self.case["id"],
            "task_binding_sha256": self.binding,
            "instruction": self.case["prompt"],
            "steps": self.rows,
            "host_only_evaluator_state_included": False,
        }
        path = self.directory / "trace.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        path.chmod(0o600)
        return {"trace_sha256": file_hash(path), "steps": len(self.rows)}


def record() -> dict:
    from playwright.sync_api import sync_playwright

    with exclusive_worker_operation("record_train_trace"):
        config = local_config()
        if config.get("ODOO_PARTITION") != "train":
            raise RuntimeError("This recorder is restricted to the train-only Odoo world")
        world = json.loads((PRIVATE / "partition_cases.json").read_text())
        case = world["cases"]["purchase"][0]
        if case["template_signature"]["target"] != "single_line_unit_price":
            raise RuntimeError("Unexpected train-only causal template")
        binding_rows = json.loads((PRIVATE / "task_set_manifest.json").read_text())["train"]
        binding = next(row["package_sha256"] for row in binding_rows
                       if row["task_id"] == case["id"])
        target_line = next(line for line in case["lines"]
                           if line["initial"]["price"] != line["expected"]["price"])
        credentials = json.loads((PRIVATE / "actor_credentials.json").read_text())
        baseline = restore()
        if not baseline["business_snapshot_equal"] or not baseline["physical_filestore_equal_before_web_restart"]:
            raise RuntimeError("Train trace did not start from frozen checkpoint")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
        source_only = PRIVATE / "train_trace_actor_visible" / case["id"] / run_id
        host_only = PRIVATE / "train_trace_host_qa"
        host_only.mkdir(exist_ok=True)
        trace_metadata = {"trace_sha256": None, "steps": 0}
        result = {"reward": 0.0, "difference_codes": ["trace_execution_failed"]}
        failure = None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    browser_login(page, int(config["ODOO_PORT"]),
                                  credentials["password"], credentials["login"])
                    # Trusted task launch selects the native Purchase list. The
                    # recorded agent controls every subsequent navigation/edit.
                    page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                    trace = TraceSession(page, case, binding, source_only)
                    trace.action("type", locator=page.get_by_role("searchbox"), text=case["id"])
                    trace.action("key", key="Enter")
                    trace.action("click", locator=page.get_by_role("cell", name=case["id"], exact=True))
                    page.wait_for_url("**/odoo/purchase/*")
                    trace.action("click", locator=page.locator("button.o-mail-Chatter-attachFiles"))
                    trace.action("click", locator=page.get_by_text(f"{case['id']}-source.pdf", exact=True))
                    page.locator("iframe.o-FileViewer-view").wait_for()
                    page.wait_for_timeout(400)
                    trace.action("click", locator=page.locator('[title="Close (Esc)"]'),
                                 memory=(f"The supplier PDF confirms {target_line['sku']} at "
                                         f"USD {target_line['expected']['price']:.2f}; correct only its unit price."))
                    row = page.locator("tr").filter(has_text=target_line["sku"]).first
                    trace.action("click", locator=row.locator('td[name="price_unit"]'))
                    trace.action("type", locator=page.locator('td[name="price_unit"] input').first,
                                 text=str(target_line["expected"]["price"]))
                    trace.action("key", key="Tab")
                    save = page.get_by_role("button", name="Save")
                    if save.count():
                        trace.action("click", locator=save)
                    else:
                        trace.action("wait", memory="Wait for the price edit to persist.")
                    page.wait_for_timeout(500)
                    trace.action("finish", memory="The RFQ price has been saved; stop without changing other records.")
                    trace_metadata = trace.save()
                finally:
                    browser.close()
            result = score(case["id"])
        except Exception as error:
            failure = error
        finally:
            after = restore()
        accepted = (failure is None and result["reward"] == 1.0
                    and not result["difference_codes"]
                    and after["business_snapshot_equal"]
                    and after["physical_filestore_equal_before_web_restart"])
        qa = {"schema": "envloop-odoo-train-trace-host-qa-v1",
              "status": "accepted" if accepted else "rejected",
              "run_id": run_id,
              "task_id": case["id"], "train_only_source_group": next(
                  row["source_groups"][0] for row in binding_rows if row["task_id"] == case["id"]),
              "source_document_sha256": json.loads((PRIVATE / "source_hashes.json").read_text())[case["id"]],
              "trace_sha256": trace_metadata["trace_sha256"],
              "steps": trace_metadata["steps"],
              "independent_reward": result["reward"],
              "independent_difference_codes": result["difference_codes"],
              "cold_reset_after_exact": after["business_snapshot_equal"]
                  and after["physical_filestore_equal_before_web_restart"],
              "official_final_task": False,
              "model_attempt": False,
              "failure_type": type(failure).__name__ if failure else None}
        (host_only / f"{case['id']}-{run_id}.json").write_text(json.dumps(qa, indent=2) + "\n")
        if not accepted:
            raise RuntimeError("Train-only actor-visible trace failed independent QA") from failure
        return {"status": qa["status"], "steps": qa["steps"],
                "trace_sha256": qa["trace_sha256"],
                "official_final_task": False}


if __name__ == "__main__":
    print(json.dumps(record(), indent=2))
