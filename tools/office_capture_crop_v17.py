"""Artifact-only one-use full-image crop worker; never controls a UI."""
import io,json,threading,time
from pathlib import Path
from PIL import Image,__version__ as pillow_version
from tools import office_owned_folder_runtime_v2 as old

SCHEMA='office-native-full-capture-crop-v17'

def crop_bytes(raw,clip):
 old.require(type(clip) is dict and set(clip)=={'x','y','width','height'} and all(type(v) is int for v in clip.values()) and clip['x']>=0 and clip['y']>=0 and clip['width']>0 and clip['height']>0,'Exact native crop rectangle required')
 old.require(0<len(raw)<=10000000,'Native full capture byte bound')
 with Image.open(io.BytesIO(raw)) as image:
  old.require(image.format in ('JPEG','PNG') and image.mode in ('RGB','RGBA') and image.width*image.height<=20000000,'Native full capture format unsupported')
  image.load();x,y,w,h=[clip[k] for k in ('x','y','width','height')]
  old.require(x+w<=image.width and y+h<=image.height,'Native crop rectangle outside full capture')
  cropped=image.crop((x,y,x+w,y+h));out=io.BytesIO();cropped.save(out,format='PNG')
  return out.getvalue(),{'schema':SCHEMA,'full_sha256':old.sha(raw),'full_size':len(raw),'full_format':image.format,'full_dimensions':[image.width,image.height],'clip':clip,'crop_dimensions':[w,h],'decoded_mode':image.mode,'full_decoded_pixel_sha256':old.sha(image.tobytes()),'crop_decoded_pixel_sha256':old.sha(cropped.tobytes()),'processor':'Pillow','processor_version':pillow_version,'rescale':False,'one_full_native_capture':True}

class CropWorker:
 def __init__(self,spool):
  self.root=Path(spool.root)/'capture-crops.private';self.root.mkdir(mode=0o700,exist_ok=True)
  old.require(not self.root.is_symlink() and not self.root.stat().st_mode&0o077,'Owned private crop spool required')
  self.clip=spool.admission['capture_clip'];self.stop=threading.Event();self.thread=None;self.error=None
 def process(self):
  for job in sorted(self.root.glob('capture-*')):
   if self.stop.is_set():return
   request=job/'request.private.json';response=job/'response.private.json'
   if not request.exists() or response.exists():continue
   old.require(job.is_dir() and not job.is_symlink() and not job.stat().st_mode&0o077,'Private capture job required')
   rb=old.private(request);body=json.loads(rb)
   try:
    old.require(set(body)=={'schema','full_sha256','full_size','clip','one_use'} and body['schema']==SCHEMA and body['clip']==self.clip and body['one_use'] is True,'Native crop request binding changed')
    raw=old.private(job/'full.image');old.require(old.sha(raw)==body['full_sha256'] and len(raw)==body['full_size'],'Native full capture bytes changed')
    cropped,proof=crop_bytes(raw,self.clip);proof.update(crop_sha256=old.sha(cropped),crop_size=len(cropped),request_sha256=old.sha(rb))
    old.write_new(job/'cropped.png',cropped);old.write_new(job/'proof.private.json',old.canonical(proof));result={'schema':SCHEMA,'status':'completed','request_sha256':old.sha(rb),'crop_sha256':old.sha(cropped),'crop_size':len(cropped),'proof_sha256':old.sha(old.canonical(proof))}
   except Exception as error:result={'schema':SCHEMA,'status':'failed','request_sha256':old.sha(rb),'error_class':type(error).__name__,'error_code_sha256':old.sha(str(error).encode())}
   old.write_new(response,old.canonical(result))
 def run(self):
  try:
   while not self.stop.wait(.025):self.process()
  except Exception as error:self.error=error
 def __enter__(self):
  self.thread=threading.Thread(target=self.run,name='owned-artifact-crop',daemon=False);self.thread.start();return self
 def __exit__(self,*args):
  self.stop.set();self.thread.join(2);old.require(not self.thread.is_alive(),'Artifact crop worker did not join')
  if self.error is not None:raise self.error
