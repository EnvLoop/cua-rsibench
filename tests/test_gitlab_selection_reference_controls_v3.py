"""Proved CSV layout and bounded local Chromium regressions; no runtime."""
import asyncio,copy,time,unittest
from pathlib import Path
from hashlib import sha256
from types import SimpleNamespace
from playwright.async_api import async_playwright
from gitlab_world import v066_selection_reference_controls_v3 as c

TARGET=['unit-asset','unit-cve','vendor','product','site','active']
NATIVE={'tag':'TABLE','role':'table','classes':'table b-table gl-table'}


class CsvTests(unittest.TestCase):
    def test_exact_actual_preview_and_semantic_layout(self):
        self.assertTrue(c.csv_layout(['0','1','2','3','4','5'],[c.FIELDS,TARGET],NATIVE,TARGET)['ready'])
        self.assertTrue(c.csv_layout(c.FIELDS,[TARGET],NATIVE,TARGET)['ready'])

    def test_wrong_indices_header_native_layout_incomplete_duplicate_target_and_disposition_refuse(self):
        cases=[(['1','2','3','4','5','6'],[c.FIELDS,TARGET],NATIVE),
               (['0','1','2','3','4','5'],[['wrong',*c.FIELDS[1:]],TARGET],NATIVE),
               (['0','1','2','3','4','5'],[c.FIELDS,TARGET],NATIVE|{'role':None}),
               (['0','1','2','3','4','5'],[c.FIELDS,TARGET],NATIVE|{'classes':'other-table'}),
               (c.FIELDS,[TARGET[:-1]],NATIVE),(c.FIELDS,[TARGET,TARGET],NATIVE),
               (c.FIELDS,[TARGET[:-1]+['watch']],NATIVE)]
        for headers,rows,native in cases:
            with self.subTest(headers=headers,rows=rows):self.assertFalse(c.csv_layout(headers,rows,native,TARGET)['ready'])

    def test_consumed_sources_recipes_defaults_and_native146_unchanged(self):
        self.assertEqual(sha256(Path(c.prior.__file__).read_bytes()).hexdigest(),c.PARENT_SHA)
        self.assertEqual(c.workflow.__code__.co_code,c.prior.workflow.__code__.co_code)
        self.assertEqual(c._readable.__kwdefaults__,c.prior._readable.__kwdefaults__)
        self.assertEqual(c.models.public_binding()['binding_sha256'],'07c1520799c160d4394f9f943601a83f18da825f0ce87b2faa776c66878608be')

    def test_actual_local_chromium_current_preview_stability_and_private_refusal_samples(self):
        async def run():
            async with async_playwright() as p:
                browser=await p.chromium.launch(headless=True)
                try:
                    page=await browser.new_page();await page.route('**/*',lambda r:r.abort())
                    records=[];active=SimpleNamespace(page=page,project_path='/owned/project',original_task={'project_family':'owned/project'},
                        guard=SimpleNamespace(lease={'expires_at':time.monotonic()+2},store=SimpleNamespace(json=lambda *args:records.append(args))))
                    html='<table role="table" class="table b-table gl-table"><thead><tr>'+''.join('<th>'+str(i)+'</th>' for i in range(6))+'</tr></thead><tbody><tr>'+''.join('<td>'+s+'</td>' for s in c.FIELDS)+'</tr><tr>'+''.join('<td>'+s+'</td>' for s in TARGET)+'</tr></tbody></table>'
                    await page.set_content(html);await c._readable(active,page.get_by_role('table'),[],table=True,target_row=TARGET)
                    self.assertFalse(records)
                    for bad in (html.replace('<th>0</th>','<th>9</th>'),html.replace('<td>asset_id</td>','<td>unknown</td>'),html.replace('<td>site</td>','<td></td>'),html+html):
                        await page.set_content(bad);active.guard.lease['expires_at']=time.monotonic()+.04
                        with self.assertRaises((ValueError,TimeoutError)) as caught:
                            await c._readable(active,page.get_by_role('table'),[],table=True,target_row=TARGET)
                        self.assertTrue(hasattr(caught.exception,'csv_readiness_samples'))
                    self.assertEqual(len(records),4)
                    await page.set_content(html);active.guard.lease['expires_at']=time.monotonic()+1
                    with self.assertRaisesRegex(ValueError,'original_project_uri'):
                        await c._readable(active,page.get_by_role('table'),[],table=True,target_row=TARGET,
                            relative='/-/blob/main/security/kev-register.csv')
                finally:await browser.close()
        asyncio.run(run())


if __name__=='__main__':unittest.main()
