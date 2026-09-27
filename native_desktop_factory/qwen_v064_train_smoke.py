"""Bounded real Qwen3.8/E2B Desktop smoke on one train/selection task.

This is development evidence only. Final-candidate packages are rejected before
provider creation. The actor sees the native screenshot and instruction through
the shared v0.6.4 model-output boundary; trusted setup/evaluation are separate.
Private screenshots, model responses, task IDs and document bytes stay in work/.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

if __package__:
    from .budget_ledger import audit as audit_budget
    from .gui_control_shell import wait_for_document_ready
    from . import qwen_v064_adapter
    from . import runtime_fingerprint_probe, profile_canonical
    from .qwen_v064_adapter import (PhysicalFrameDrift, dispatch, observe,
                                    parse_current_action)
    from .verify import verify
else:
    from budget_ledger import audit as audit_budget
    from gui_control_shell import wait_for_document_ready
    import qwen_v064_adapter
    import runtime_fingerprint_probe, profile_canonical
    from qwen_v064_adapter import (PhysicalFrameDrift, dispatch, observe,
                                   parse_current_action)
    from verify import verify

from cursibench import (scale_action_contract, scale_action_output_v064,
                        scale_action_output_v065, scale_vision_proxy)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_digest(module) -> str:
    return digest(Path(module.__file__).read_bytes())


def preflight(package_dir: Path, candidate_root: Path) -> tuple[dict, bytes, str, dict, str]:
    package_dir, candidate_root = package_dir.resolve(), candidate_root.resolve()
    if not package_dir.is_relative_to(candidate_root):
        raise ValueError("Package must be inside the candidate root")
    package = json.loads((package_dir / "package.json").read_bytes())
    split = package.get("split")
    if split not in ("train", "selection") or package_dir.parent.name != split:
        raise ValueError("Only train/selection packages may enter this smoke")
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    matching = [row for row in inventory["tasks"] if row["task_id"] == package["task_id"]]
    if len(matching) != 1 or matching[0] != package:
        raise ValueError("Task is absent from the declared nonfinal inventory")
    files = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
             *package_dir.glob("*.docx")]
    if len(files) != 1:
        raise ValueError("Expected one native Office input")
    baseline = files[0].read_bytes()
    instruction = (package_dir / "actor_task.txt").read_text()
    oracle_raw = (package_dir / "oracle.json").read_bytes()
    oracle = json.loads(oracle_raw)
    if (digest(baseline) != package["input_sha256"]
            or digest(instruction.encode()) != package["actor_task_sha256"]):
        raise ValueError("Input or instruction binding changed")
    if (digest(oracle_raw) != package["oracle_sha256"]
            or oracle.get("split") != split or oracle.get("task_id") != package["task_id"]):
        raise ValueError("Oracle or split binding changed")
    return package, baseline, instruction, oracle, files[0].name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--guest-identity-manifest", type=Path, required=True)
    parser.add_argument("--expected-profile-manifest", type=Path, required=True)
    parser.add_argument("--max-actions", type=int, default=3)
    parser.add_argument("--max-samples", type=int, default=4)
    parser.add_argument("--output-contract", choices=("v064", "v065"), default="v064")
    parser.add_argument("--lease-seconds", type=int, default=600)
    parser.add_argument("--max-lane-reserved-usd", type=Decimal, default=Decimal("40"))
    parser.add_argument("--expected-template-id", default="k0wmnzir0zuzye6dndlw")
    args = parser.parse_args()
    if not (1 <= args.max_actions <= 10 and args.max_actions <= args.max_samples <= 12
            and 120 <= args.lease_seconds <= 600):
        raise ValueError("Invalid action/sample/lease envelope")
    output_contract = (scale_action_output_v064 if args.output_contract == "v064"
                       else scale_action_output_v065)
    if args.out.exists():
        raise ValueError("Refusing to overwrite a smoke receipt")
    if not args.out.resolve().is_relative_to((args.work_root / "gui-diagnostics").resolve()):
        raise ValueError("Output must be inside ledger-visible gui-diagnostics")
    package, baseline, instruction, oracle, filename = preflight(args.package, args.candidate_root)
    identity_raw = args.guest_identity_manifest.read_bytes()
    identity = json.loads(identity_raw)
    if (identity.get("schema") != "cua-native-wdi-guest-content-identity-public-v1"
            or identity.get("scoped_guest_content_identity_passed") is not True
            or identity.get("guest_content_probe_script_sha256") !=
            digest(runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())):
        raise ValueError("Guest-content identity manifest is not bound to this probe")
    profile_raw = args.expected_profile_manifest.read_bytes()
    profile_expected = json.loads(profile_raw)
    if (profile_expected.get("schema") != "cua-native-wdi-profile-drift-analysis-public-v1"
            or profile_expected.get("canonical_profile_stable_across_two_probes") is not True
            or profile_expected.get("canonicalizer_sha256") != source_digest(profile_canonical)):
        raise ValueError("Canonical profile manifest is not bound to this parser")
    budget = audit_budget(args.work_root, proposed_new_sandboxes=1,
                          proposed_lease_seconds=args.lease_seconds,
                          max_lane_reserved_usd=args.max_lane_reserved_usd)
    if not budget["within_cap"]:
        raise ValueError("Lane-wide E2B lease reservation exceeds cap")
    if not os.environ.get("TINKER_API_KEY") or not os.environ.get("E2B_API_KEY"):
        raise ValueError("Tinker and E2B credentials must be available privately")
    args.out.mkdir(parents=True)
    receipt = {
        "schema": "cua-native-wdi-gui-development-attempt-v1",
        "attempt": f"qwen_{args.output_contract}_nonfinal_smoke", "status": "started",
        "split": package["split"], "task_id": package["task_id"],
        "input_sha256": digest(baseline), "task_binding_sha256": package["package_sha256"],
        "sandbox_timeout_seconds": args.lease_seconds,
        "max_actions": args.max_actions, "max_samples": args.max_samples,
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "runner_source_sha256": digest(Path(__file__).read_bytes()),
        "native_adapter_source_sha256": source_digest(qwen_v064_adapter),
        "shared_action_parser_sha256": source_digest(scale_action_contract),
        "shared_v064_adapter_sha256": source_digest(scale_action_output_v064),
        "selected_model_output_version": output_contract.OUTPUT_VERSION,
        "selected_model_output_adapter_sha256": source_digest(output_contract),
        "shared_vision_proxy_sha256": source_digest(scale_vision_proxy),
        "expected_guest_identity_manifest_sha256": digest(identity_raw),
        "expected_profile_manifest_sha256": digest(profile_raw),
        "e2b_lane_budget_before": {k: budget[k] for k in (
            "past_conservative_reserved_usd", "proposed_reserved_usd",
            "combined_reserved_usd", "lane_usd_cap")},
        "sampling": [], "actions": [], "frame_screenshots": [],
        "stale_recheck_screenshots": [],
        "provider_billed_usd": None,
        "stage": "pre_provider",
    }

    def persist():
        (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    persist()
    sandbox = None
    service = None
    session_status = "errored"
    try:
        import tinker
        from e2b_desktop import Sandbox
        renderer = scale_vision_proxy.QwenVisionRenderer.load()
        service = tinker.ServiceClient(user_metadata=scale_vision_proxy.campaign_metadata(
            "native-wdi-v064-nonfinal-smoke"))
        backend = scale_vision_proxy.TinkerVisionBackend.from_service(service, renderer)
        sampler = scale_vision_proxy.VisionSamplingAdapter(
            backend, args.out / "sampler-journal",
            limits=scale_vision_proxy.Limits(max_actions=args.max_samples,
                                             output_tokens=512))
        receipt["renderer_identity"] = renderer.identity
        receipt["sampling_binding_sha256"] = sampler.binding_sha256
        persist()
        receipt["stage"] = "create_desktop"
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=args.lease_seconds, allow_internet_access=False)
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version,
        }
        if (info.template_id != args.expected_template_id
                or info.cpu_count > 8 or info.memory_mb > 8192):
            raise ValueError("E2B Desktop image or resource shape drifted")
        receipt["stage"] = "guest_content_attestation"
        sandbox.files.write("/tmp/native-guest-content-probe.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        guest_result = sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe.py",
            timeout=450, request_timeout=480)
        if guest_result.exit_code != 0:
            raise ValueError("Fresh guest content probe failed")
        guest_content = json.loads(guest_result.stdout)
        if (guest_content.get("content_tree_sha256") != identity["static_content_sha256"]
                or guest_content.get("counts") != identity["static_content_counts"]
                or guest_content.get("kernel") != identity["kernel_identity"]
                or guest_content.get("excluded_paths") != identity["static_content_excluded_paths"]
                or info.template_id != identity["provider_template_id"]):
            raise ValueError("Guest content differs from independent frozen identity")
        receipt["guest_content_attested"] = True
        receipt["guest_content_sha256"] = guest_content["content_tree_sha256"]
        initial_profile = sandbox.commands.run(
            "test ! -e /home/user/.config/libreoffice/4/user")
        if initial_profile.exit_code != 0:
            raise ValueError("Fresh LibreOffice profile was already present")
        receipt["fresh_libreoffice_profile_absent"] = True
        persist()
        receipt["stage"] = "stage_public_training_input"
        remote = "/home/user/" + filename
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Trusted staged input differs from bound baseline")
        receipt["stage"] = "open_training_document"
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(sandbox, filename)
        # The stock LibreOffice first-run Tip may appear after the window title
        # already reads as ready. The evaluator calibration used this same
        # neutral GUI dismissal before actor turns; keep it in trusted setup.
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        receipt["trusted_setup_late_tip_guard"] = True
        persist()

        sandbox.files.write("/tmp/native-profile-file-probe.py",
                            runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())

        def canonical_profile() -> str:
            profile_result = sandbox.commands.run("python3 /tmp/native-profile-file-probe.py")
            if profile_result.exit_code != 0:
                raise ValueError("Neutral profile-file manifest failed")
            rows = json.loads(profile_result.stdout)
            registry = bytes(sandbox.files.read(
                "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
                format="bytes"))
            return profile_canonical.canonical_profile_tree(rows, registry)

        receipt["stage"] = "first_task_bound_profile_snapshot"
        persist()
        profile_digest_1 = canonical_profile()
        receipt["task_bound_profile_first_sha256"] = profile_digest_1
        persist()
        time.sleep(1)
        receipt["stage"] = "second_task_bound_profile_snapshot"
        persist()
        profile_digest_2 = canonical_profile()
        if (profile_digest_1 != profile_digest_2
                or profile_digest_1 != profile_expected["canonical_profile_tree_sha256"]):
            raise ValueError("Task-bound LibreOffice profile differs from canonical neutral baseline")
        receipt["task_bound_canonical_profile_sha256"] = profile_digest_1
        receipt["task_bound_profile_attested"] = True
        persist()
        receipt["stage"] = "qwen_actor_sampling"
        previous = None
        memory = ""
        step = 0
        for sample_index in range(args.max_samples):
            frame = observe(sandbox, task_id=package["task_id"],
                            task_binding_sha256=package["package_sha256"],
                            instruction=instruction, step=step,
                            previous_action_result=previous, memory=memory,
                            max_actions=args.max_actions)
            (args.out / f"frame-{sample_index}.png").write_bytes(frame.screenshot_bytes)
            receipt["frame_screenshots"].append({
                "sha256": digest(frame.screenshot_bytes),
                "bytes": len(frame.screenshot_bytes),
            })
            persist()
            rendered = output_contract.render_for_model(frame)
            request_id = "desktopv064_" + uuid4().hex
            result = sampler.sample(request_id=request_id, **rendered)
            receipt["sampling"].append(scale_vision_proxy.public_receipt(result))
            persist()
            if result["status"] != "completed":
                receipt["status"] = "provider_sampling_error"
                break
            def save_stale_frame(raw: bytes) -> None:
                (args.out / f"stale-recheck-{sample_index}.png").write_bytes(raw)
                receipt["stale_recheck_screenshots"].append({
                    "sample_index": sample_index, "sha256": digest(raw),
                    "bytes": len(raw),
                })
                persist()
            try:
                action = parse_current_action(result["text"], frame, sandbox,
                                              on_stale_frame=save_stale_frame,
                                              normalizer=output_contract.normalize_model_action)
            except scale_action_contract.ContractError as exc:
                receipt["actions"].append({"step": step, "status": "rejected",
                                           "error_code": exc.code})
                persist()
                if isinstance(exc, PhysicalFrameDrift) and sample_index + 1 < args.max_samples:
                    continue
                receipt["status"] = "model_output_or_frame_rejected"
                break
            try:
                kind = dispatch(sandbox, action)
            except scale_action_contract.ContractError as exc:
                receipt["actions"].append({"step": step, "status": "rejected",
                                           "error_code": exc.code})
                receipt["status"] = "model_action_not_dispatchable"
                persist()
                break
            receipt["actions"].append({"step": step, "status": "applied",
                                       "type": kind, "memory_sha256": digest(action["memory"].encode())})
            persist()
            memory = action["memory"]
            if kind == "finish":
                receipt["status"] = "model_finished"
                break
            previous = {"status": "applied", "code": "ok"}
            step += 1
            if step >= args.max_actions:
                receipt["status"] = "action_budget_reached"
                break
        else:
            receipt["status"] = "sample_budget_reached"
        saved = bytes(sandbox.files.read(remote, format="bytes"))
        (args.out / ("saved" + Path(filename).suffix)).write_bytes(saved)
        receipt["saved_sha256"] = digest(saved)
        receipt["saved_changed"] = saved != baseline
        receipt["development_verifier"] = verify(baseline, saved, oracle)
        session_status = "success" if receipt["status"] in (
            "model_finished", "action_budget_reached", "sample_budget_reached") else "errored"
    except Exception as exc:
        receipt["status"] = "infrastructure_or_runner_error"
        receipt["error_type"] = type(exc).__name__
        receipt["error_message_private"] = str(exc)[:500]
        persist()
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=8))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        if service is not None:
            try:
                service.close(session_status).result(timeout=30)
                receipt["tinker_session_closed"] = True
            except Exception as exc:
                receipt["tinker_close_error_type"] = type(exc).__name__
        persist()
    print(json.dumps({"status": receipt["status"],
                      "completed_samples": sum(r["status"] == "completed" for r in receipt["sampling"]),
                      "applied_actions": sum(r["status"] == "applied" for r in receipt["actions"]),
                      "desktop_killed": receipt.get("is_running_after_kill") is False},
                     sort_keys=True))
    return 0 if session_status == "success" and receipt.get("is_running_after_kill") is False else 2


if __name__ == "__main__":
    sys.exit(main())
