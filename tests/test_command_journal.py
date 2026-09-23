import hashlib,shlex,sys,tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from cursibench.command_journal import execute

class JournalTests(unittest.TestCase):
    def test_lost_response_and_concurrent_retry_execute_once(self):
        with tempfile.TemporaryDirectory() as root:
            counter=Path(root)/'counter'
            code=f"from pathlib import Path; p=Path({str(counter)!r}); p.write_text(p.read_text()+'x' if p.exists() else 'x'); print('saved')"
            command=shlex.quote(sys.executable)+' -c '+shlex.quote(code)
            with ThreadPoolExecutor(max_workers=3) as pool:
                results=list(pool.map(lambda _:execute(root,'a'*32,command,5),range(3)))
            self.assertEqual(counter.read_text(),'x')
            self.assertEqual(results,[{'stdout':'saved\n','stderr':'','return_code':0}]*3)
            with self.assertRaises(ValueError):execute(root,'a'*32,'different command',5)

    def test_crash_after_intent_never_reexecutes(self):
        with tempfile.TemporaryDirectory() as root:
            command='printf should-not-run'
            (Path(root)/('b'*32+'.intent')).write_text(hashlib.sha256(command.encode()).hexdigest())
            with self.assertRaisesRegex(RuntimeError,'refusing to replay'):
                execute(root,'b'*32,command,5)
            self.assertFalse((Path(root)/('b'*32+'.json')).exists())
