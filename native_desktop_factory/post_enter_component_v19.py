"""One uniform wall bound around the unchanged v9 Enter code and auditor."""
from unittest.mock import patch
from . import post_enter_control_proxy_v9 as legacy
from . import v066_post_enter_control_audit_v9 as legacy_audit

MAX_PROBE_WALL_MS = 60_000
SAMPLE_DELAYS_MS = legacy.SAMPLE_DELAYS_MS
ORIGINAL_AUDIT = legacy_audit.post_enter_samples
RECIPE = {'schema': 'cua-native-post-enter-component-v19',
    'max_wall_ms': MAX_PROBE_WALL_MS, 'sample_delays_ms': list(SAMPLE_DELAYS_MS),
    'required_samples': 5, 'equal_final_application_frames': 2,
    'maximum_unique_transitions': 2, 'revisited_state_forbidden': True,
    'native_document_window_required': True, 'raw_full_png_retained': True,
    'input_retries': 0, 'pixel_masking': False, 'max_actor_wall_seconds': 720}


class PostEnterControlProxyV19(legacy.PostEnterControlProxyV9):
    def press(self, key):
        # The superclass performs the exact original input/capture/checks.
        # Only its module-local component limit changes for this synchronous call.
        with patch.object(legacy, 'MAX_PROBE_WALL_MS', MAX_PROBE_WALL_MS):
            return super().press(key)


def post_enter_samples(*args, **kwargs):
    with patch.object(legacy_audit, 'MAX_PROBE_WALL_MS', MAX_PROBE_WALL_MS):
        return ORIGINAL_AUDIT(*args, **kwargs)
