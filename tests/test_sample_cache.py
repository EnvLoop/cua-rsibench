import unittest
from cursibench.sample_cache import SamplingCache
class CacheTests(unittest.TestCase):
 def test_network_retries_do_not_repeat_sampling(self):
  cache=SamplingCache();calls=[];future=object()
  def start():calls.append(1);return future
  first,reused=cache.get('request-001','prompt',start)
  again,reused=cache.get('request-001','prompt',start)
  self.assertIs(first,again);self.assertTrue(reused);self.assertEqual(len(calls),1)
  with self.assertRaises(ValueError):cache.get('request-001','changed',start)
 def test_cache_is_bounded(self):
  cache=SamplingCache(limit=1);cache.get('request-001','one',lambda:object())
  with self.assertRaises(ValueError):cache.get('request-002','two',lambda:object())

class MultiTaskCacheTests(unittest.TestCase):
 def test_capacity_covers_full_multi_task_action_budget(self):
  from cursibench.sample_cache import request_capacity
  capacity=request_capacity(3)
  self.assertEqual(capacity,270)
  cache=SamplingCache(limit=capacity);calls=[]
  for i in range(270):cache.get(f'request-{i:04}',str(i),lambda:calls.append(1))
  _,reused=cache.get('request-0000','0',lambda:calls.append(1))
  self.assertTrue(reused);self.assertEqual(len(calls),270)
  with self.assertRaises(ValueError):cache.get('request-0270','overflow',lambda:None)
