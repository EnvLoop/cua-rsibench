"""Production GitLab native getter on synthetic local Chromium DOM only."""
import unittest
from playwright.async_api import async_playwright
from gitlab_world import v066_native_surface_adapter_v13 as adapter

class NativeHeaderDOMTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.p=await async_playwright().start();self.browser=await self.p.chromium.launch(headless=True)
  self.page=await self.browser.new_page(viewport={'width':1440,'height':1000})
  await self.page.route('**/*',lambda route:route.fulfill(body='<html></html>',content_type='text/html'))
  await self.page.goto('http://127.0.0.1:8018/group/project/-/project_members')
  await self.page.set_content('''<style>body{margin:0}button,a{display:block;width:140px;height:35px}main{position:absolute;left:300px;top:100px;width:800px;height:700px}header{padding:8px}</style>
   <header role="banner"><button id="global">Global account</button></header>
   <nav role="navigation"><a id="global-nav" href="/group/project/issues">Global navigation</a></nav>
   <aside class="super-sidebar"><button id="sidebar">Sidebar</button></aside>
   <main><header class="gl-page-header"><button id="invite"><span>Invite members</span></button>
    <a id="project-link" href="/group/project/issues">Project issues</a></header>
    <button id="disabled" disabled><span>Disabled nested span</span></button>
    <div aria-disabled="true"><button id="aria-disabled"><span>Ancestor disabled</span></button></div>
    <fieldset disabled><button id="fieldset"><span>Inherited disabled</span></button></fieldset>
    <div class="user-menu"><button id="account">Owned layout account menu</button></div>
    <a id="logout" href="/users/sign_out">Sign out</a>
    <a id="outside-project" href="/other/project/issues">Other project</a>
    <a id="external" href="https://outside.invalid">External link</a>
   </main><button id="outside">Outside content</button>
   <script>window.gon={current_user_id:17}</script>''')
 async def asyncTearDown(self):await self.browser.close();await self.p.stop()
 async def native(self,points=None):return await self.page.evaluate(adapter.META_JS,{'project':'/group/project','points':points or []})
 async def row(self,selector):
  native=await self.native();ref=await self.page.locator(selector).get_attribute('data-envloop-native-ref')
  return next(r for r in native['targets'] if r['ref']==ref)
 async def point(self,selector):
  b=await self.page.locator(selector).bounding_box();return {'x':round(b['x']+b['width']/2),'y':round(b['y']+b['height']/2)}
 async def test_owned_project_content_header_controls_are_enabled(self):
  self.assertTrue((await self.row('#invite'))['enabled']);self.assertTrue((await self.row('#project-link'))['enabled'])
  native=await self.native([await self.point('#invite span')]);self.assertTrue(native['hits'][0]['enabled'])
  self.assertEqual(native['schema'],'gitlab-native-surface-v13');self.assertEqual(native['account_uid'],'17')
 async def test_global_banner_sidebar_account_logout_and_other_navigation_disabled(self):
  for selector in ['#global','#global-nav','#sidebar','#account','#logout','#outside-project','#external','#outside']:
   with self.subTest(selector=selector):self.assertFalse((await self.row(selector))['enabled'])
 async def test_disabled_ancestors_and_physical_span_hits_stay_unsafe(self):
  for selector in ['#disabled','#aria-disabled','#fieldset']:
   with self.subTest(selector=selector):
    self.assertFalse((await self.row(selector))['enabled'])
    native=await self.native([await self.point(selector+' span')]);self.assertFalse(native['hits'][0]['enabled'])
 async def test_banner_inside_main_remains_protected(self):
  await self.page.locator('main').evaluate('(e)=>e.insertAdjacentHTML("beforeend",\'<header role="banner"><button id="banner-in-main">Global banner in layout</button></header>\')')
  self.assertFalse((await self.row('#banner-in-main'))['enabled'])
 async def test_owned_container_inside_global_header_does_not_make_header_safe(self):
  await self.page.locator('body').evaluate('(e)=>e.insertAdjacentHTML("beforeend",\'<header style="position:absolute;left:0;top:500px"><div class="page-content"><button id="nested-in-global-header">Outside header control</button></div></header>\')')
  self.assertFalse((await self.row('#nested-in-global-header'))['enabled'])
 async def test_generic_rule_has_no_task_or_answer_branch(self):
  self.assertNotIn('Invite',adapter.META_JS);self.assertNotIn('template_group',adapter.META_JS)
  self.assertNotIn('expected_',adapter.META_JS);self.assertNotIn('oracle',adapter.META_JS);self.assertNotIn('.value',adapter.META_JS)

if __name__=='__main__':unittest.main()
