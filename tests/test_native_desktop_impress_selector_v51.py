"""Offline captured Impress selector boundaries; no qualification credit."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import time
import unittest
import warnings
import json

from native_desktop_factory import native_editor_capability_v42 as build
from native_desktop_factory import native_editor_runtime_v50 as old_runtime
from native_desktop_factory import native_editor_reader_v50 as old_reader
from native_desktop_factory import native_impress_selector_capability_v51 as capability
from native_desktop_factory import native_editor_reader_v51 as reader
from native_desktop_factory import native_editor_runtime_v51 as runtime
from cursibench import native_surface_guard_policy_v1 as guard


ROOT = Path(__file__).resolve().parents[1]


def flags(*, sensitive=True, focused=False):
    # Retained public TRAIN slide-sorter shape metadata; no task body or IDs.
    return {
        'ENABLED': True, 'SENSITIVE': sensitive, 'VISIBLE': True,
        'SHOWING': True, 'EDITABLE': False, 'FOCUSED': focused,
        'STALE': False, 'DEFUNCT': False, 'MANAGES_DESCENDANTS': False,
    }


def mode():
    return {
        'schema': 'owned-current-edit-mode-evidence-v42',
        'document_binding_sha256': 'a' * 64,
        'observed_at': 1., 'expires_at': 10.9,
        'visible_initial_native_proof': True,
        'same_native_node_reopened': True, 'current_native_state_read': True,
        'unique_current_command': True, 'command': '.uno:EditDoc',
        'name': 'Edit Mode', 'parent_menu': 'Edit', 'checked': True,
        'enabled': True, 'sensitive': True, 'stale': False, 'defunct': False,
        'node_identity_sha256': 'b' * 64,
    }


def args():
    return {
        'build': deepcopy(build.BUILD), 'raw_flags': flags(),
        'ancestors': [('panel', flags()),
                      ('document frame', flags(sensitive=False)),
                      ('frame', flags())],
        'selector': {
            'name': 'Slides View', 'description': 'This is where you sort slides.',
            'role': 'document frame',
            'identity': {'available': True, 'identity_sha256': 'c' * 64},
            'child_count': 4, 'selection_interface_available': True,
            'ACTIVE': True, 'SELECTABLE': True, 'FOCUSABLE': True,
            'MULTISELECTABLE': True,
        },
        'mode': mode(),
        'context': {
            'document_binding_sha256': 'a' * 64,
            **{key: True for key in (
                'owned_current_principal', 'same_current_impress_document',
                'strict_zero_child_shape', 'strict_physical_leaf_identity_proved',
                'unobscured', 'original_file_writable', 'original_medium_writable',
                'current_application_is_writable',
                'current_selection_interface_read', 'shape_active',
                'shape_selectable', 'shape_focusable')},
        },
        'now': 2.,
    }


class SelectorBoundaries(unittest.TestCase):
    def test_retained_actual_shape_is_click_only_without_flag_or_focus_override(self):
        values = args()
        snapshot = deepcopy(values)
        proof = capability.selector_capability(**values)
        self.assertEqual(values, snapshot)
        self.assertEqual(proof['raw_native_flags'], values['raw_flags'])
        self.assertTrue(proof['effective_pointer_eligible'])
        self.assertEqual(proof['allowed_actions'], ['click'])
        self.assertFalse(proof['effective_keyboard_eligible'])
        self.assertFalse(proof['native_focused_override'])
        self.assertTrue(proof['actual_lease_required_by_unchanged_dispatch_guard'])
        target = guard.NativeTarget('slide', (11, 378, 158, 82), True, True,
                                    False, False, tuple(proof['allowed_actions']))
        envelope = SimpleNamespace(targets=[target])
        self.assertTrue(guard._safe_target({'ref': 'slide'}, envelope, 'click'))
        for action in ('double_click', 'drag', 'scroll', 'key', 'type'):
            with self.subTest(action=action):
                self.assertFalse(guard._safe_target(
                    {'ref': 'slide'}, envelope, action,
                    keyboard=action in ('key', 'type')))
        values['raw_flags']['FOCUSED'] = True
        self.assertFalse(capability.selector_capability(**values)['effective_keyboard_eligible'])

    def test_every_missing_owned_leaf_medium_or_selection_gate_refuses(self):
        for key, value in args()['context'].items():
            if value is True:
                values = args()
                values['context'][key] = False
                with self.subTest(key=key), self.assertRaises(ValueError):
                    capability.selector_capability(**values)

    def test_unsupported_build_scope_role_child_count_and_selection_refuse(self):
        values = args()
        values['build'] = {}
        with self.assertRaises(ValueError):
            capability.selector_capability(**values)
        for key, value in (
            ('name', 'Other view'), ('description', 'Unknown scope'),
            ('role', 'document presentation'), ('selection_interface_available', False),
            ('ACTIVE', False), ('SELECTABLE', False), ('FOCUSABLE', False),
            ('MULTISELECTABLE', False), ('child_count', 0), ('child_count', 65),
            ('child_count', True), ('child_count', None),
        ):
            values = args()
            values['selector'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                capability.selector_capability(**values)
        for role in ('paragraph', 'text', 'document frame'):
            values = args()
            values['ancestors'][0] = (role, flags())
            with self.subTest(role=role), self.assertRaises(ValueError):
                capability.selector_capability(**values)

    def test_disabled_stale_editable_and_other_insensitive_ancestors_refuse(self):
        for key, value in (
            ('ENABLED', False), ('SENSITIVE', False), ('VISIBLE', False),
            ('SHOWING', False), ('STALE', True), ('DEFUNCT', True),
            ('EDITABLE', True), ('FOCUSED', None),
        ):
            values = args()
            values['raw_flags'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                capability.selector_capability(**values)
        for index, key, value in (
            (1, 'SENSITIVE', True), (1, 'EDITABLE', True),
            (2, 'SENSITIVE', False), (2, 'STALE', True),
            (2, 'VISIBLE', False), (2, 'ENABLED', False),
        ):
            values = args()
            values['ancestors'][index][1][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                capability.selector_capability(**values)
        values = args()
        values['ancestors'].append(('document frame', flags(sensitive=False)))
        with self.assertRaises(ValueError):
            capability.selector_capability(**values)

    def test_false_readonly_mode_stale_binding_and_missing_current_read_refuse(self):
        for key, value in (
            ('checked', False), ('document_binding_sha256', 'd' * 64),
            ('expires_at', 1.5), ('same_native_node_reopened', False),
            ('current_native_state_read', False), ('enabled', False),
            ('sensitive', False), ('stale', True), ('defunct', True),
        ):
            values = args()
            values['mode'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                capability.selector_capability(**values)


class Node:
    def __init__(self, key, role, raw, extra=()):
        self.path = '/org/a11y/atspi/accessible/' + key
        self.app = SimpleNamespace(bus_name=':1.77')
        self.role, self.flags, self.extra = role, raw, set(extra)
        self.count, self.pid = 0, 10
        self.name, self.description = '', ''
        self.selection = None

    def get_role_name(self): return self.role
    def get_child_count(self): return self.count
    def get_process_id(self): return self.pid
    def get_name(self): return self.name
    def get_description(self): return self.description
    def get_selection_iface(self): return self.selection
    def get_state_set(self):
        return SimpleNamespace(contains=lambda key: key in self.extra)


class ReaderDelegate(unittest.TestCase):
    def test_actual_gi_selection_interface_and_unchanged_denials(self):
        class Evidence(dict):
            filename = 'fixture.pptx'
            x11 = {'wm_class': 'libreoffice-impress'}
            def refresh(self): return self

        shape = Node('shape', 'panel', flags(), ('ACTIVE', 'SELECTABLE', 'FOCUSABLE'))
        document = Node('document', 'document frame', flags(sensitive=False),
                        ('ACTIVE', 'SELECTABLE', 'FOCUSABLE', 'MULTISELECTABLE'))
        document.name = 'Slides View'
        document.description = 'This is where you sort slides.'
        document.count, document.selection = 4, object()
        window = Node('window', 'frame', flags())
        chain = [shape, document, window]
        evidence = Evidence(
            build=build.BUILD, mode=mode(), binding='a' * 64,
            native_pid=10, native_uid=1000,
            medium={'original_file_writable': True, 'original_medium_writable': True,
                    'application_is_readonly': False})
        baseline_record = {
            'ref': 'slide', 'bounds': [11, 378, 158, 82], 'visible': True,
            'enabled': False, 'obscured': True, 'keyboard': False, 'actions': [],
        }
        baseline_fact = {'role': 'panel', 'native_flags': shape.flags,
                         'structural_inventory_only': True, 'native_actions_authorized': False}
        source = SimpleNamespace(
            _v42_evidence=evidence, state_flags=lambda api, node: node.flags,
            geometry=lambda api, node, viewport: [11, 378, 158, 82],
            physical_hit=lambda *a, **kw: (shape, 3))
        api = SimpleNamespace(StateType=SimpleNamespace(
            **{key: key for key in ('ACTIVE', 'SELECTABLE', 'FOCUSABLE', 'MULTISELECTABLE')}))

        def invoke(pid=10, uid=1000):
            return reader.compatible_record(
                source, api, shape, window, pid=pid, uid=uid,
                viewport=[1280, 800], ancestry=lambda *a: chain)

        with patch.object(reader.previous.previous, 'compatible_record',
                          return_value=(baseline_record, baseline_fact)) as delegated, \
             patch.object(reader.time, 'monotonic', return_value=2.):
            record_snapshot, fact_snapshot = deepcopy(baseline_record), deepcopy(baseline_fact)
            selected, proof = invoke()
            self.assertEqual(delegated.call_count, 1)
            self.assertEqual(selected['actions'], ['click'])
            self.assertTrue(selected['enabled'])
            self.assertFalse(selected['keyboard'])
            self.assertEqual(proof['native_flags'], flags())
            self.assertEqual(baseline_record, record_snapshot)
            self.assertEqual(baseline_fact, fact_snapshot)
            for change in ('foreign_pid', 'foreign_uid', 'nonleaf', 'missing_selection',
                           'wrong_scope', 'unknown_role', 'wrong_application', 'readonly'):
                with self.subTest(change=change):
                    call_pid, call_uid = 10, 1000
                    if change == 'foreign_pid': call_pid = 99
                    elif change == 'foreign_uid': call_uid = 2000
                    elif change == 'nonleaf': shape.count = 1
                    elif change == 'missing_selection': document.selection = None
                    elif change == 'wrong_scope': document.name = 'Other view'
                    elif change == 'unknown_role': document.role = 'panel'
                    elif change == 'wrong_application': evidence.filename = 'fixture.docx'
                    elif change == 'readonly': evidence['medium']['original_medium_writable'] = False
                    denied, _ = invoke(call_pid, call_uid)
                    self.assertIs(denied, baseline_record)
                    shape.count = 0
                    document.selection, document.name, document.role = object(), 'Slides View', 'document frame'
                    evidence.filename = 'fixture.pptx'
                    evidence['medium']['original_medium_writable'] = True
            evidence['medium']['application_is_readonly'] = True
            denied, _ = invoke()
            self.assertIs(denied, baseline_record)
            evidence['medium']['application_is_readonly'] = False
            def supported_getter():
                warnings.warn('Atspi.Accessible.get_selection_iface is deprecated',
                              DeprecationWarning)
                return document.selection
            document.get_selection_iface = supported_getter
            selected, proof = invoke()
            self.assertEqual(selected['actions'], ['click'])
            retained = proof['Impress_selector_capability_evidence']['administrative_selector']
            self.assertEqual(retained['supported_getter_warnings'][0]['getter'],
                             'get_selection_iface')
            def unexpected_getter():
                warnings.warn('Unexpected getter warning', RuntimeWarning)
                return document.selection
            document.get_selection_iface = unexpected_getter
            denied, _ = invoke()
            self.assertIs(denied, baseline_record)
            document.get_selection_iface = lambda: document.selection
            source.physical_hit = lambda *a, **kw: (window, 3)
            denied, _ = invoke()
            self.assertIs(denied, baseline_record)


def denial_metadata():
    denial = {
        'ref': 'denied-shape', 'bounds': [10, 10, 20, 20], 'visible': True,
        'enabled': False, 'obscured': True, 'keyboard': False, 'actions': [],
    }
    canvas = {
        'ref': 'canvas', 'bounds': [0, 0, 100, 100], 'visible': True,
        'enabled': True, 'obscured': False, 'keyboard': False, 'actions': ['click'],
    }
    save = {**canvas, 'ref': 'save', 'bounds': [120, 80, 30, 20]}
    fact = {'structural_inventory_only': True, 'native_actions_authorized': False,
            'native_flags': flags()}
    return {
        'targets': [denial, canvas, save],
        'requested_point_facts': [{'requested_point': [20, 20],
                                   'actual_hit': denial, 'native_fact': fact}],
        'retained_native_facts': [fact],
    }


class DenialSerialization(unittest.TestCase):
    def test_only_explicit_denial_wire_normalized_flags_bounds_and_raw_facts_unchanged(self):
        metadata = denial_metadata()
        snapshot = deepcopy(metadata)
        result = capability.actionable_metadata(metadata)
        self.assertEqual(metadata, snapshot)
        self.assertEqual(len(result['targets']), 3)
        self.assertEqual(result['targets'][0], {**metadata['targets'][0], 'actions': ['click']})
        self.assertIs(result['targets'][1], metadata['targets'][1])
        self.assertIs(result['targets'][2], metadata['targets'][2])
        self.assertIs(result['requested_point_facts'], metadata['requested_point_facts'])
        self.assertIs(result['retained_native_facts'], metadata['retained_native_facts'])
        self.assertEqual(result['requested_point_facts'][0]['actual_hit']['actions'], [])
        self.assertEqual(result['explicit_structural_denial_schema_projection_refs'],
                         ['denied-shape'])
        self.assertTrue(result['disabled_denial_bounds_and_flags_preserved'])
        self.assertTrue(result['denial_facts_preserved'])

    def test_original_guard_denies_smaller_disabled_hit_under_canvas_and_equal_area(self):
        from tests.test_native_desktop_semantic_native_transport_v23 import SemanticTests
        metadata = denial_metadata()
        serialized = capability.actionable_metadata(metadata)
        fixture = SemanticTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.meta['targets'] = serialized['targets']
        observation = fixture.observation()
        _, receipt = fixture.actor.dispatch_model(
            '{"type":"click","target":{"x":20,"y":20}}', observation,
            actor_deadline=time.monotonic() + 720)
        self.assertEqual(receipt['native_status'], 'rejected')
        decision = json.loads(
            (fixture.root / receipt['native_dispatch_receipt']['path']).read_bytes())
        self.assertEqual(decision['reason'], 'target_not_current_and_safe')
        self.assertEqual(fixture.native_calls, [])
        targets = [guard.NativeTarget(**{**target,
                    'bounds': tuple(target['bounds']), 'actions': tuple(target['actions'])})
                   for target in serialized['targets']]
        envelope = SimpleNamespace(targets=targets)
        self.assertFalse(guard._safe_target({'x': 20, 'y': 20}, envelope, 'click'))
        self.assertFalse(guard._safe_target({'ref': 'denied-shape'}, envelope, 'click'))
        self.assertTrue(guard._safe_target({'x': 130, 'y': 90}, envelope, 'click'))
        targets.append(guard.NativeTarget('same-area', (10, 10, 20, 20),
                                         True, True, False, False, ('click',)))
        self.assertFalse(guard._safe_target({'x': 20, 'y': 20}, envelope, 'click'))

    def test_missing_mismatched_or_not_explicit_empty_action_denials_fail_closed(self):
        for change in ('absent_fact', 'wrong_target', 'authorized_fact',
                       'not_structural', 'keyboard', 'enabled', 'not_obscured'):
            metadata = denial_metadata()
            item = metadata['requested_point_facts'][0]
            if change == 'absent_fact': metadata['requested_point_facts'] = []
            elif change == 'wrong_target':
                item['actual_hit'] = {**item['actual_hit'], 'ref': 'another-shape'}
            elif change == 'authorized_fact': item['native_fact']['native_actions_authorized'] = True
            elif change == 'not_structural': item['native_fact']['structural_inventory_only'] = False
            elif change == 'keyboard': item['actual_hit']['keyboard'] = True
            elif change == 'enabled': item['actual_hit']['enabled'] = True
            elif change == 'not_obscured': item['actual_hit']['obscured'] = False
            snapshot = deepcopy(metadata)
            with self.subTest(change=change), self.assertRaises(ValueError):
                capability.actionable_metadata(metadata)
            self.assertEqual(metadata, snapshot)

    def test_unknown_malformed_record_stays_rejected_by_unchanged_wire_validator(self):
        from tests.test_native_desktop_semantic_native_transport_v23 import SemanticTests
        fixture = SemanticTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        target = {**fixture.meta['targets'][0], 'actions': ['unsupported_action']}
        serialized = capability.actionable_metadata({'targets': [target]})
        fixture.meta['targets'] = serialized['targets']
        with self.assertRaises(guard.GuardError):
            fixture.observation()
        self.assertEqual(fixture.native_calls, [])
        self.assertEqual(serialized['targets'][0], target)


class UniformSource(unittest.TestCase):
    def test_all_21_constructors_guard_code_old_50_bytes_globals_and_activation(self):
        runtime_snapshot = (Path(old_runtime.__file__).read_bytes(), dict(vars(old_runtime)))
        reader_snapshot = (Path(old_reader.__file__).read_bytes(), dict(vars(old_reader)))
        old_manifest = old_runtime.source_manifest(ROOT)
        old_sources = {name: (ROOT / name).read_bytes()
                       for name in old_manifest['source_sha256s']}
        previous_factory = old_runtime.factory(manifest=old_manifest, source_root=ROOT)
        manifest = runtime.source_manifest(ROOT)
        factory = runtime.factory(manifest=manifest, source_root=ROOT)
        actors = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role in manifest['actor_paths']:
                for filename in ('fixture.xlsx', 'fixture.docx', 'fixture.pptx'):
                    out = root / role / Path(filename).suffix[1:]
                    out.mkdir(mode=0o700, parents=True)
                    actor = factory.wrap_owned_guest(
                        SimpleNamespace(sandbox_id='offline-' + role,
                                        commands=SimpleNamespace(), files=SimpleNamespace()),
                        root=root, out=out, filename=filename,
                        lease_started_monotonic=time.monotonic())
                    actors.append(actor)
                    self.assertIs(type(actor), factory.actor_class)
        self.assertEqual(len(actors), 21)
        for name in ('capture', 'native_input', 'envelope', 'lease_check', 'dispatch_model'):
            current = getattr(factory.actor_class, name).__code__
            original = getattr(previous_factory.actor_class, name).__code__
            self.assertEqual(current.co_code, original.co_code, name)
            self.assertEqual(current.co_consts, original.co_consts, name)
        self.assertIs(runtime.control_driver, old_runtime.control_driver)
        reader.scoped_reader()
        self.assertEqual(Path(old_runtime.__file__).read_bytes(), runtime_snapshot[0])
        self.assertEqual(dict(vars(old_runtime)), runtime_snapshot[1])
        self.assertEqual(Path(old_reader.__file__).read_bytes(), reader_snapshot[0])
        self.assertEqual(dict(vars(old_reader)), reader_snapshot[1])
        self.assertEqual(old_runtime.source_manifest(ROOT), old_manifest)
        for name, raw in old_sources.items():
            self.assertEqual((ROOT / name).read_bytes(), raw, name)
            self.assertEqual(manifest['source_sha256s'][name], old_manifest['source_sha256s'][name])
        self.assertEqual(manifest['native_policy_sha256'], old_manifest['native_policy_sha256'])
        self.assertEqual(manifest['task_policy'], {
            'max_actions': 90, 'actor_seconds': 720, 'lease_seconds': 1200})
        binding = runtime.public_binding(ROOT)
        self.assertFalse(binding['native_qualification_passed'])
        self.assertFalse(binding['old_results_reclassified'])
        self.assertEqual(binding['model_calls'], 0)
        self.assertEqual(binding['tinker_calls'], 0)
        with self.assertRaises(ValueError):
            factory.require_activation()


if __name__ == '__main__':
    unittest.main()
