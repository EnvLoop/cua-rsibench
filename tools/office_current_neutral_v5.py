"""Zero-model original Office neutral lifecycle CLI for rich SEC package sources.

Prepare/check/run use the same reviewed owned-folder V4 lifecycle. Native
execution still requires actual browser permission, profile and owned cleanup.
"""
from tools.office_current_facade_v5 import source_epoch, neutral_module


def main():
    with source_epoch():neutral_module().main()


if __name__=='__main__':main()
