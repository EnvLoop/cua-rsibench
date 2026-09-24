"""Qualify one published GitLab mutation on an isolated, seeded GitLab CE.

The fixture is a minimal local `primer/design` project, not the original
WebArena GitLab snapshot. A fresh browser performs every task action through
GitLab's visible UI. The pinned upstream evaluator and an independent DB
readback must both discriminate the correct and wrong-date attempts.
"""

import argparse
import asyncio
import contextlib
from datetime import date
import hashlib
import io
import json
import logging
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "6473f72db5dcefc97b5725b59e734504edc28a21"
SOURCE_SHA256 = "d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30"
CONTEXT = "colima-cua-gitlab-mutation"
CONTAINER = "cua-v06-gitlab-mutation"
BASE = "http://localhost:8013"
PROJECT = "primer/design"
TASK_ID = 590
TITLE = "product launch"
START_DATE = "2023-01-16"
CORRECT_DUE = "2023-01-30"
WRONG_DUE = "2023-02-01"
VERSION = "gitlab-milestone-mutation-v1"
SENSITIVE = re.compile(r"password|passwd|token|secret|session|auth|csrf|^sid$", re.I)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")))


def display_date(value):
    return date.fromisoformat(value).strftime("%b %d, %Y").replace(" 0", " ")


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    Path(path).chmod(0o600)


def docker(*args, timeout=90, input_text=None):
    return subprocess.run(["docker", "--context", CONTEXT, *args], input=input_text,
                          text=True, capture_output=True, check=True, timeout=timeout).stdout


def safe_url(value):
    if not value:
        return value
    u = urlsplit(value)
    query = [(key, "REDACTED" if SENSITIVE.search(key) else data)
             for key, data in parse_qsl(u.query, keep_blank_values=True)]
    return urlunsplit((u.scheme, u.netloc.rsplit("@", 1)[-1], u.path, urlencode(query), ""))


def local_request(url):
    u = urlsplit(url)
    return (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1")
            and u.port == 8013 and not u.username and not u.password) or u.scheme in ("about", "blob", "data")


def sanitize_har(raw):
    """Retain only task-relevant form fields and public request metadata."""
    entries = []
    for row in raw["log"]["entries"]:
        req, res = row["request"], row["response"]
        request = {"url": safe_url(req["url"]), "method": req["method"],
                   "headers": [], "cookies": [], "queryString": []}
        form = req.get("postData") or {}
        if urlsplit(req["url"]).path == f"/{PROJECT}/-/milestones" and req["method"] == "POST":
            values = dict(parse_qsl(form.get("text", ""), keep_blank_values=True))
            keys = ("milestone[title]", "milestone[start_date]", "milestone[due_date]")
            request["postData"] = {"mimeType": "application/x-www-form-urlencoded",
                                   "text": urlencode([(key, values.get(key, "")) for key in keys])}
        entries.append({"startedDateTime": row.get("startedDateTime"), "request": request,
                        "response": {"status": res["status"], "headers": [], "cookies": [],
                                     "redirectURL": safe_url(res.get("redirectURL", "")),
                                     "content": {}}})
    return {"log": {"version": "1.2", "creator": {"name": VERSION, "version": "1"},
                    "entries": entries}}


def source_proof(source):
    source = Path(source).resolve()
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    require(head == SOURCE_COMMIT, "upstream source commit differs")
    dirty = subprocess.run(["git", "-C", str(source), "status", "--porcelain", "--",
                            "src", "assets/dataset"], capture_output=True, text=True, check=True).stdout
    require(not dirty.strip(), "upstream evaluator or dataset modified")
    data = source / "assets/dataset/webarena-verified.json"
    require(sha(data.read_bytes()) == SOURCE_SHA256, "upstream task dataset changed")
    task = next(row for row in json.loads(data.read_text()) if row["task_id"] == TASK_ID)
    require(task["sites"] == ["gitlab"] and task["revision"] == 2
            and task["intent_template_id"] == 339, "task identity changed")
    require(task["intent"] ==
            'Create a milestone in the current repo with title "product launch" for the upcoming event of product launch starting on January 16, 2023 and ending on January 30, 2023',
            "task intent changed")
    expected = task["eval"][1]["expected"]
    require(expected == {"url": "__GITLAB__/primer/design/-/milestones", "http_method": "POST",
                         "post_data": {"milestone[title]": TITLE,
                                       "milestone[start_date]": START_DATE,
                                       "milestone[due_date]": CORRECT_DUE},
                         "response_status": 302}, "published evaluator contract changed")
    import webarena_verified
    require(Path(webarena_verified.__file__).resolve().is_relative_to(source / "src"),
            "installed evaluator does not match pinned source")
    files = {p.relative_to(source).as_posix(): sha(p.read_bytes())
             for p in (source / "src/webarena_verified").rglob("*.py")}
    return {"git_commit": head, "dataset_sha256": SOURCE_SHA256,
            "task_sha256": digest(task), "evaluator_source_sha256": digest(files),
            "task_intent": task["intent"], "seeded_original_webarena_snapshot": False}


def container_proof():
    row = json.loads(docker("inspect", CONTAINER, timeout=30))[0]
    require(row["State"]["Running"] and row["Config"]["Image"] ==
            "gitlab/gitlab-ce:18.5.0-ce.0", "isolated GitLab image/state changed")
    require(row["NetworkSettings"]["Ports"]["8013/tcp"] ==
            [{"HostIp": "127.0.0.1", "HostPort": "8013"}], "loopback port changed")
    return {"docker_context": CONTEXT, "container_name": CONTAINER,
            "container_id_sha256": sha(row["Id"]), "image_sha256": row["Image"],
            "loopback_port": 8013}


def psql(query):
    return docker("exec", CONTAINER, "gitlab-psql", "-A", "-t", "-c", query).strip()


def snapshot():
    project = psql("SELECT id FROM projects WHERE path='design' AND namespace_id="
                   "(SELECT id FROM namespaces WHERE path='primer' AND type='Group');")
    require(project.isdigit(), "fixture project missing or ambiguous")
    project_id = int(project)
    raw = psql("SELECT COALESCE(json_agg(row_to_json(m)), '[]'::json) FROM "
               "(SELECT id,title,start_date,due_date,project_id,group_id,state FROM milestones "
               f"WHERE project_id={project_id} ORDER BY id) m;")
    milestones = json.loads(raw)
    events = int(psql(f"SELECT count(*) FROM events WHERE project_id={project_id};"))
    issues = int(psql(f"SELECT count(*) FROM issues WHERE project_id={project_id};"))
    seq = psql("SELECT last_value || '|' || is_called FROM milestones_id_seq;")
    return {"project_id": project_id, "milestones": milestones, "events": events,
            "issues": issues, "milestones_sequence": seq,
            "business_sha256": digest([milestones, events, issues, seq])}


def reset(baseline):
    """Reset only benchmark-created state inside this disposable VM."""
    project_id = baseline["project_id"]
    seq_value, seq_called = baseline["milestones_sequence"].split("|")
    require(seq_value.isdigit() and seq_called in ("t", "f", "true", "false"),
            "invalid baseline sequence")
    code = ("project=Project.find_by_full_path('primer/design') or raise 'project absent';"
            f"raise 'project changed' unless project.id=={project_id};"
            f"rows=Milestone.where(project_id:{project_id},title:'{TITLE}').to_a;"
            "ids=rows.map(&:id);rows.each(&:destroy!);"
            f"Event.where(project_id:{project_id},target_type:'Milestone',target_id:ids).delete_all;"
            "ActiveRecord::Base.connection.execute(\"SELECT setval('milestones_id_seq', "
            f"{seq_value}, {str(seq_called in ('t', 'true')).lower()})\");"
            "puts rows.size")
    count = docker("exec", CONTAINER, "gitlab-rails", "runner", code, timeout=120).strip()
    require(count == "1", "expected exactly one milestone to reset")
    after = snapshot()
    require(after == baseline, "GitLab business state did not return to baseline")
    return {"reset_rows": int(count), "business_state_restored": True,
            "baseline_sha256": baseline["business_sha256"]}


def evaluator(source):
    from webarena_verified.api import WebArenaVerified
    from webarena_verified.types.config import WebArenaVerifiedConfig
    logging.getLogger("webarena_verified").setLevel(logging.ERROR)
    return WebArenaVerified(config=WebArenaVerifiedConfig(
        test_data_file=Path(source) / "assets/dataset/webarena-verified.json",
        environments={"gitlab": {"urls": [BASE]}}))


def evaluate(wa, trace):
    response = {"task_type": "mutate", "status": "SUCCESS", "retrieved_data": None}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = wa.evaluate_task(task_id=TASK_ID, agent_response=response, network_trace=trace)
    return {"status": str(result.status), "score": result.score,
            "evaluators": [{"name": item.evaluator_name, "status": str(item.status),
                            "score": item.score} for item in result.evaluators_results],
            "error_present": result.error_msg is not None}


async def case(browser, source, target, password, due):
    target.mkdir()
    with tempfile.TemporaryDirectory(prefix=".private-har-", dir=target) as temp:
        raw_har = Path(temp) / "network.har"
        context = await browser.new_context(viewport={"width": 1440, "height": 1000},
                                            record_har_path=str(raw_har), record_har_content="embed")
        blocked = []
        async def guard(route):
            if local_request(route.request.url):
                await route.continue_()
            else:
                blocked.append({"method": route.request.method,
                                "host": urlsplit(route.request.url).hostname})
                await route.abort()
        await context.route("**/*", guard)
        page = await context.new_page()
        try:
            require(not await context.cookies(), "browser context not fresh")
            await page.goto(BASE + "/users/sign_in", wait_until="domcontentloaded", timeout=90000)
            await page.locator("#user_login").fill("root")
            await page.locator("#user_password").fill(password)
            await page.get_by_role("button", name="Sign in").click()
            await page.wait_for_url(lambda value: "users/sign_in" not in value, timeout=90000)
            await page.goto(BASE + f"/{PROJECT}", wait_until="domcontentloaded", timeout=90000)
            require(await page.get_by_text("Design", exact=True).count() > 0, "project GUI missing")
            await page.screenshot(path=str(target / "project.png"), full_page=True)
            await page.get_by_text("Plan", exact=True).first.click()
            await page.get_by_role("link", name="Milestones").click()
            await page.get_by_role("link", name="New milestone").click()
            await page.locator("#milestone_title").fill(TITLE)
            for _ in range(3):
                start = page.locator("#milestone_start_date")
                await start.click()
                await start.fill(START_DATE)
                await start.press("Tab")
                await page.wait_for_timeout(100)
                end = page.locator("#milestone_due_date")
                await end.click()
                await end.fill(due)
                await end.press("Tab")
                await page.wait_for_timeout(100)
                values = [await page.locator(f"#milestone_{name}").input_value()
                          for name in ("title", "start_date", "due_date")]
                if values == [TITLE, START_DATE, due]:
                    break
            require(values == [TITLE, START_DATE, due],
                    f"visible date form values differ after three UI attempts: {values}")
            await page.screenshot(path=str(target / "form.png"), full_page=True)
            await page.get_by_role("button", name="Create milestone").click()
            await page.wait_for_url(lambda value: "/milestones/new" not in value, timeout=90000)
            require(f"/{PROJECT}/-/milestones/" in page.url, "milestone GUI did not open")
            await page.get_by_text(display_date(due), exact=False).first.wait_for(timeout=30000)
            body_text = await page.locator("body").inner_text()
            await page.screenshot(path=str(target / "final.png"), full_page=True)
            final = {"url": safe_url(page.url), "title_visible": await page.get_by_text(TITLE).count() > 0,
                     "start_date_visible": display_date(START_DATE) in body_text,
                     "due_date_visible": display_date(due) in body_text}
            require(all(final[key] for key in ("title_visible", "start_date_visible", "due_date_visible")),
                    "saved milestone title or dates not visible in GitLab")
        finally:
            await context.close()
        raw = json.loads(raw_har.read_text())
        clean = sanitize_har(raw)
        clean_path = target / "network.sanitized.har"
        write_new(clean_path, clean)
        wa = evaluator(source)
        raw_score, clean_score = evaluate(wa, raw_har), evaluate(wa, clean_path)
        require(raw_score == clean_score, "HAR sanitation changed official score")
        require(password not in clean_path.read_text(), "demo login secret in sanitized HAR")
        receipt = {"case": target.name, "form_values": values, "final_gui": final,
                   "official_evaluator": clean_score, "raw_and_sanitized_score_equal": True,
                   "network_entries": len(clean["log"]["entries"]),
                   "blocked_requests": blocked, "raw_har_retained": False,
                   "auth_state_retained": False,
                   "screenshots_sha256": {name: sha((target / name).read_bytes())
                                          for name in ("project.png", "form.png", "final.png")}}
        write_new(target / "receipt.json", receipt)
        return receipt


async def run(source, output, private_env):
    from playwright.async_api import async_playwright
    source, output = Path(source).resolve(), Path(output).resolve()
    require(output.is_relative_to(ROOT / "work/scale-v06") and not output.exists(),
            "output must be a new ignored work/scale-v06 directory")
    secret_lines = Path(private_env).read_text().splitlines()
    secret = [line.split("=", 1)[1] for line in secret_lines
              if line.startswith("GITLAB_ROOT_PASSWORD=")]
    require(len(secret) == 1 and secret[0], "isolated test credential missing")
    output.mkdir(mode=0o700, parents=True)
    report = {"version": VERSION, "task_id": TASK_ID, "complete": False,
              "model_calls": 0, "qualified_task_count": 0, "hundred_task_ready": False,
              "original_snapshot_seeded": False, "started_at": time.time()}
    try:
        report["source"] = source_proof(source)
        report["container"] = container_proof()
        baseline = snapshot()
        require(not baseline["milestones"], "project baseline has milestones")
        report["business_baseline"] = baseline
        attempts = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                for name, due in (("positive-1", CORRECT_DUE),
                                  ("wrong-due-date", WRONG_DUE),
                                  ("positive-2", CORRECT_DUE)):
                    attempt = None
                    try:
                        attempt = await case(browser, source, output / name, secret[0], due)
                        current = snapshot()
                        require(len(current["milestones"]) == 1,
                                "GUI did not persist exactly one milestone")
                        item = current["milestones"][0]
                        require(item["project_id"] == baseline["project_id"] and
                                item["title"] == TITLE and item["start_date"] == START_DATE and
                                item["due_date"] == due,
                                "independent DB readback differs from GUI intent")
                        attempt["db_readback"] = {"milestone": item, "events": current["events"],
                                                   "issues": current["issues"],
                                                   "business_sha256": current["business_sha256"]}
                    finally:
                        # A failed evaluator/readback must not leave a submitted
                        # milestone in the isolated fixture.
                        if snapshot() != baseline:
                            reset_result = reset(baseline)
                            if attempt is not None:
                                attempt["reset"] = reset_result
                    require(attempt is not None and "reset" in attempt,
                            "GUI task did not produce a resettable milestone")
                    attempts.append(attempt)
            finally:
                await browser.close()
        scores = [row["official_evaluator"]["score"] for row in attempts]
        require(scores == [1.0, 0.0, 1.0], "official evaluator failed positive/wrong-date/positive")
        require(all(not row["official_evaluator"]["error_present"] and
                    row["raw_and_sanitized_score_equal"] and row["reset"]["business_state_restored"]
                    for row in attempts), "evaluator or reset incomplete")
        report.update(complete=True, qualified_task_count=1, scores=scores,
                      attempts=attempts, final_business_state=snapshot(),
                      limitation="One published task on a synthetic local project; no model run or 100-task admission.")
    except Exception as exc:
        report.update(error_type=type(exc).__name__, blocker="GitLab mutation qualification incomplete")
        raise
    finally:
        report["finished_at"] = time.time()
        write_new(output / "result.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "work/scale-v06/sources/webarena-verified")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-env", type=Path,
                        default=ROOT / "work/scale-v06/gitlab-mutation-private.env")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.source, args.output, args.private_env)), indent=2))
