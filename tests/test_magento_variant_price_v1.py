"""Focused guards for five-variant Magento price qualification."""
import copy
import importlib.util
from pathlib import Path
import unittest
from urllib.parse import parse_qsl


TOOL = Path(__file__).resolve().parents[1] / 'tools/qualify_magento_variant_price_v1.py'
spec = importlib.util.spec_from_file_location('magento_variant_price_v1', TOOL)
qualify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualify)


def snapshot():
    ids = list(qualify.TARGETS) + list(qualify.WRONG)
    selected = {name: [] for name in qualify.RESTORE}
    selected['catalog_product_entity_decimal'] = [
        {'entity_id': key, 'attribute_id': qualify.PRICE_ATTR, 'store_id': 0,
         'value_id': key, 'value': '52.000000'} for key in ids]
    return {'tables': {name: {'rows': 1, 'sha256': 'baseline'} for name in qualify.MONITORED},
            'selected': selected, 'identities': []}


class MagentoVariantPriceTests(unittest.TestCase):
    def test_sanitized_har_excludes_login_and_other_product_fields(self):
        raw = {'log': {'entries': [
            {'request': {'url': 'http://localhost:7792/admin/admin/login/', 'method': 'POST',
                         'headers': [], 'postData': {'mimeType': 'application/x-www-form-urlencoded',
                                                    'text': 'username=admin&password=private'}},
             'response': {'status': 302, 'redirectURL': 'http://localhost:7792/admin/'}},
            {'request': {'url': 'http://localhost:7792/admin/catalog/product/save/id/111/type/simple/store/0/set/4/back/edit/key/secret/',
                         'method': 'POST', 'headers': [],
                         'postData': {'mimeType': 'application/x-www-form-urlencoded',
                                      'text': 'form_key=private&product%5Bprice%5D=47.00&product%5Bsku%5D=private'}},
             'response': {'status': 302, 'redirectURL': 'http://localhost:7792/admin/catalog/product/edit/id/111/'}}]}}
        clean = qualify.sanitize_har(raw)
        self.assertNotIn('private', str(clean))
        self.assertNotIn('secret', str(clean))
        self.assertNotIn('postData', clean['log']['entries'][0]['request'])
        post = clean['log']['entries'][1]['request']['postData']
        self.assertEqual(dict(parse_qsl(post['text'])), {'product[price]': '47.00'})

    def test_multipart_price_is_kept_without_form_key(self):
        post = {'mimeType': 'multipart/form-data; boundary=----boundary',
                'text': '------boundary\r\nContent-Disposition: form-data; name="form_key"\r\n\r\nprivate\r\n'
                        '------boundary\r\nContent-Disposition: form-data; name="product[price]"\r\n\r\n47.00\r\n'
                        '------boundary--\r\n'}
        self.assertEqual(qualify.price_from_post(post), '47.00')

    def test_positive_requires_all_five_green_variants_and_red_unchanged(self):
        before = snapshot()
        after = copy.deepcopy(before)
        for row in after['selected']['catalog_product_entity_decimal']:
            if row['entity_id'] in qualify.TARGETS:
                row['value'] = '47.000000'
        after['tables']['catalog_product_entity_decimal']['sha256'] = 'changed'
        qualify.validate_positive(before, after)
        after['selected']['catalog_product_entity_decimal'][0]['value'] = '52.000000'
        with self.assertRaisesRegex(ValueError, 'five target prices'):
            qualify.validate_positive(before, after)

    def test_wrong_color_fails_if_any_green_target_changes(self):
        before = snapshot()
        after = copy.deepcopy(before)
        for row in after['selected']['catalog_product_entity_decimal']:
            if row['entity_id'] == 112:
                row['value'] = '47.000000'
        qualify.validate_negative(before, after)
        after['selected']['catalog_product_entity_decimal'][0]['value'] = '47.000000'
        with self.assertRaisesRegex(ValueError, 'green target'):
            qualify.validate_negative(before, after)

    def test_reset_detects_unrelated_eav_drift(self):
        before = snapshot()
        after = copy.deepcopy(before)
        after['tables']['catalog_product_entity_varchar']['sha256'] = 'drift'
        with self.assertRaisesRegex(ValueError, 'monitored baseline'):
            qualify.validate_reset(before, after)


if __name__ == '__main__':
    unittest.main()
