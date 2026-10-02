import unittest
from types import SimpleNamespace
from native_desktop_factory.native_client_coordinate_probe import absolute_client_geometry

class ClientCoordinatesTests(unittest.TestCase):
 def source(self,text):
  return SimpleNamespace(command=lambda argv:text)
 def test_actual_absolute_client_origin_keeps_native_window_identity(self):
  text='xwininfo: Window id: 0x2e000e3 "owned document"\n Absolute upper-left X: 0\n Absolute upper-left Y: 51\n Width: 1280\n Height: 749'
  value=absolute_client_geometry(self.source(text),{'window_id':str(int('2e000e3',16))})
  self.assertEqual((value['X'],value['Y'],value['WIDTH'],value['HEIGHT']),(0,51,1280,749))
  self.assertEqual(value['source'],'xwininfo_absolute_client_origin')
 def test_other_window_missing_origin_and_zero_dimensions_reject(self):
  text='Window id: 0x10\nAbsolute upper-left X: 0\nAbsolute upper-left Y: 51\nWidth: 1280\nHeight: 749'
  for raw,window in [(text,'17'),(text.replace('Absolute upper-left Y: 51','Relative upper-left Y: 51'),'16'),(text.replace('Height: 749','Height: 0'),'16')]:
   with self.assertRaises(ValueError):absolute_client_geometry(self.source(raw),{'window_id':window})
if __name__=='__main__':unittest.main()
