"""Portable hydration, exclusion and refusal checks; no account or task data."""
import asyncio
from copy import deepcopy
import json
import shutil
import subprocess
import unittest

from cursibench import atomic_editor_matching as matching


LABEL = 'Example editor label'


def nodes():
    return [
        {'tag': 'DIV', 'role': 'code', 'bounds': [20, 30, 400, 200], 'painted': True,
         'documentReady': 'complete', 'editor_textareas': [{'tag': 'TEXTAREA', 'role': 'textbox',
         'label': LABEL, 'disabled': False, 'readonly': False}],
         'focus': {'tag': 'TEXTAREA', 'role': 'textbox', 'label': LABEL, 'inside_editor': True}},
        {'tag': 'DIV', 'role': None, 'bounds': [20, 230, 40, 20], 'painted': False,
         'documentReady': 'complete', 'editor_textareas': [],
         'focus': {'tag': 'TEXTAREA', 'role': 'textbox', 'label': LABEL, 'inside_editor': False}},
    ]


def snapshot(values=None, count=None):
    values = nodes() if values is None else values
    return {'schema': matching.SCHEMA, 'broad_count': len(values) if count is None else count,
        'role_code_target_count': sum(value['role'] == 'code' for value in values),
        'matching_nodes': deepcopy(values), 'url': 'https://example.invalid/editor',
        'documentReady': 'complete', 'readonly': True, 'native_input_performed': False}


class AtomicMatchingTests(unittest.TestCase):
    def test_count_and_full_facts_share_one_hydrated_array_with_exclusions(self):
        state = matching.project_snapshot(snapshot(), expected_label=LABEL)
        self.assertEqual(state['broad_count'], 2)
        self.assertEqual(state['eligible_count'], 1)
        self.assertEqual(state['excluded_matches'][0]['native_facts'], nodes()[1])
        self.assertFalse(state['unknown_matching_facts'])
        self.assertFalse(state['permission_granted'])
        self.assertEqual(matching.require_unique_known_editor(state), nodes()[0])

    def test_async_collection_has_no_separate_count_call(self):
        class HydratingLocator:
            async def count(self): raise AssertionError('independent count races hydration')
            async def evaluate_all(self, script):
                self.script = script
                return snapshot()
        locator = HydratingLocator()
        state = asyncio.run(matching.collect_snapshot(locator, expected_label=LABEL))
        self.assertEqual(locator.script, matching.SNAPSHOT_JS)
        self.assertEqual(state['broad_count'], 2)
        self.assertFalse(state['separate_matching_count_used'])

    def test_incomplete_and_overlimit_matching_facts_still_refuse(self):
        for value in (snapshot(count=1), snapshot([], count=9)):
            state = matching.project_snapshot(value, expected_label=LABEL)
            with self.assertRaisesRegex(ValueError, 'unknown_or_overlimit'):
                matching.require_unique_known_editor(state)

    def test_ambiguous_focused_editors_and_unfocused_code_editor_refuse(self):
        state = matching.project_snapshot(snapshot([nodes()[0], nodes()[0]]), expected_label=LABEL)
        with self.assertRaisesRegex(ValueError, 'multiple_eligible'):
            matching.require_unique_known_editor(state)
        value = nodes(); value[0]['focus']['inside_editor'] = False
        with self.assertRaisesRegex(ValueError, 'focus_target_drift'):
            matching.require_unique_known_editor(matching.project_snapshot(snapshot(value), expected_label=LABEL))

    def test_wrong_label_disabled_readonly_or_unpainted_editor_refuse(self):
        for change in ('label', 'disabled', 'readonly', 'painted'):
            values = nodes()
            if change == 'label': values[0]['editor_textareas'][0]['label'] = 'Different editor'
            elif change == 'painted': values[0]['painted'] = False
            else: values[0]['editor_textareas'][0][change] = True
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'drift'):
                matching.require_unique_known_editor(matching.project_snapshot(snapshot(values), expected_label=LABEL))

    def test_zero_matches_are_known_but_not_ready_and_metadata_is_not_mutated(self):
        value = snapshot([]); retained = deepcopy(value)
        state = matching.project_snapshot(value, expected_label=LABEL)
        self.assertEqual(value, retained)
        self.assertFalse(state['unknown_matching_facts'])
        with self.assertRaisesRegex(ValueError, 'not_ready'):
            matching.require_unique_known_editor(state)

    def test_incomplete_boolean_facts_cannot_be_treated_as_enabled_writable(self):
        for field in ('disabled', 'readonly'):
            value = nodes(); value[0]['editor_textareas'][0].pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'complete_typed'):
                matching.project_snapshot(snapshot(value), expected_label=LABEL)

    @unittest.skipUnless(shutil.which('node'), 'Node is required to execute the actual readonly callback')
    def test_actual_javascript_collects_both_facts_counts_and_roles_synchronously(self):
        setup = r'''
const doc={readyState:'complete',activeElement:null,elementFromPoint:()=>valid};
const field={tagName:'TEXTAREA',disabled:false,readOnly:false,getAttribute:(key)=>key==='role'?'textbox':LABEL};
doc.activeElement=field;globalThis.document=doc;globalThis.location={href:'https://example.invalid/editor'};
globalThis.getComputedStyle=(el)=>({display:el===tail?'none':'block',visibility:'visible'});
const valid={tagName:'DIV',isConnected:true,ownerDocument:doc,getAttribute:(key)=>key==='role'?'code':null,
matches:()=>true,getBoundingClientRect:()=>({x:20,y:30,width:400,height:200}),
querySelectorAll:()=>[field],contains:(el)=>el===field};
const tail={tagName:'DIV',isConnected:true,ownerDocument:doc,getAttribute:()=>null,matches:()=>false,
getBoundingClientRect:()=>({x:20,y:230,width:40,height:20}),querySelectorAll:()=>[],contains:()=>false};
process.stdout.write(JSON.stringify(collect([valid,tail])));
'''
        program = 'const LABEL=' + json.dumps(LABEL) + ';const collect=' + matching.SNAPSHOT_JS + ';\n' + setup
        result = subprocess.run(['node', '-'], input=program, text=True, capture_output=True, check=True)
        state = matching.project_snapshot(json.loads(result.stdout), expected_label=LABEL)
        self.assertEqual(state['broad_count'], 2)
        self.assertEqual(state['role_code_target_count'], 1)
        self.assertEqual(state['eligible_count'], 1)
        self.assertEqual(state['excluded_matches'][0]['native_facts']['editor_textareas'], [])
        matching.require_unique_known_editor(state)


if __name__ == '__main__': unittest.main()
