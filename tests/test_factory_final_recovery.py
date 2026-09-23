import unittest
from cursibench.factory_final_recovery import replace_build_failures

class FinalRecoveryTests(unittest.TestCase):
    def test_only_build_failed_rows_are_replaced(self):
        original={'tasks':[{'task':'a','score':0.,'error_type':None},{'task':'b','score':None,'error_type':'BuildException'}]}
        recovered=replace_build_failures(original,[{'task':'b','score':1.,'error_type':None}],['a','b'])
        self.assertEqual(recovered['score'],.5);self.assertIsNone(original['tasks'][1]['score'])
        with self.assertRaisesRegex(ValueError,'exactly'):
            replace_build_failures(original,[{'task':'a','score':1.,'error_type':None}],['a','b'])
    def test_retry_failure_remains_unscored(self):
        original={'tasks':[{'task':'a','score':None,'error_type':'BuildException'}]}
        result=replace_build_failures(original,[{'task':'a','score':None,'error_type':'ConnectError'}],['a'])
        self.assertIsNone(result['score']);self.assertEqual(result['status'],'infrastructure_error')
