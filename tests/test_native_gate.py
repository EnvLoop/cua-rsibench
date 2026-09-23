import unittest
from cursibench.native_campaign import gate
class GateTests(unittest.TestCase):
    def test_efficiency_requires_perfect_quality(self):
        base={'success_rate':1,'median_steps':50,'infrastructure_errors':0}
        self.assertTrue(gate(base,dict(base,median_steps=40))[0])
        self.assertFalse(gate(base,dict(base,success_rate=.9,median_steps=20))[0])
        self.assertFalse(gate(base,dict(base,median_steps=45))[0])
        self.assertFalse(gate(base,dict(base,median_steps=20,infrastructure_errors=1))[0])
