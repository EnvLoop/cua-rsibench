"""Fresh-browser GUI check that non-admin actors cannot browse other splits."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from . import bootstrap, factory, operators, runtime


PRIVATE = runtime.PRIVATE / "operator-acl-gui-private"


def _local(value: str) -> bool:
    parsed = urlsplit(value)
    return ((parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")
             and parsed.port == 8014 and not parsed.username and not parsed.password)
            or parsed.scheme in ("about", "blob", "data"))


async def _case(browser, partition: str, credentials: dict, projects: dict) -> dict:
    folder = PRIVATE / partition
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    context = await browser.new_context(viewport={"width": 1440, "height": 1000})
    blocked_external = []
    async def guard(route):
        if _local(route.request.url):
            await route.continue_()
        else:
            blocked_external.append(urlsplit(route.request.url).hostname or "non-http")
            await route.abort()
    await context.route("**/*", guard)
    page = await context.new_page()
    try:
        if await context.cookies():
            raise RuntimeError("operator browser context not fresh")
        await page.goto(runtime.BASE + "/users/sign_in", wait_until="domcontentloaded")
        await page.locator("#user_login").fill(credentials["username"])
        await page.locator("#user_password").fill(credentials["password"])
        await page.get_by_role("button", name="Sign in").click()
        await page.wait_for_url(lambda value: "users/sign_in" not in value,
                                timeout=90000)
        reachable = {}
        for target_partition, project in projects.items():
            response = await page.goto(runtime.BASE + "/" + project["full_path"],
                                       wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(500)
            body = (await page.locator("body").inner_text())[:5000]
            status = response.status if response is not None else None
            own = target_partition == partition
            if own:
                if status != 200 or project["display_name"] not in body:
                    raise RuntimeError("operator cannot see own project in native GitLab GUI")
            elif status != 404 or project["display_name"] in body:
                raise RuntimeError("operator can see a cross-partition private project")
            screenshot = folder / (target_partition + ".png")
            await page.screenshot(path=str(screenshot), full_page=False,
                                  animations="disabled")
            reachable[target_partition] = {
                "allowed_expected": own,
                "native_http_status": status,
                "project_title_visible": project["display_name"] in body,
                "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
            }
        return {"partition": partition, "user_sha256": factory.sha256(credentials["username"]),
                "fresh_browser_context": True,
                "access": reachable, "blocked_external_host_count": len(set(blocked_external))}
    finally:
        await context.close()


async def run() -> dict:
    from playwright.async_api import async_playwright
    if PRIVATE.exists():
        raise RuntimeError("operator ACL GUI evidence directory already exists")
    PRIVATE.mkdir(mode=0o700, parents=True)
    world = bootstrap.world()
    groups = operators.plan(world)["groups"]
    projects = {partition: next(project for project in bootstrap.all_projects(world)
                                if project["group_path"] == group)
                for partition, group in groups.items()}
    credentials = json.loads(operators.CREDENTIALS.read_text())
    results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for partition in operators.PARTITIONS:
                results.append(await _case(browser, partition,
                                           credentials[partition], projects))
        finally:
            await browser.close()
    own_successes = sum(row["access"][row["partition"]]["native_http_status"] == 200
                        for row in results)
    cross_denials = sum(item["native_http_status"] == 404
                        for row in results for partition, item in row["access"].items()
                        if partition != row["partition"])
    report = {"schema": "envloop-gitlab-scoped-operator-gui-acl-v1",
              "operator_count": 3, "own_project_gui_successes": own_successes,
              "cross_partition_gui_denials": cross_denials,
              "expected_cross_partition_gui_denials": 6,
              "acl_gui_passed": own_successes == 3 and cross_denials == 6,
              "root_admin_actor_used": False,
              "model_calls": 0, "official_final_admitted": 0,
              "cases": results}
    factory.write_private(runtime.PRIVATE / "operator-acl-gui-receipt-private.json", report)
    return {key: value for key, value in report.items() if key != "cases"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(asyncio.run(run()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
