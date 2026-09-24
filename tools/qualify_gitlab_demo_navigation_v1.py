"""Qualify one read-only WebArena task in disposable, real GitLab CE.

The upstream demo image is an empty GitLab, not WebArena's seeded GitLab
snapshot. This smoke proves only task 44's GUI/evaluator wiring and a fresh
browser session. It does not qualify source-data-dependent or mutation tasks.
"""

import argparse
import asyncio
import contextlib
import hashlib
import importlib.metadata
import io
import json
import logging
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

VERSION = "gitlab-demo-navigation-v1"
COMMIT = "6473f72db5dcefc97b5725b59e734504edc28a21"
IMAGE = "sha256:f7e992491db0c80a9a3f066c2c26e69b444307b5a8834e1bdde7929c4a74e97e"
CONTEXT = "colima-cua-gitlab"
CONTAINER = "cua-v06-gitlab-demo"
BASE = "http://localhost:8012"
TASK_ID = 44
ROOT = Path(__file__).resolve().parents[1]
SENSITIVE = re.compile(r"password|passwd|token|secret|session|auth|csrf|^sid$", re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    Path(path).chmod(0o600)


def local_request(url, method, *, setup=False):
    u = urlsplit(url)
    if u.scheme in ("data", "blob", "about"):
        return True
    return (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1")
            and u.port == 8012 and not u.username and not u.password
            and (setup or method in ("GET", "HEAD", "OPTIONS")))


def safe_url(url):
    u = urlsplit(url)
    query = [(name, "REDACTED" if SENSITIVE.search(name) else value)
             for name, value in parse_qsl(u.query, keep_blank_values=True)]
    return urlunsplit((u.scheme, u.netloc.rsplit("@", 1)[-1], u.path, urlencode(query), ""))


def sanitize_har(raw):
    """Strip auth and bodies while retaining actual navigation evidence."""
    allowed = {"accept", "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-user"}
    entries = []
    for item in raw["log"]["entries"]:
        req, response = item["request"], item["response"]
        url = safe_url(req["url"])
        entries.append({"startedDateTime": item.get("startedDateTime"),
            "request": {"url": url, "method": req["method"],
                        "headers": [h for h in req.get("headers", []) if h["name"].lower() in allowed],
                        "cookies": [], "queryString": [{"name": k, "value": v}
                                                     for k, v in parse_qsl(urlsplit(url).query)]},
            "response": {"status": response["status"], "headers": [], "cookies": [],
                         "redirectURL": safe_url(response.get("redirectURL", "")), "content": {}}})
    return {"log": {"version": "1.2", "creator": {"name": VERSION, "version": "1"},
                    "entries": entries}}


def source_proof(source):
    source = Path(source).resolve()
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    require(head == COMMIT, "upstream source commit differs")
    dirty = subprocess.run(["git", "-C", str(source), "status", "--porcelain", "--",
                            "src", "assets/dataset"], check=True, capture_output=True, text=True).stdout
    require(not dirty.strip(), "upstream source/evaluator modified")
    data_path = source / "assets/dataset/webarena-verified.json"
    rows = json.loads(data_path.read_text())
    candidates = [row for row in rows if row["sites"] == ["gitlab"]]
    require(len(candidates) == 180, "GitLab-only task inventory changed")
    templates = {row["intent_template_id"] for row in candidates}
    require(len(templates) == 41, "GitLab intent-template inventory changed")
    task = next(row for row in candidates if row["task_id"] == TASK_ID)
    require(task["revision"] == 2 and task["intent"] == "Open my todos page"
            and task["start_urls"] == ["__GITLAB__"], "task 44 changed")
    require(task["eval"] == [
        {"evaluator": "AgentResponseEvaluator", "results_schema": {"type": "null"},
         "expected": {"task_type": "navigate", "status": "SUCCESS", "retrieved_data": None}},
        {"evaluator": "NetworkEventEvaluator", "ignored_query_params_patterns": ["page", "sort"],
         "expected": {"url": ["__GITLAB__/dashboard/todos",
                              "__GITLAB__/dashboard/todos?state=pending"]}}],
        "task 44 evaluator contract changed")
    from webarena_verified import __file__ as installed_source
    require(Path(installed_source).resolve().is_relative_to(source / "src"),
            "upstream evaluator imported from another installation")
    evaluator_files = {p.relative_to(source).as_posix(): sha(p.read_bytes())
                       for p in (source / "src/webarena_verified").rglob("*.py")}
    kinds = {kind: sum(row["eval"][0]["expected"].get("task_type") == kind for row in candidates)
             for kind in ("navigate", "retrieve", "mutate")}
    return task, {"git_commit": head, "dataset_sha256": sha(data_path.read_bytes()),
                  "task_sha256": digest(task), "evaluator_source_sha256": digest(evaluator_files),
                  "gitlab_only_ids": len(candidates), "unique_intent_templates": len(templates),
                  "task_type_counts": kinds, "versions": {name: importlib.metadata.version(name)
                     for name in ("webarena-verified", "playwright")}}


def container_proof():
    row = json.loads(subprocess.run(["docker", "--context", CONTEXT, "inspect", CONTAINER],
        check=True, capture_output=True, text=True, timeout=30).stdout)[0]
    require(row["Image"] == IMAGE and row["State"]["Running"], "container image/state differs")
    require(row["NetworkSettings"]["Ports"]["8012/tcp"] == [
        {"HostIp": "127.0.0.1", "HostPort": "8012"}], "GitLab is not bound to expected loopback port")
    return {"name": CONTAINER, "docker_context": CONTEXT, "image_sha256": IMAGE,
            "container_id_sha256": sha(row["Id"]), "host_port": 8012,
            "seeded_webarena_snapshot": False}


def business_fingerprint():
    # Explicitly excludes users/sign-in metadata and worker/session tables.
    queries = []
    for name in ("todos", "projects", "issues", "merge_requests"):
        queries.append(f"SELECT '{name}', count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY t.id), '')) FROM {name} t")
    sql = " UNION ALL ".join(queries) + ";"
    row = subprocess.run(["docker", "--context", CONTEXT, "exec", CONTAINER,
                          "gitlab-psql", "-A", "-t", "-c", sql],
                         check=True, capture_output=True, text=True, timeout=90)
    table = {}
    for line in row.stdout.strip().splitlines():
        name, count, value = line.split("|")
        table[name] = {"rows": int(count), "sha256": value}
    require(len(table) == 4, "incomplete independent GitLab business readback")
    return {"tables": table, "sha256": digest(table), "readonly": True,
            "scope": "todos, projects, issues, merge_requests; excludes auth/session/background tables"}


def evaluator(source):
    from webarena_verified.api import WebArenaVerified
    from webarena_verified.types.config import WebArenaVerifiedConfig
    logging.getLogger("webarena_verified").setLevel(logging.ERROR)
    return WebArenaVerified(config=WebArenaVerifiedConfig(
        test_data_file=Path(source) / "assets/dataset/webarena-verified.json",
        environments={"gitlab": {"urls": [BASE]}}))


def evaluate(wa, trace):
    response = {"task_type": "navigate", "status": "SUCCESS", "retrieved_data": None}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = wa.evaluate_task(task_id=TASK_ID, agent_response=response, network_trace=trace)
    return {"task_id": result.task_id, "status": str(result.status), "score": result.score,
            "evaluators": [{"name": r.evaluator_name, "status": str(r.status), "score": r.score}
                           for r in result.evaluators_results],
            "evaluator_checksum": result.webarena_verified_evaluator_checksum,
            "data_checksum": result.webarena_verified_data_checksum,
            "error_present": result.error_msg is not None}


async def case(browser, source, target, positive):
    target.mkdir()
    demo = json.loads((Path(source) / "examples/configs/config.demo.json").read_text())
    credentials = demo["environments"]["__GITLAB__"]["credentials"]
    setup = await browser.new_context()
    try:
        async def setup_guard(route):
            if local_request(route.request.url, route.request.method, setup=True):
                await route.continue_()
            else:
                await route.abort()
        await setup.route("**/*", setup_guard)
        require(not await setup.cookies(), "fresh browser has cookies")
        page = await setup.new_page()
        await page.goto(BASE + "/users/sign_in", wait_until="domcontentloaded", timeout=90000)
        await page.locator("#user_login").fill(credentials["username"])
        await page.locator("#user_password").fill(credentials["password"])
        await page.get_by_role("button", name="Sign in").click()
        await page.wait_for_url(lambda url: "/users/sign_in" not in urlsplit(url).path, timeout=90000)
        state = await setup.storage_state()
    finally:
        await setup.close()
    with tempfile.TemporaryDirectory(prefix=".private-har-", dir=target) as temp:
        raw_path = Path(temp) / "network.har"
        context = await browser.new_context(storage_state=state, viewport={"width": 1440, "height": 1000},
            record_har_path=str(raw_path), record_har_content="omit")
        blocked = []
        async def guard(route):
            request = route.request
            if local_request(request.url, request.method):
                await route.continue_()
            else:
                blocked.append({"method": request.method, "url": safe_url(request.url)})
                await route.abort()
        await context.route("**/*", guard)
        page = await context.new_page()
        try:
            await page.goto(BASE, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            baseline = {"url": safe_url(page.url), "signed_in": await page.locator("#user_login").count() == 0}
            require(baseline["signed_in"], "fresh context did not restore authenticated session")
            await page.screenshot(path=str(target / "baseline.png"), full_page=True)
            # Both branches use the visible GitLab UI; target action is not a direct URL jump.
            if positive:
                await page.get_by_role("link", name=re.compile("To-Do List|To-Do|Todos", re.I)).first.click()
                expected = "/dashboard/todos"
            else:
                await page.get_by_role("link", name="Milestones", exact=True).click()
                expected = "/dashboard/milestones"
            await page.wait_for_url(re.compile(re.escape(expected)), timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            body_text = await page.locator("body").inner_text()
            final = {"url": safe_url(page.url), "title": await page.title(),
                     "body_visible": await page.locator("body").is_visible(),
                     "error_banner_visible": "An error occurred" in body_text}
            await page.screenshot(path=str(target / "final.png"), full_page=True)
        finally:
            await context.close()
        raw = json.loads(raw_path.read_text())
        clean = sanitize_har(raw)
        raw_score = evaluate(evaluator(source), raw_path)
        clean_path = target / "network.har"
        write(clean_path, clean)
        clean_score = evaluate(evaluator(source), clean_path)
        require(raw_score == clean_score, "HAR sanitation changed published evaluator outcome")
        require(credentials["password"] not in clean_path.read_text(), "demo credential leaked")
        record = {"case": target.name, "positive": positive, "baseline": baseline,
                  "final_gui": final, "network_entries": len(clean["log"]["entries"]),
                  "blocked_requests": blocked, "published_evaluator": clean_score,
                  "raw_and_sanitized_evaluator_equal": True, "raw_har_retained": False,
                  "auth_state_retained": False,
                  "screenshots": {name: sha((target / name).read_bytes())
                                  for name in ("baseline.png", "final.png")}}
        write(target / "receipt.json", record)
        return record


def validate(cases, snapshots):
    require([row["positive"] for row in cases] == [True, False, True], "wrong smoke sequence")
    require([row["published_evaluator"]["score"] for row in cases] == [1.0, 0.0, 1.0],
            "official positive/negative discrimination failed")
    require([row["published_evaluator"]["status"] for row in cases] ==
            ["success", "failure", "success"], "evaluator error is not a valid negative")
    require(all(row["raw_and_sanitized_evaluator_equal"] and
                row["final_gui"]["body_visible"] and
                not row["final_gui"]["error_banner_visible"] for row in cases),
            "GUI or evidence incomplete")
    require(all(not any("/api/graphql" in blocked["url"] for blocked in row["blocked_requests"])
                for row in cases), "a required GitLab GraphQL request was blocked")
    require(len(snapshots) == 4 and len({row["sha256"] for row in snapshots}) == 1,
            "read-only UI changed GitLab business state")


async def run(source, output):
    from playwright.async_api import async_playwright
    source, output = Path(source).resolve(), Path(output).resolve()
    require(output.is_relative_to(ROOT / "work/scale-v06") and not output.exists(),
            "output must be a new ignored work/scale-v06 directory")
    output.mkdir(parents=True, mode=0o700)
    report = {"version": VERSION, "task_id": TASK_ID, "complete": False,
              "started_at": time.time(), "model_calls": 0, "paid_provider_calls": 0,
              "user_account_accessed": False, "qualified_task_count": 0,
              "hundred_task_ready": False, "backend_mutation_reset_qualified": False,
              "qualification_scope": "one read-only task in an unseeded real GitLab CE demo"}
    try:
        task, source_data = source_proof(source)
        report.update(task_intent=task["intent"], source=source_data, container=container_proof())
        snapshots = [business_fingerprint()]
        write(output / "business-before.json", snapshots[0])
        cases = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            report["browser_version"] = browser.version
            try:
                for name, positive in (("positive-1", True), ("wrong-milestones", False), ("positive-2", True)):
                    receipt = await case(browser, source, output / name, positive)
                    cases.append(receipt)
                    snapshots.append(business_fingerprint())
                    write(output / ("business-after-" + name + ".json"), snapshots[-1])
                    print(json.dumps({"case": name, "score": receipt["published_evaluator"]["score"],
                                      "network_entries": receipt["network_entries"]}), flush=True)
            finally:
                await browser.close()
        validate(cases, snapshots)
        report.update(complete=True, qualified_task_count=1, positive_scores=[1, 1],
                      negative_score=0, business_state_unchanged=True,
                      limitation="Unseeded demo; no 100-task, source-data, or mutation rollback qualification.")
    except Exception as exc:
        report.update(error_type=type(exc).__name__, blocker="GUI/source/evaluator qualification incomplete")
        raise
    finally:
        report["finished_at"] = time.time()
        write(output / "result.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "work/scale-v06/sources/webarena-verified")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.source, args.output)), indent=2))
