"""Shared passive readiness after native Save; exact v18 checks are reused."""
from unittest.mock import patch
from . import pre_observation_readiness_v18 as base

MAX_WALL_MS = base.MAX_WALL_MS
SAMPLE_DELAYS_MS = base.SAMPLE_DELAYS_MS
ORIGINAL_NEEDS_READINESS = base.needs_readiness
passive_samples = base.passive_samples
settled_suffix = base.settled_suffix
_owner = base._owner
RECIPE = {'schema': 'cua-native-save-passive-readiness-v20',
    'additional_input_trigger': 'Control+S', 'reused_capture_source': 'pre_observation_readiness_v18.py',
    'max_wall_ms': MAX_WALL_MS, 'sample_delays_ms': list(SAMPLE_DELAYS_MS),
    'required_samples': 7, 'required_settled_suffix': 4,
    'full_final_png_returned_unchanged': True, 'same_native_window_required': True,
    'exact_or_original_narrow_caret_required': True, 'action_retries': 0,
    'pixel_masking': False, 'max_actor_wall_seconds': 720}


def needs_readiness(action):
    return ORIGINAL_NEEDS_READINESS(action) or action['type'] == 'key' and action.get('key') == 'Control+S'


def dispatch(*args, **kwargs):
    with patch.object(base, 'needs_readiness', needs_readiness):return base.dispatch(*args, **kwargs)


def observe(*args, **kwargs):
    # Keep the same injection point used by offline latency tests; live capture
    # delegates to the original v18 function with its unchanged defaults.
    with patch.object(base, 'passive_samples', passive_samples):return base.observe(*args, **kwargs)


def audit_samples(*args, **kwargs):
    with patch.object(base, 'needs_readiness', needs_readiness):return base.audit_samples(*args, **kwargs)
