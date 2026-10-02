"""Original Office teacher/selection/shared/final CLI with current rich SEC graphs.

All V4 authority gates and actor/scorer/reset/close mechanics remain unchanged.
The additive source epoch requires fresh witnesses and native qualification.
"""
from tools.office_current_facade_v5 import source_epoch


def main():
    with source_epoch() as modules:
        modules['tools/office_current_worker_cli_v4.py'].main()


if __name__=='__main__':main()
