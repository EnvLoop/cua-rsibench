# Non-Tinker controller runtime

This image packages the implementation, public development fixtures, data parsers, independent verifiers, Docker/Compose clients, E2B clients, Harbor 0.23 with its E2B extra, Chromium and artifact/report libraries. It starts no model request and embeds no private split, account, key or model checkpoint. Original application containers and authenticated Office sessions remain separate execution resources.

Stage an explicit, hash-checked build context and source archive:

```bash
python tools/build_non_tinker_source_bundle_v1.py stage \
  --out work/non-tinker-build/context \
  --archive work/non-tinker-build/EnvLoop-Non-Tinker-Source.tar.gz
docker build -f work/non-tinker-build/context/deployment/non-tinker-runner/Dockerfile \
  -t envloop/non-tinker-runner:local work/non-tinker-build/context
docker run --rm --network none envloop/non-tinker-runner:local
```

The default command checks every source hash, imports real factory/verifier modules, performs Office artifact readback, launches Chromium, applies an input action and captures real pixels. It also verifies Docker, Compose and Harbor executables, imports the E2B SDKs and external Harbor agent classes, and checks the current source bindings and CLI entrypoints in isolated processes. The Harbor Tinker extra is excluded. These are controller build tests; their success is not a real-application qualification or benchmark model score.

To run a specific application command, provide only its owned private workspace and the appropriate application connection. Do not bake private data into a replacement image. Container-control commands require an explicitly supplied Docker daemon connection; Office requires the original signed-in browser bridge. E2B credentials are runtime inputs for owned native guests. Tinker is required only when actual training or Qwen model sampling resumes.

Odoo's historical standalone imports require its code directory on the process path. Use a role-specific process rather than importing conflicting standalone factories into one interpreter:

```bash
docker run --rm \
  -e PYTHONPATH=/opt/envloop:/opt/envloop/src:/opt/envloop/enterprise_fallback/odoo18 \
  envloop/non-tinker-runner:local \
  python -m enterprise_fallback.odoo18.twenty_task_trial_controls_v2 --help
```

The CI workflow builds an amd64 runner, verifies it without network access, uploads the source archive and smoke receipt, and pushes a commit-addressed GHCR image. It uses repository-scoped CI registry authorization. No external training-provider secret is needed. Native cell qualifications and the complete result paper remain separate gates.

The current [non-training release](https://github.com/EnvLoop/cua-rsibench/releases/tag/v0.6.8-non-training-readiness) provides the verified source archive, manifest, smoke receipt, architecture diagram and native-control evidence, including the fresh Impress 0/1/0 controls and the original selection-reference entrypoint builds. Their selection application runs and complete Office lifecycle remain pending. Its [actual CI run](https://github.com/EnvLoop/cua-rsibench/actions/runs/37118914429) built the amd64 image, checked it without network or provider keys, and pushed the code-only image. All 1,720 archive files and the public assets were independently reopened. The stable Desktop V50 default is retained while complete V52 qualification remains pending. The original dated English methods PDF remains linked from the release without being relabeled as a new experiment paper.

The organization currently disables the package's Public setting, so GHCR remains private and anonymous image pull has not passed. Build from the public source archive without registry access. An administrator must enable public package visibility before anonymous pull can be advertised.
