"""GitLab binding for the shared Qwen3.8 screenshot/action contract.

This adapter never calls a model. It converts a trusted live Playwright frame
to the same `scale_action_contract`/v0.6.3 representation used across the
study, and dispatches only a freshly validated GUI primitive. Fixture APIs,
SQL, filesystem, and arbitrary URLs are not model actions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import import_module
from pathlib import Path
from urllib.parse import urlsplit

from cursibench import gui_sft_episode_v2, scale_action_contract, scale_vision_proxy
from cursibench.scale_action_contract import (
    ContractError, ContractLimits, Observation, make_observation,
    public_receipt as shared_public_receipt, validate_action,
)
from cursibench.gui_sft_episode_v2 import (
    MAX_ACTIONS as SHARED_GUI_MAX_ACTIONS, STUDY_CELL_BY_ADAPTER,
)

from . import runtime


CONTROL_SELECTOR = (
    'a, button, input, select, textarea, [role="button"], [role="link"], '
    '[role="menuitem"], [contenteditable="true"]'
)
ADAPTER_ID = "gitlab_project"
STUDY_CELL = STUDY_CELL_BY_ADAPTER[ADAPTER_ID]
if STUDY_CELL != "gitlab" or SHARED_GUI_MAX_ACTIONS != 90:
    raise RuntimeError("GitLab actor differs from shared GUI SFT cell/action ceiling")
SHARED_SOURCE_SHA256 = {
    "scale_action_contract.py": "8be932baaee4841c6015a432e99bad141c1c2986174c8aeb5448f6bf62df600a",
    "scale_action_output_v064.py": "3a53dee508ec1f5edf8fe1f7000c69e90d00774c8444c21703acc5157cec3d70",
    "scale_vision_proxy.py": "1c8c8ddeaf7f9439f037606092f60219168b9ed1d3f0d4fc64288eef8e0b5ae2",
    "gui_sft_episode_v2.py": "1bfe13ed6be14949b15031945afabff1b9aa5fcd8bc7ba4e50e837cd3a8aff1b",
}


def output_module():
    try:
        return import_module("cursibench.scale_action_output_v064")
    except ImportError:
        raise RuntimeError("shared v0.6.4 Qwen GUI output module is missing") from None


def assert_shared_stack() -> dict[str, str]:
    modules = (scale_action_contract, output_module(),
               scale_vision_proxy, gui_sft_episode_v2)
    actual = {Path(module.__file__).name:
              hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
              for module in modules}
    if actual != SHARED_SOURCE_SHA256:
        raise RuntimeError("shared Qwen GUI source revision differs from frozen GitLab binding")
    return actual


def local_origin(value: str) -> bool:
    parsed = urlsplit(value)
    return (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")
            and parsed.port == 8014 and not parsed.username and not parsed.password)


async def install_local_guard(context) -> list[str]:
    """Block model-session requests outside the dedicated loopback GitLab."""
    blocked = []
    async def guard(route):
        address = route.request.url
        parsed = urlsplit(address)
        if local_origin(address) or parsed.scheme in ("about", "blob", "data"):
            await route.continue_()
        else:
            blocked.append(parsed.hostname or "non-http")
            await route.abort()
    await context.route("**/*", guard)
    return blocked


def short(value: str | None, limit: int) -> str:
    return " ".join((value or "").split())[:limit]


async def visible_controls(page) -> tuple[list[dict], dict[str, object]]:
    """Current, viewport-hit-tested control descriptors and bound DOM nodes."""
    viewport = page.viewport_size or {"width": 1440, "height": 1000}
    controls, handles = [], {}
    for handle in await page.locator(CONTROL_SELECTOR).element_handles():
        if len(controls) >= 120:
            break
        try:
            if not await handle.is_visible() or not await handle.is_enabled():
                continue
            box = await handle.bounding_box()
            if box is None:
                continue
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            if not (0 <= x < viewport["width"] and 0 <= y < viewport["height"]):
                continue
            if not await handle.evaluate('''(node, point) => {
                const hit = document.elementFromPoint(point.x, point.y);
                return !!hit && (hit === node || node.contains(hit));
            }''', {"x": x, "y": y}):
                continue
            tag = (await handle.evaluate("(node) => node.tagName")).lower()
            role = await handle.get_attribute("role") or {
                "a": "link", "button": "button", "input": "textbox",
                "select": "combobox", "textarea": "textbox",
            }.get(tag, "textbox" if await handle.get_attribute("contenteditable") == "true"
                  else "control")
            label = short(await handle.get_attribute("aria-label") or
                          await handle.inner_text() or
                          await handle.get_attribute("title") or
                          await handle.get_attribute("placeholder"), 200)
            if not label and tag in ("button", "a"):
                label = f"Unlabeled {role} at screenshot ({round(x)}, {round(y)})"
            if not label:
                continue
            ref = f"c{len(controls) + 1:03d}"
            controls.append({"ref": ref, "role": short(role, 80),
                             "label": label, "visible": True, "enabled": True})
            handles[ref] = handle
        except Exception:
            continue  # Detached controls never become an advertised ref.
    return controls, handles


@dataclass(frozen=True)
class Frame:
    observation: Observation
    handles: dict[str, object]
    page_url: str


async def capture(page, *, task_id: str, binding_sha256: str, instruction: str,
                  step: int, memory: str = "", previous: dict | None = None,
                  limits: ContractLimits | None = None) -> Frame:
    assert_shared_stack()
    if not local_origin(page.url):
        raise ContractError("invalid_observation")
    frame_url = page.url
    image = await page.screenshot(type="png", full_page=False,
                                  animations="disabled",
                                  mask=[page.locator('input[type="password"]')])
    controls, handles = await visible_controls(page)
    headings = []
    for node in await page.locator("h1,h2").element_handles():
        try:
            if await node.is_visible():
                headings.append(short(await node.inner_text(), 200))
        except Exception:
            continue
    # Fail if the source page changed while collecting its references.
    repeat = await page.screenshot(type="png", full_page=False,
                                   animations="disabled",
                                   mask=[page.locator('input[type="password"]')])
    if page.url != frame_url or image != repeat:
        raise ContractError("stale_frame")
    obs = make_observation(
        task_id=task_id, task_binding_sha256=binding_sha256,
        instruction=instruction, step=step, screenshot_bytes=image,
        a11y_text="Visible headings: " + "; ".join(headings[:12]), dom_text="",
        controls=controls, previous_action_result=previous,
        memory=memory, limits=limits or ContractLimits(max_step=90))
    return Frame(obs, handles, frame_url)


def model_request(frame: Frame) -> dict[str, bytes | str]:
    assert_shared_stack()
    return output_module().render_for_model(frame.observation)


def _action_refs(action: dict) -> tuple[str, ...]:
    targets = []
    if action["type"] in ("click", "type"):
        targets.append(action["target"])
    elif action["type"] in ("key", "scroll") and "target" in action:
        targets.append(action["target"])
    elif action["type"] == "drag":
        targets.extend((action["from"], action["to"]))
    return tuple(target["ref"] for target in targets if "ref" in target)


async def _fresh(page, frame: Frame, action: dict) -> bool:
    if page.url != frame.page_url or not local_origin(page.url):
        return False
    image = await page.screenshot(type="png", full_page=False,
                                  animations="disabled",
                                  mask=[page.locator('input[type="password"]')])
    if hashlib.sha256(image).hexdigest() != frame.observation.screenshot["sha256"]:
        return False
    refs = _action_refs(action)
    if not refs:
        return True
    controls, handles = await visible_controls(page)
    old = {row.ref: row for row in frame.observation.controls}
    current = {row["ref"]: row for row in controls}
    for ref in refs:
        if ref not in old or ref not in current or ref not in frame.handles or ref not in handles:
            return False
        if old[ref].label != current[ref]["label"] or old[ref].role != current[ref]["role"]:
            return False
        try:
            if not await frame.handles[ref].evaluate(
                    "(node, candidate) => node.isConnected && node === candidate",
                    handles[ref]):
                return False
        except Exception:
            return False
    return True


async def _point(page, target: dict, handles: dict[str, object]) -> tuple[float, float]:
    if "x" in target:
        return float(target["x"]), float(target["y"])
    item = handles[target["ref"]]
    if not await item.is_visible() or not await item.is_enabled():
        raise ContractError("stale_frame")
    box = await item.bounding_box()
    if box is None:
        raise ContractError("stale_frame")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


async def validate_and_dispatch(page, raw_model_action: str, frame: Frame) -> tuple[dict, dict]:
    """Recheck exact observed pixels and bound refs immediately before GUI dispatch."""
    assert_shared_stack()
    action = output_module().normalize_model_action(
        raw_model_action, frame.observation,
        current_frame_id=frame.observation.frame_id)
    if not await _fresh(page, frame, action):
        raise ContractError("stale_frame")
    validate_action(action, frame.observation,
                    current_frame_id=frame.observation.frame_id)
    kind = action["type"]
    if kind == "finish":
        result = {"status": "applied", "code": "ok"}
    elif kind == "wait":
        await page.wait_for_timeout(action["duration_ms"])
        result = {"status": "applied", "code": "ok"}
    elif kind == "click":
        target = action["target"]
        if "ref" in target:
            await frame.handles[target["ref"]].click(timeout=15000)
        else:
            await page.mouse.click(target["x"], target["y"])
        result = {"status": "applied", "code": "ok"}
    elif kind == "type":
        target = action["target"]
        if "ref" in target:
            control = frame.handles[target["ref"]]
            if action["mode"] == "fill":
                await control.fill(action["text"], timeout=15000)
            else:
                await control.focus()
                await page.keyboard.insert_text(action["text"])
        else:
            await page.mouse.click(target["x"], target["y"])
            if action["mode"] == "fill":
                await page.keyboard.press("ControlOrMeta+A")
            await page.keyboard.insert_text(action["text"])
        result = {"status": "applied", "code": "ok"}
    elif kind == "key":
        if "target" in action:
            target = action["target"]
            if "ref" in target:
                await frame.handles[target["ref"]].focus()
            else:
                await page.mouse.click(target["x"], target["y"])
        await page.keyboard.press(action["key"])
        result = {"status": "applied", "code": "ok"}
    elif kind == "scroll":
        if "target" in action:
            target = action["target"]
            if "ref" in target:
                await frame.handles[target["ref"]].hover()
            else:
                await page.mouse.move(target["x"], target["y"])
        await page.mouse.wheel(action["dx"], action["dy"])
        result = {"status": "applied", "code": "ok"}
    elif kind == "drag":
        x1, y1 = await _point(page, action["from"], frame.handles)
        x2, y2 = await _point(page, action["to"], frame.handles)
        await page.mouse.move(x1, y1)
        await page.mouse.down()
        await page.mouse.move(x2, y2, steps=8)
        await page.mouse.up()
        result = {"status": "applied", "code": "ok"}
    else:
        raise ContractError("invalid_action")
    return result, shared_public_receipt(frame.observation, action=action)
