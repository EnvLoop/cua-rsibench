import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from gitlab_world.v066_uniform_reference_controls_v13 import Locator, Page


class GuardedReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_placeholder_lookup_keeps_the_guarded_locator(self):
        original=SimpleNamespace(get_by_placeholder=lambda *args,**kwargs:object())
        active=SimpleNamespace(page=original)
        page=Page(active)
        self.assertIsInstance(page.get_by_placeholder('Search',exact=True),Locator)
        parent=Locator(original,active)
        self.assertIsInstance(parent.get_by_placeholder('Search',exact=True),Locator)

    async def test_missing_painted_control_never_observes_or_dispatches(self):
        native=SimpleNamespace(element_handles=AsyncMock(return_value=[object(),object()]))
        guard=SimpleNamespace(observe=AsyncMock(),dispatch=AsyncMock())
        active=SimpleNamespace(guard=guard,page=object())
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            await Locator(native,active).click()
        guard.observe.assert_not_awaited()
        guard.dispatch.assert_not_awaited()


if __name__=='__main__':unittest.main()
