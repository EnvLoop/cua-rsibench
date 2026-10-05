"""Readonly Monaco matching facts captured in one synchronous DOM snapshot.

This module discovers facts only. Callers retain ownership, stability, current
target, physical input, saved-artifact and reset guards. It grants no permission.
"""
from __future__ import annotations

from typing import Any


SCHEMA = 'atomic-readonly-editor-matches-v1'
SELECTOR = '.monaco-editor'
CODE_SELECTOR = '.monaco-editor[role="code"]'
MAXIMUM_MATCHES = 8

FACTS_JS = r'''el=>{
 const doc=el.ownerDocument,r=el.getBoundingClientRect(),s=getComputedStyle(el),hit=doc.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
 const fields=[...el.querySelectorAll('textarea')].map(e=>({tag:e.tagName,role:e.getAttribute('role'),label:e.getAttribute('aria-label')||'',disabled:e.disabled,readonly:e.readOnly}));
 const active=doc.activeElement;
 return{tag:el.tagName,role:el.getAttribute('role'),bounds:[r.x,r.y,r.width,r.height],documentReady:doc.readyState,
  painted:el.isConnected&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&!!hit&&(hit===el||el.contains(hit)),
  editor_textareas:fields,focus:active?{tag:active.tagName,role:active.getAttribute('role'),label:active.getAttribute('aria-label')||'',inside_editor:el.contains(active)}:null,
  readonly:true};
}'''

SNAPSHOT_JS = ('(elements)=>{const count=elements.length;const roleCount=elements.filter(el=>el.matches(' +
    repr(CODE_SELECTOR) + ')).length;const snapshot=(' + FACTS_JS + ');return{schema:' + repr(SCHEMA) +
    ',broad_count:count,role_code_target_count:roleCount,matching_nodes:count<=8?elements.map(snapshot):[],' +
    'url:location.href,documentReady:document.readyState,readonly:true,native_input_performed:false};}')


def project_snapshot(snapshot: dict[str, Any], *, expected_label: str) -> dict[str, Any]:
    """Retain all observed exclusions and refuse incomplete or overlimit facts.

    ``expected_label`` must come from the caller's existing task/file contract.
    It is compared exactly; this helper does not derive it from the candidate.
    """
    if not isinstance(expected_label, str) or not expected_label:
        raise ValueError('exact_expected_editor_label_required')
    if (type(snapshot) is not dict or snapshot.get('schema') != SCHEMA or
            snapshot.get('readonly') is not True or snapshot.get('native_input_performed') is not False):
        raise ValueError('atomic_readonly_matching_snapshot_required')
    count, roles, nodes = (snapshot.get(key) for key in ('broad_count', 'role_code_target_count', 'matching_nodes'))
    if (type(count) is not int or count < 0 or type(roles) is not int or not 0 <= roles <= count or
            type(nodes) is not list or type(snapshot.get('url')) is not str or
            snapshot.get('documentReady') not in ('loading', 'interactive', 'complete')):
        raise ValueError('atomic_matching_snapshot_shape_changed')
    eligible, excluded = [], []
    drift = False
    for index, node in enumerate(nodes):
        if type(node) is not dict:
            raise ValueError('matching_node_facts_required')
        fields, focus = node.get('editor_textareas', []), node.get('focus') or {}
        if (type(fields) is not list or type(focus) is not dict or type(node.get('painted')) is not bool or
                any(type(field) is not dict or type(field.get('disabled')) is not bool or
                    type(field.get('readonly')) is not bool for field in fields)):
            raise ValueError('complete_typed_matching_node_facts_required')
        code = node.get('tag') == 'DIV' and node.get('role') == 'code'
        editable = (code and node.get('painted') is True and len(fields) == 1 and
            fields[0].get('tag') == 'TEXTAREA' and fields[0].get('role') == 'textbox' and
            not fields[0].get('disabled') and not fields[0].get('readonly') and
            fields[0].get('label', '') == expected_label)
        focused = (editable and focus.get('inside_editor') is True and focus.get('tag') == 'TEXTAREA' and
                   focus.get('role') == 'textbox' and focus.get('label', '') == expected_label)
        if focused:
            eligible.append(node)
        else:
            excluded.append({'index': index, 'native_facts': node})
        if code and not focused:
            drift = True
    return {'broad_count': count, 'eligible_count': len(eligible), 'eligible_nodes': eligible,
            'excluded_matches': excluded, 'current_role_focus_target_drift': drift,
            'role_code_target_count': roles, 'url': snapshot['url'],
            'unknown_matching_facts': count > MAXIMUM_MATCHES or len(nodes) != count,
            'atomic_matching_snapshot': snapshot, 'separate_matching_count_used': False,
            'native_input_performed': False, 'permission_granted': False}


def require_unique_known_editor(state: dict[str, Any]) -> dict[str, Any]:
    """Check the existing matching contract; no wait or input is performed."""
    if state['unknown_matching_facts']:
        raise ValueError('unknown_or_overlimit_matching_facts')
    if state['eligible_count'] > 1:
        raise ValueError('multiple_eligible_native_editors')
    if state['current_role_focus_target_drift']:
        raise ValueError('native_editor_role_focus_target_drift')
    if state['role_code_target_count'] != state['eligible_count']:
        raise ValueError('role_code_target_count_proof_changed')
    if state['eligible_count'] != 1:
        raise ValueError('unique_editor_not_ready')
    return state['eligible_nodes'][0]


async def collect_snapshot(locator: Any, *, expected_label: str) -> dict[str, Any]:
    """Use ``page.locator(SELECTOR)``; never call a separate matching count."""
    return project_snapshot(await locator.evaluate_all(SNAPSHOT_JS), expected_label=expected_label)
