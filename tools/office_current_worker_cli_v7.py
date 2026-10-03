"""Source-bound Host7 CLI; no Office or provider calls in sources mode."""
import argparse
import json
from pathlib import Path
import sys
from tools.office_current_facade_v7 import counterpart_registry,source_epoch


def main():
    if len(sys.argv)>1 and sys.argv[1]=='sources':
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('mode',choices=('sources',));parser.add_argument('--repo-root',type=Path,required=True)
        args=parser.parse_args();print(json.dumps(counterpart_registry(args.repo_root),sort_keys=True));return
    with source_epoch() as modules:
        modules['tools/office_current_worker_cli_v4.py'].main()


if __name__=='__main__':main()
