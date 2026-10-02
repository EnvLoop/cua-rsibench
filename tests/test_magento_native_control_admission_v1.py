"""TRAIN evidence precedes selection/final roster, native work and output creation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from magento_catalog_factory import native_surface_facade_v1 as facade


class ControlAdmissionTests(unittest.TestCase):
    def test_selection_and_final_controls_reopen_train_before_native_or_output(self):
        for split in ('selection', 'official_candidate'):
            with self.subTest(split=split), TemporaryDirectory() as temp:
                class Inputs:
                    binding = {'source': 'synthetic-current'}
                    def validate_train_admission(self):
                        raise ValueError('actual_current_train_proof_missing')
                    @property
                    def roster(self):
                        raise AssertionError('Roster must remain unopened before TRAIN admission')
                    def runtime(self):
                        raise AssertionError('Native constructor must not be called')
                output = Path(temp) / 'fresh-controls'
                with patch.object(facade, 'public_binding', return_value=Inputs.binding):
                    with self.assertRaisesRegex(ValueError, 'actual_current_train_proof_missing'):
                        facade.run_controls(inputs=Inputs(), split=split, output=output, enable_live=True)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
