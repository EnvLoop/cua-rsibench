# Non-Tinker controller runtime

This image packages the implementation, public development fixtures, data parsers, independent verifiers, Docker/Compose clients, E2B clients, Chromium and artifact/report libraries. It starts no model request and embeds no private split, account, key or model checkpoint. Original application containers and authenticated Office sessions remain separate execution resources.

Stage an explicit, hash-checked build context and source archive:

```bash
python tools/build_non_tinker_source_bundle_v1.py stage \
  --out work/non-tinker-build/context \
  --archive work/non-tinker-build/EnvLoop-Non-Tinker-Source.tar.gz
docker build -f work/non-tinker-build/context/deployment/non-tinker-runner/Dockerfile \
  -t envloop/non-tinker-runner:local work/non-tinker-build/context
docker run --rm --network none envloop/non-tinker-runner:local
```

The default command checks every source hash, imports real factory/verifier modules, performs Office artifact readback, launches Chromium, applies an input action and captures real pixels. It also verifies Docker and Compose executables and imports the E2B SDKs. These are controller build tests; their success is not a real-application qualification or benchmark model score.

To run a specific application command, provide only its owned private workspace and the appropriate application connection. Do not bake private data into a replacement image. Container-control commands require an explicitly supplied Docker daemon connection; Office requires the original signed-in browser bridge. E2B credentials are runtime inputs for owned native guests. Tinker is required only when actual training or Qwen model sampling resumes.

Odoo's historical standalone imports require its code directory on the process path. Use a role-specific process rather than importing conflicting standalone factories into one interpreter:

```bash
docker run --rm \
  -e PYTHONPATH=/opt/envloop:/opt/envloop/src:/opt/envloop/enterprise_fallback/odoo18 \
  envloop/non-tinker-runner:local \
  python -m enterprise_fallback.odoo18.twenty_task_trial_controls_v2 --help
```

The CI workflow builds an amd64 runner, verifies it without network access, uploads the source archive and smoke receipt, and pushes a commit-addressed GHCR image. It uses repository-scoped CI registry authorization. No external training-provider secret is needed. Native cell qualifications and the complete result paper remain separate gates.
