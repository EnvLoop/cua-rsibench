"""Fresh TRAIN source/reset qualification for the shared V15 task epoch."""
from . import v066_neutral_telemetry_coldboot_v7 as _loader

_loader._load_frozen('gitlab_world/v066_uniform_train_qualification_v14.py',
                    'cecdc452419162bc8530392944b812679ab191d9c111fc425a590b2dd95980a9', globals(),
                    (('v14', 'v15', 3),))


if __name__ == '__main__':
    main()
