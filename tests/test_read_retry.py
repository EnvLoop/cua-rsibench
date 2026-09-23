import unittest
from cursibench.read_retry import retry_read

class TimeoutException(Exception):pass

class ReadRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_recovers_but_action_never_replays(self):
        calls=[];notices=[]
        async def once():
            calls.append(1)
            if len(calls)<3:raise TimeoutException()
            return 'read-result'
        async def no_wait(_):pass
        result=await retry_read('curl -sf http://127.0.0.1:4318/observe',once,lambda *x:notices.append(x),no_wait)
        self.assertEqual(result,'read-result');self.assertEqual(len(calls),3);self.assertEqual(len(notices),2)
        calls.clear()
        with self.assertRaises(TimeoutException):
            await retry_read('curl -X POST http://127.0.0.1:4318/act',once,sleep=no_wait)
        self.assertEqual(len(calls),1)

    async def test_bound_and_real_errors(self):
        calls=[]
        async def timeout():calls.append(1);raise TimeoutException()
        async def no_wait(_):pass
        with self.assertRaises(TimeoutException):
            await retry_read('curl -sf http://127.0.0.1:4318/observe',timeout,sleep=no_wait)
        self.assertEqual(len(calls),3)
        calls.clear()
        async def broken():calls.append(1);raise ValueError('bad observation')
        with self.assertRaises(ValueError):
            await retry_read('curl -sf http://127.0.0.1:4318/observe',broken,sleep=no_wait)
        self.assertEqual(len(calls),1)
