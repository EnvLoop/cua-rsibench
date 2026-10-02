import json
from pathlib import Path
import tempfile
import unittest
from tools.office_owned_folder_spool_v2 import NativeOperationSpool
from tools.office_owned_folder_runtime_v2 import OfficeRuntimeError,canonical,write_new

class SpoolTests(unittest.TestCase):
 def test_response_timeout_preserves_one_use_unknown_intent(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700);admission=root/'source.private.json'
   write_new(admission,canonical({'schema':'office-owned-folder-native-host-source-review-v2','approved':True,'single_account':True,'graph_used':False,'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64}))
   ticks=iter([0,1]);spool=NativeOperationSpool(root/'spool',source_admission=admission,clock=lambda:next(ticks),deadline_seconds=0,poll_seconds=0)
   with self.assertRaisesRegex(OfficeRuntimeError,'uncertain'):spool.owned_folder_inventory()
   self.assertEqual(spool.sequence,1);directory=spool.root/'operation-0000';self.assertTrue((directory/'request.private.json').exists());self.assertTrue((directory/'terminal-uncertain.private.json').exists())
   self.assertFalse((directory/'response.private.json').exists());self.assertEqual(len(list(spool.root.glob('operation-*'))),1)

if __name__=='__main__':unittest.main()
