import json,unittest
from cursibench.native_data_factory import alias_controls
class DataFactoryTests(unittest.TestCase):
 def test_control_alias_augmentation_preserves_facts(self):
  payload={'observation':{'text':'Issue GH-12 costs 17','controls':[{'id':'17','label':'Open GH-12'},{'id':'21','label':'Save'}]},'memory':'GH-12'}
  row={'record_id':3,'messages':[{'role':'user','content':'contract\n'+json.dumps(payload)},{'role':'assistant','content':json.dumps({'action':{'type':'click','control':'17'},'memory':'GH-12'})}]}
  augmented=alias_controls(row,1)
  after=json.loads(augmented['messages'][0]['content'].split('\n',1)[1]);action=json.loads(augmented['messages'][-1]['content'])
  self.assertEqual(after['observation']['text'],payload['observation']['text'])
  self.assertEqual(after['observation']['controls'][0]['id'],action['action']['control'])
  self.assertNotEqual(action['action']['control'],'17')
  self.assertEqual(action['memory'],'GH-12')
  self.assertEqual(payload['observation']['controls'][0]['id'],'17')
