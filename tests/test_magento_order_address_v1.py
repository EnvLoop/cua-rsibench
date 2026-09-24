"""Focused guards for the isolated Magento address qualification."""
import copy
import importlib.util
from pathlib import Path
import unittest
from urllib.parse import parse_qsl


TOOL = Path(__file__).resolve().parents[1] / 'tools/qualify_magento_order_address_v1.py'
spec = importlib.util.spec_from_file_location('magento_order_address_v1', TOOL)
qualify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualify)


class MagentoOrderAddressQualificationTests(unittest.TestCase):
    def test_har_redaction_preserves_observed_address_post_only(self):
        raw = {'log': {'entries': [
            {'request': {'url': 'http://localhost:7790/admin/admin/login/', 'method': 'POST',
                         'headers': [], 'postData': {'mimeType': 'application/x-www-form-urlencoded',
                                                    'text': 'username=admin&password=private'}},
             'response': {'status': 302, 'redirectURL': 'http://localhost:7790/admin/'}},
            {'request': {'url': 'http://localhost:7790/admin/sales/order/addressSave/address_id/598/key/secret/',
                         'method': 'POST', 'headers': [],
                         'postData': {'mimeType': 'application/x-www-form-urlencoded',
                                      'text': 'form_key=private&street%5B0%5D=456+Oak+Avenue&'
                                              'street%5B1%5D=Apartment+5B&country_id=US&region=New+York&'
                                              'region_id=43&city=New+York&postcode=10001'}},
             'response': {'status': 302, 'redirectURL': 'http://localhost:7790/admin/sales/order/view/order_id/299/'}}]}}
        clean = qualify.sanitize_har(raw)
        self.assertNotIn('private', str(clean))
        self.assertNotIn('secret', str(clean))
        self.assertNotIn('postData', clean['log']['entries'][0]['request'])
        post = clean['log']['entries'][1]['request']['postData']
        self.assertEqual(dict(parse_qsl(post['text'])), qualify.ADDRESS)
        self.assertEqual(clean['log']['entries'][1]['response']['status'], 302)

    def test_reset_rejects_order_grid_drift_even_when_address_row_matches(self):
        before = {'tables': {name: {'rows': 1, 'sha256': 'a'} for name in qualify.TABLES},
                  'rows': {'598': {'street': 'old'}, '600': {'street': 'old'}},
                  'grid_rows': {'299': {'billing_address': 'old'},
                                '300': {'billing_address': 'old'}}}
        after = copy.deepcopy(before)
        after['tables']['sales_order_grid']['sha256'] = 'b'
        after['grid_rows']['299']['billing_address'] = 'new'
        with self.assertRaisesRegex(ValueError, 'baseline hashes'):
            qualify.validate_reset(before, after)
        after = copy.deepcopy(before)
        qualify.validate_reset(before, after)


if __name__ == '__main__':
    unittest.main()
