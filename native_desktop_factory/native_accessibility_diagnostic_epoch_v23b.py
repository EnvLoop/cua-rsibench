"""Explicit source closure for a fresh read-only diagnostic guest epoch."""
from pathlib import Path
import hashlib
from .native_accessibility_diagnostic_v23b import FROZEN_SHA

FILES=('native_desktop_factory/native_accessibility_probe_v23.py','native_desktop_factory/native_accessibility_diagnostic_v23b.py',
 'native_desktop_factory/native_accessibility_diagnostic_epoch_v23b.py','tests/test_native_desktop_accessibility_diagnostic_v23b.py')

def proposal(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES}
 if sources[FILES[0]]!=FROZEN_SHA:raise ValueError('frozen_v23_probe_source_changed')
 return {'schema':'cua-native-accessibility-diagnostic-source-epoch-v23b','source_sha256s':sources,'frozen_probe_sha256':FROZEN_SHA,
  'fresh_owned_guest_required':True,'diagnostic_only':True,'native_mutations':0,'guard_relaxed':False,'model_dispatch_enabled':False,
  'native_qualification_claimed':False,'old_results_reclassified':False,'provider_calls_by_source_proposal':0}
