import io,json,tempfile,threading,time,unittest
from pathlib import Path
from PIL import Image
from tools import office_owned_folder_runtime_v2 as old
from tools.office_capture_crop_v17 import SCHEMA,crop_bytes,CropWorker
from tools.office_crop_spool_v17 import NativeOperationSpool

class CaptureCropTests(unittest.TestCase):
 def image(self):
  image=Image.new('RGB',(32,24));image.putdata([(x*7,y*9,(x+y)*4) for y in range(24) for x in range(32)]);out=io.BytesIO();image.save(out,format='JPEG',quality=97);return out.getvalue()
 def fixture(self,timeout=.5):
  root=Path(tempfile.mkdtemp()).resolve();root.chmod(0o700);admission=root/'admission.private.json';clip={'x':0,'y':6,'width':32,'height':18}
  old.write_new(admission,old.canonical({'schema':'office-owned-folder-native-host-source-review-v2','approved':True,'single_account':True,'graph_used':False,'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64,'capture_clip':clip}))
  host=NativeOperationSpool(root/'spool.private',source_admission=admission,deadline_seconds=timeout,poll_seconds=.01);return host,clip
 def test_actual_JPEG_decoded_crop_exact_pixels_and_header_exclusion(self):
  raw=self.image();clip={'x':0,'y':6,'width':32,'height':18};cropped,proof=crop_bytes(raw,clip)
  full=Image.open(io.BytesIO(raw));result=Image.open(io.BytesIO(cropped));self.assertEqual(result.tobytes(),full.crop((0,6,32,24)).tobytes());self.assertEqual(proof['crop_decoded_pixel_sha256'],old.sha(result.tobytes()));self.assertEqual(result.size,(32,18));self.assertFalse(proof['rescale'])
 def test_concurrent_actual_request_crop_response_and_join(self):
  host,clip=self.fixture();raw=self.image();finished=[]
  def pump():
   directory=host.root/'operation-0000'
   while not (directory/'request.private.json').exists():time.sleep(.005)
   rb=old.private(directory/'request.private.json');request=json.loads(rb);job=host.root/'capture-crops.private/capture-0000';job.mkdir(mode=0o700);old.write_new(job/'full.image',raw);old.write_new(job/'request.private.json',old.canonical({'schema':SCHEMA,'full_sha256':old.sha(raw),'full_size':len(raw),'clip':clip,'one_use':True}))
   while not (job/'response.private.json').exists():time.sleep(.005)
   response=json.loads(old.private(job/'response.private.json'));self.assertEqual(response['status'],'completed');proof=json.loads(old.private(job/'proof.private.json'));self.assertEqual(proof['full_sha256'],old.sha(raw))
   old.write_new(directory/'response.private.json',old.canonical({'schema':'office-owned-folder-operation-response-v2','request_sha256':old.sha(rb),'sequence':0,'operation':request['operation'],'status':'completed','result':{'artifact_only_crop_completed':True}}));finished.append(True)
  thread=threading.Thread(target=pump);thread.start();self.assertEqual(host.request('actor_open',{}),{'artifact_only_crop_completed':True});thread.join(1);self.assertFalse(thread.is_alive());self.assertEqual(finished,[True]);self.assertFalse(any(t.name=='owned-artifact-crop' and t.is_alive() for t in threading.enumerate()))
 def test_tampered_full_image_fails_and_worker_joins(self):
  host,clip=self.fixture();worker=CropWorker(host);job=worker.root/'capture-0000';job.mkdir(mode=0o700);raw=self.image();old.write_new(job/'full.image',raw);old.write_new(job/'request.private.json',old.canonical({'schema':SCHEMA,'full_sha256':'f'*64,'full_size':len(raw),'clip':clip,'one_use':True}))
  with worker:
   end=time.monotonic()+1
   while not (job/'response.private.json').exists() and time.monotonic()<end:time.sleep(.005)
  self.assertEqual(json.loads(old.private(job/'response.private.json'))['status'],'failed');self.assertFalse(worker.thread.is_alive());self.assertFalse((job/'cropped.png').exists())
 def test_request_timeout_no_orphan_and_wrong_rectangle(self):
  host,clip=self.fixture(timeout=.05)
  with self.assertRaises(ValueError):host.request('actor_open',{})
  self.assertFalse(any(t.name=='owned-artifact-crop' and t.is_alive() for t in threading.enumerate()))
  with self.assertRaises(ValueError):crop_bytes(self.image(),{**clip,'width':33})
 def test_malformed_private_request_exits_and_joins_without_response(self):
  host,clip=self.fixture();worker=CropWorker(host);job=worker.root/'capture-0000';job.mkdir(mode=0o700);old.write_new(job/'request.private.json',b'{')
  with self.assertRaises(ValueError):
   with worker:
    end=time.monotonic()+1
    while worker.error is None and time.monotonic()<end:time.sleep(.005)
  self.assertFalse(worker.thread.is_alive());self.assertFalse((job/'response.private.json').exists())
if __name__=='__main__':unittest.main()
