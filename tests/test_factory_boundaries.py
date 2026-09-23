import json,tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from cursibench.factory_budget import Budget
from cursibench.factory_worker import resolve_path

class FactoryBoundaryTests(unittest.TestCase):
    def test_budget_is_idempotent_atomic_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.jsonl';budget=Budget(path,{'rollouts':2})
            def reserve(i):
                try:budget.reserve('rollouts',1,str(i));return True
                except ValueError:return False
            with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(reserve,range(4)))
            self.assertEqual(sum(results),2)
            row=json.loads(path.read_text().splitlines()[1]);budget.reserve('rollouts',1,row['request_id'])
            self.assertEqual(budget.snapshot()['reserved']['rollouts'],2)
            with self.assertRaises(ValueError):budget.reserve('rollouts',2,row['request_id'])
            text=path.read_text().replace('"amount": 1','"amount": 0',1);path.write_text(text)
            with self.assertRaisesRegex(ValueError,'integrity'):budget.snapshot()

    def test_paths_reject_traversal_symlink_and_input_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace=root/'workspace';inputs=root/'inputs';workspace.mkdir();inputs.mkdir()
            secret=root/'secret';secret.write_text('private');(workspace/'escape').symlink_to(root)
            for path,write in [('../secret',False),('/etc/passwd',False),('escape/secret',False),('inputs/sources.json',True),('factory.py; echo x',False)]:
                with self.subTest(path=path),self.assertRaises(ValueError):resolve_path(path,write,workspace,inputs)
            self.assertEqual(resolve_path('src/generate.py',True,workspace,inputs),(workspace/'src/generate.py').resolve())
            self.assertEqual(resolve_path('inputs/sources.json',False,workspace,inputs),(inputs/'sources.json').resolve())

    def test_resume_cursor_keeps_interrupted_calls_charged(self):
        with tempfile.TemporaryDirectory() as tmp:
            budget=Budget(Path(tmp)/'ledger.jsonl',{'researcher_calls':5})
            budget.reserve('researcher_calls',1,'researcher:0:0')
            budget.reserve('researcher_calls',1,'researcher:1:0')
            self.assertEqual(budget.next_research_turn(),2)
            self.assertEqual(budget.snapshot()['reserved']['researcher_calls'],2)
        with self.assertRaises(ValueError):resolve_path('.')
