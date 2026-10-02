"""Scroll bypasses no guard: disabled current pixels are excluded."""
import asyncio,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
from magento_catalog_factory import native_reference_bulk_price_v6 as reference

class ScrollReferenceTests(unittest.TestCase):
 def test_safe_native_point_replaces_disabled_textarea_coordinate(self):
  async def run():
   unsafe={'visible':True,'enabled':False,'obscured':False,'actions':['scroll']}
   safe={**unsafe,'enabled':True}
   adapter=SimpleNamespace(meta=AsyncMock(return_value={'hits':[unsafe,safe,unsafe,unsafe,unsafe]}),actor=SimpleNamespace(check=Mock()))
   ctrl=SimpleNamespace(adapter=adapter);obs=SimpleNamespace(screenshot={'width':1440,'height':1000})
   with patch.object(reference.parent,'control_sample',new=AsyncMock(return_value={'type':'scroll','target':{'x':1200,'y':900},'dx':0,'dy':600})):
    value=await reference.control_sample(ctrl,obs);self.assertEqual(value['target'],{'x':1152,'y':500})
    adapter.meta.return_value={'hits':[unsafe]*5}
    with self.assertRaisesRegex(ValueError,'no_current_safe_scroll_surface'):await reference.control_sample(ctrl,obs)
  asyncio.run(run())

if __name__=='__main__':unittest.main()
