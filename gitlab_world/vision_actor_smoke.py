"""Read-only native-GitLab proof of the shared Qwen screenshot/action adapter."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from cursibench.scale_action_contract import ContractError

from . import bootstrap, factory, operators, runtime, verify, vision_actor


PRIVATE = runtime.PRIVATE / "vision-actor-smoke-v064-private"


async def run() -> dict:
    from playwright.async_api import async_playwright

    if PRIVATE.exists():
        raise RuntimeError("Qwen adapter smoke output already exists")
    PRIVATE.mkdir(mode=0o700, parents=True)
    before = verify.state_snapshot()
    baseline = json.loads((runtime.PRIVATE / "baseline-persisted-state.json").read_text())
    if before["business_sha256"] != baseline["business_sha256"]:
        raise RuntimeError("Qwen adapter smoke did not start from cold baseline")
    world = bootstrap.world()
    project = next(row for row in world["projects"] if row["partition"] == "train")
    task = next(row for row in world["tasks"]
                if row["project_family"] == project["full_path"])
    credential = json.loads(operators.CREDENTIALS.read_text())["train"]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context = await browser.new_context(viewport={"width": 1440, "height": 1000})
            blocked = await vision_actor.install_local_guard(context)
            page = await context.new_page()
            try:
                if await context.cookies():
                    raise RuntimeError("Qwen adapter browser context not fresh")
                await page.goto(runtime.BASE + "/users/sign_in",
                                wait_until="domcontentloaded")
                await page.locator("#user_login").fill(credential["username"])
                await page.locator("#user_password").fill(credential["password"])
                await page.get_by_role("button", name="Sign in").click()
                await page.wait_for_url(lambda value: "users/sign_in" not in value,
                                        timeout=90000)
                await page.goto(runtime.BASE + "/" + project["full_path"],
                                wait_until="domcontentloaded")
                await page.get_by_text(project["display_name"], exact=False).first.wait_for()
                binding = factory.sha256(factory.canonical(task))
                frame = None
                for _ in range(6):
                    try:
                        frame = await vision_actor.capture(
                            page, task_id=task["task_id"], binding_sha256=binding,
                            instruction=task["prompt"], step=0)
                        break
                    except ContractError as exc:
                        if exc.code != "stale_frame":
                            raise
                        await page.wait_for_timeout(300)
                if frame is None:
                    raise RuntimeError("GitLab page did not settle for Qwen frame")
                request = vision_actor.model_request(frame)
                image = PRIVATE / "frame-private.png"
                image.write_bytes(request["image_bytes"])
                image.chmod(0o600)
                result, public = await vision_actor.validate_and_dispatch(
                    page, '{"type":"wait","duration_ms":20}', frame)
                if result != {"status": "applied", "code": "ok"}:
                    raise RuntimeError("shared action wait did not dispatch")
                await page.goto(runtime.BASE + "/" + project["full_path"] + "/-/issues",
                                wait_until="domcontentloaded")
                stale_rejected = False
                try:
                    await vision_actor.validate_and_dispatch(
                        page, '{"type":"wait","duration_ms":20}', frame)
                except ContractError as exc:
                    stale_rejected = exc.code == "stale_frame"
                if not stale_rejected:
                    raise RuntimeError("changed GitLab frame reused a stale model action")
            finally:
                await context.close()
        finally:
            await browser.close()
    after = verify.state_snapshot()
    if after["business_sha256"] != before["business_sha256"]:
        raise RuntimeError("read-only Qwen adapter smoke mutated GitLab business state")
    private = {"schema": "envloop-gitlab-shared-qwen-actor-smoke-v1",
               "shared_source_sha256": vision_actor.assert_shared_stack(),
               "shared_output_version": vision_actor.output_module().OUTPUT_VERSION,
               "shared_action_contract_version": public["version"],
               "model_calls": 0, "applied_read_only_wait": True,
               "stale_frame_rejected": stale_rejected,
               "scoped_non_admin_actor": True,
               "same_business_sha256": True,
               "screenshot_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
               "control_count": public["control_count"],
               "blocked_external_host_count": len(set(blocked)),
               "public_contract_receipt": public,
               "official_final_admitted": 0}
    factory.write_private(PRIVATE / "receipt.json", private)
    return {key: value for key, value in private.items()
            if key not in ("public_contract_receipt", "screenshot_sha256")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(asyncio.run(run()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
