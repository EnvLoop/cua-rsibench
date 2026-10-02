# Desktop v21 deadline runtime

The v21 entrypoint implements the absolute actor deadline through the actual model sampler, private RPC, clean child and existing image-bearing vision adapter. The same native guest guard and saved-state scorer remain in use. The shared base and all four selected checkpoints use the same 90-action, 720-second actor policy, 1,200-second guest lease, image profile, seed and retry policy. The selected checkpoint path uses the checked `CampaignSession.checkpoint_result` API and its canonical `checkpoint_path` field.

Exact legacy source hashes are checked before loading the control, common episode and pilot bodies into a separate v21 namespace. Reviewed replacements add only the absolute deadline argument, typed budget-stop branch, retained actor clock and uncertain-intent accounting. Original files are not rewritten by the loader. The proposal source closure includes the new transport, RPC, pinned loader, worker, shared-base bridge, TRAIN pilot and tests. Fresh v21 freeze/permit schemas and attempt IDs prevent reuse of v20 artifacts.

The clean adapter keeps its existing integer limits schema while the wrapped SDK future receives the exact lesser floating-point actor budget. There is no minimum remaining cutoff or integer floor. An independent provider timeout before the actual actor deadline remains a provider fault. A proven actor deadline or response arriving after it is retained in the private journal and RPC result. The proof survives the vision adapter's generic timeout handling. The command is poisoned, cannot be resubmitted and cannot provide a late GUI action. A late completed response has a separate bounded private token receipt.

The parent RPC permits at most five seconds of acknowledgement bookkeeping after the actor deadline. This does not extend the model's wait or authorize GUI action. The actor action clock stops at 720 seconds; raw elapsed time through acknowledgement is retained separately. Native dispatch completion after the deadline is invalid. The independent episode audit verifies the stopped clock, every applied completion timestamp and the budget proof. Only then can trusted saved readback, the original scorer, actor cleanup and a distinct fresh reset complete. Failed readback, restoration or owned-guest cleanup produces no scored task.

Provider shutdown is separate from inference completion. A poisoned child finishes its existing cleanup path and writes a hash-bound close acknowledgement. The parent closes stdin, waits at most 45 seconds, and forces termination only if that bounded cleanup fails. The terminal receipt separately records validated command acknowledgement, command poison, uncertain model completion, forced termination and provider close status. It never resets poison to resume sampling or retries cleanup HTTP. An acknowledged service close does not invent the missing sample output or an invoice.

Uncertain paid requests remain in the ledger. Existing formal selection coverage and provider-invoice guards are unchanged and continue to reject an uncertain request as a completed model response. A TRAIN task can receive an independently verified budget-ending score while formal study eligibility remains separate. The old v20 episode stays invalid and unscored.

Root execution uses a fresh private artifact directory after source review. The pinned native SDK host runs the parent; the sampler process itself always uses the durable root's clean Qwen runtime. Quietly load the already authorized shell configuration with tracing disabled and retain the existing credential environment only in the terminal. Do not run preparation, review or paid execution against an old output namespace.

```bash
export PYTHONPATH="$DESKTOP_REPO:$DESKTOP_REPO/src"
export PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

"$NATIVE_PYTHON" -m native_desktop_factory.model_transport_integration_v21 proposal \
  --output "$FRESH_PRIVATE_ROOT/model-proposal.private.json"

"$NATIVE_PYTHON" -m native_desktop_factory.train_weak_base_pilot_v21 prepare \
  --control-freeze "$EXISTING_V20_CONTROL_FREEZE" --task-id "$PUBLIC_TRAIN_TASK_ID" \
  --output-root "$FRESH_PRIVATE_ROOT/episode" \
  --freeze "$FRESH_PRIVATE_ROOT/source-freeze.private.json"

"$NATIVE_PYTHON" -m native_desktop_factory.train_weak_base_pilot_v21 review \
  --freeze "$FRESH_PRIVATE_ROOT/source-freeze.private.json" \
  --permit "$FRESH_PRIVATE_ROOT/one-use-permit.private.json"

"$NATIVE_PYTHON" -m native_desktop_factory.train_weak_base_pilot_v21 run \
  --freeze "$FRESH_PRIVATE_ROOT/source-freeze.private.json" \
  --permit "$FRESH_PRIVATE_ROOT/one-use-permit.private.json" --enable-paid-pilot
```

The proposal command performs source work only. Review retains the existing active-zero requirement. The paid flag still precedes private/provider access in the runtime entrypoint. Each execution must use the existing one-shot supervisor and a new source-frozen directory; neither an uncertain process nor a consumed permit is restarted automatically.

Validation passed 42 tests using the actual v21 RPC request/acknowledgement path, clean adapter/future path, and common saved/scored/reset episode with synthetic provider and native guest objects, plus the existing transport/pilot and corrected checkpoint regression tests. It includes all five base/checkpoint slots, late responses, earlier provider faults, poisoned shutdown, uncertain close acknowledgement, failed readback/restoration and unchanged budget/guard/scorer bindings. No native GUI or provider operation was performed during implementation. Root must still execute a fresh native pilot and inspect its exact retained artifacts before reporting a current result.
