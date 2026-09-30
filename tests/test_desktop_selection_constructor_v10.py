"""Offline constructor/grammar/context tests; no provider or private gold."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from native_desktop_factory import selection_control_scripts_v10 as scripts
from native_desktop_factory import selection_control_successor_worker_v10 as successor
from native_desktop_factory import selection_control_successor_epoch_v10 as epoch
from native_desktop_factory import v066_post_enter_control_attempt_v9 as old_worker
from native_desktop_factory import v066_post_enter_control_audit_v9 as old_audit
from native_desktop_factory.v066_control_plan import compile_script


class ConstructorTests(unittest.TestCase):
 def test_all_one_and_two_target_calc_profiles_compile_with_target_only_near_miss(self):
  for workflow in ['calc-growth','calc-risk']:
   for count in [1,2]:
    sheet='Review' if count==1 else 'Two-factor review';cells=['B4'] if count==1 else ['B5','B6']
    targets={sheet+'!'+cell:{'formula':'='+str(index+2),'expected_value':index+2} for index,cell in enumerate(cells)}
    baseline={sheet:{cell:{'formula':'0'} for cell in cells}}
    for attempt in ['positive','near-miss','cold-reset']:
     script=scripts.script_from_layout(workflow=workflow,targets=targets,attempt=attempt,cells=baseline)
     actions,guards=compile_script(script)
     self.assertLessEqual(len(actions),90)
     if attempt!='cold-reset':self.assertEqual(guards['saved_artifact_readbacks'],1)
     else:self.assertEqual(actions,[])
    near=scripts.script_from_layout(workflow=workflow,targets=targets,attempt='near-miss',cells=baseline)
    self.assertIn('write =0',near)

 def test_calc_target_uses_one_fully_qualified_namebox_entry_then_plain_formula(self):
  for sheet,cells in [('Review',['B4']),('Two-factor review',['B5','B6'])]:
   targets={sheet+'!'+cell:{'formula':'=Evidence!D'+str(index+2)} for index,cell in enumerate(cells)}
   baseline={sheet:{cell:{'formula':'0'} for cell in cells}}
   for attempt in ['positive','near-miss']:
    script=scripts.script_from_layout(workflow='calc-growth',targets=targets,attempt=attempt,cells=baseline)
    self.assertEqual(script.count('click 52,170'),len(cells))
    for cell in cells:self.assertIn("write '"+sheet+"'."+cell+'\npress enter\nwait 1\nwrite =',script)
    self.assertNotIn('write '+sheet+'\n',script)
    for cell in cells:self.assertNotIn('write '+cell+'\n',script)
   positive=scripts.script_from_layout(workflow='calc-growth',targets=targets,attempt='positive',cells=baseline)
   self.assertIn('write =Evidence.D2',positive)

 def test_calc_reference_quotes_spaces_and_escapes_apostrophes(self):
  self.assertEqual(scripts.calc_cell_reference('Two-factor review','B5'),"'Two-factor review'.B5")
  self.assertEqual(scripts.calc_cell_reference("This year's sheet",'A1'),"'This year''s sheet'.A1")
  self.assertEqual(scripts.calc_cell_reference('Review','B4'),"'Review'.B4")
  for sheet,cell in [('Review\nwrite =9','B4'),('Review','B0'),('Review','B5\nwrite =9')]:
   with self.assertRaises(ValueError):scripts.calc_cell_reference(sheet,cell)

 def test_one_and_two_target_impress_profiles_compile(self):
  for count,slide_count,target_slide in [(1,4,3),(2,5,4)]:
   targets={'old-'+str(i):'new-'+str(i) for i in range(count)}
   slides=[[] for _ in range(slide_count)];slides[target_slide-1]=list(targets)
   for attempt in ['positive','near-miss','cold-reset']:
    script=scripts.script_from_layout(workflow='impress-deck',targets=targets,attempt=attempt,slides=slides,target_slide=target_slide)
    self.assertLessEqual(len(compile_script(script)[0]),90)

 def test_one_and_two_target_writer_profiles_reuse_visible_replace_guards(self):
  for count in [1,2]:
   targets={'old-'+str(i):'new-'+str(i) for i in range(count)}
   script=scripts.script_from_layout(workflow='writer-brief',targets=targets,attempt='positive',paragraphs=list(targets))
   actions,guards=compile_script(script);self.assertLessEqual(len(actions),90)
   self.assertEqual(guards['visible_window_assertions'],count*5)
   self.assertEqual(script.count('press ctrl,h'),count)

 def test_final_scripts_delegate_byte_for_byte_without_selection_logic(self):
  oracle={'split':'final_candidate','workflow':'calc-growth','targets':{'opaque':'opaque'}}
  with patch.object(scripts.historical,'actor_script',return_value='unchanged-final-script\n') as call:
   self.assertEqual(scripts.actor_script(Path('/sealed'),oracle,'positive'),'unchanged-final-script\n')
  call.assert_called_once_with(Path('/sealed'),oracle,'positive')

 def test_invalid_selection_shapes_fail_before_any_script_dispatch(self):
  for targets in [{},{'bad!B5':{'formula':'=1'},'bad!B6':{'formula':'=2'}},{'Two-factor review!B6':{'formula':'=1'}}]:
   with self.assertRaises(ValueError):scripts.script_from_layout(workflow='calc-growth',targets=targets,attempt='positive',cells={})

 def test_successor_paid_gate_precedes_all_private_reads(self):
  with patch.object(epoch,'validate',side_effect=AssertionError('Must not read private inputs')):
   with self.assertRaisesRegex(ValueError,'disabled'):successor.run_trio(freeze_path=Path('/absent'),permit_path=Path('/absent'))

 def test_process_context_installs_new_constructor_for_execution_and_audit_then_restores(self):
  original_worker_script=old_worker.actor_script;original_audit_script=old_audit.actor_script;original_worker_epoch=old_worker.epoch
  with successor.context():
   self.assertIs(old_worker.actor_script,scripts.actor_script);self.assertIs(old_audit.actor_script,scripts.actor_script)
   self.assertIs(old_worker.epoch,epoch);self.assertIs(old_audit.epoch,epoch)
  self.assertIs(old_worker.actor_script,original_worker_script);self.assertIs(old_audit.actor_script,original_audit_script)
  self.assertIs(old_worker.epoch,original_worker_epoch)

 def test_layout_metadata_reader_never_opens_oracle_or_instruction(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);(root/'dummy.xlsx').write_bytes(b'opaque actor input')
   # Layout inspection reads only the actor-visible input parser.
   data={'Evidence ledger':{},'Two-factor review':{'B5':{'formula':'wrong'},'B6':{'formula':'wrong'}},'Method':{}}
   with patch.object(scripts,'xlsx_cells',return_value=data):
    result=scripts.selection_layout_metadata(root,{'workflow':'calc-growth','package_sha256':'a'*64,'template_group':'selection'})
   self.assertTrue(result['layout_checked_without_oracle']);self.assertEqual(result['profile']['targets'],2)
   self.assertEqual(result['namebox_cell_references'],["'Two-factor review'.B5","'Two-factor review'.B6"])


if __name__=='__main__':unittest.main()
