"""Keep the current clocked Actor and request deadline with typed lease checks."""
from tools.office_current_native_clock_v4 import CurrentOperationSpool
from tools.office_owned_folder_spool_v3 import NativeOperationSpool as TypedSpool

class NativeOperationSpool(CurrentOperationSpool,TypedSpool):
 pass
