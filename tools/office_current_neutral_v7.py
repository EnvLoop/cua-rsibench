"""Host7 TRAIN-only neutral preparation/check/run; no qualification promotion."""
from tools.office_current_facade_v7 import source_epoch,neutral_module


def main():
    with source_epoch():neutral_module().main()


if __name__=='__main__':main()
