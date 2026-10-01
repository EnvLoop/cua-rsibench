"""Explicit v22 campaign entrypoint; same existing source/resource/task gates."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import types
from cursibench import full_study_runtime_v2 as runtime

LEGACY_CLI_SHA256='b90a3af0abbdcdd738be01b16d977b93e248c625c6f486860e4637fff1e9b389'


def main(argv=None):
    # Policy-specific arguments are removed before the checked legacy parser;
    # all its required task/configuration arguments and commands remain real.
    policy_parser=argparse.ArgumentParser(add_help=False)
    policy_parser.add_argument('--policy-dir',type=Path,required=True)
    policy_parser.add_argument('--parent-witness',type=Path,required=True)
    policy_parser.add_argument('--policy-public-commit',required=True)
    args,rest=policy_parser.parse_known_args(argv)
    source_path=Path(__file__).with_name('full_study_campaign_dispatch_v1.py')
    raw=source_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=LEGACY_CLI_SHA256:raise ValueError('immutable_campaign_cli_source_changed')
    source=raw.decode();source=source.replace("if __name__ == '__main__':", "if False:")
    namespace={'__file__':str(source_path),'__name__':'checked_campaign_cli_v2'}
    exec(compile(source,'source-checked-full-campaign-cli-v2','exec'),namespace)
    def frozen(**kwargs):
        return runtime.load_policy_study(repo_root=kwargs['repo_root'],parent_manifest=kwargs['manifest_path'],
            parent_prepared=kwargs['prepared_dir'],ratification=kwargs['ratification_path'],
            parent_public_commit=kwargs['public_commit_sha1'],parent_witness=args.parent_witness,policy_dir=args.policy_dir,policy_public_commit=args.policy_public_commit)
    namespace['FrozenStudy']=frozen
    return namespace['main'](rest)


if __name__=='__main__':raise SystemExit(main())
