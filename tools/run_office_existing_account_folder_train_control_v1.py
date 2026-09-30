"""Explicit folder-only manual TRAIN auditor; unchanged saved-state scoring."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from tools.office_single_account_train_pilot_v1 import audit, EXISTING_FOLDER_SCOPE


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.spec,args.evidence,args.out,work_root=Path.cwd()/'work',
                 account_scope=EXISTING_FOLDER_SCOPE)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
