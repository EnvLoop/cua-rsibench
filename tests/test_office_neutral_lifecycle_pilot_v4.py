"""Source gates only; no native host/provider operation."""
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from tools import office_neutral_lifecycle_pilot_v4 as pilot

class NeutralPilotTests(unittest.TestCase):
 def test_native_enable_is_required_before_any_private_read_or_host(self):
  with patch.object(pilot,'validate') as validate,patch.object(pilot,'NativeOperationSpool') as host:
   with self.assertRaises(ValueError):pilot.run(config_path=Path('/unused'),permit_path=Path('/unused'),enable_native=False)
   validate.assert_not_called();host.assert_not_called()
 def test_old_empty_or_forged_config_refuses_before_host(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'config.private.json';path.write_text('{}');path.chmod(0o600)
   with patch.object(pilot,'NativeOperationSpool') as host:
    with self.assertRaises((ValueError,KeyError)):pilot.run(config_path=path,permit_path=path,enable_native=True)
    host.assert_not_called()

if __name__=='__main__':unittest.main()
