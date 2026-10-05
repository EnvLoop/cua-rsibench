"""Joined artifact processing while the existing clocked native request waits."""
from tools.office_clocked_typed_spool_v16 import NativeOperationSpool as Original
from tools.office_capture_crop_v17 import CropWorker

class NativeOperationSpool(Original):
 def request(self,operation,payload):
  with CropWorker(self):return super().request(operation,payload)
