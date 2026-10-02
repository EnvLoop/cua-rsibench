"""Native14 Sol6 teacher endpoint; original V13 collector stays unchanged."""
from .native_compat_source_loader_v1 import load_source
from types import SimpleNamespace
import os
_impl = load_source(
    'enterprise_fallback/odoo18/twenty_task_trial_teacher_v1.py',
    'enterprise_fallback.odoo18._twenty_task_trial_teacher_v2',
    '8f65162fecd11dc66678d1e469d0a8cc7845d39bbf729a88844ec6bd687164a5',
    (('native_surface_workers_v13', 'native_surface_workers_v14', 1),
     ("'image_detail':'high'}", "'image_detail':'high','response_format':'json_object'}", 1)))
_impl.TEACHER_SYSTEM_PROMPT += (
    '\nThis native browser runs on macOS. For select-all inside a focused editor, '
    'use Meta+A (Command+A). Control+A moves the caret to the beginning and does '
    'not select the existing text here. After activating a real editor, replace '
    'its value with Meta+A followed by a separate targetless insert action, or '
    'use fill on an actual editable textbox ref. Verify the displayed value '
    'matches the source exactly; do not append another copy of a reference. '
    'For this teacher collection, never emit a fill action. Edit using an '
    'observed click to activate the field, a fresh Meta+A action, then a '
    'separate targetless insert action. Table-cell refs are not editable '
    'textbox refs even when they display a number. Observe between each step. '
    'Once you read a source document, retain all its required values and the '
    'completed edits in every later memory. Do not replace these facts with '
    'a generic instruction to open the document again. If one paperclip click '
    'does not expose an attachment card, scroll down to reveal the card rather '
    'than repeatedly clicking the paperclip. Do not repeat an ineffective '
    'click on an unchanged frame more than twice. After saving and reopening '
    'once, finish if the visible requested fields match retained source facts; '
    'the independent evaluator performs the complete saved-state check.')

def _json_teacher_provider(request, timeout_seconds):
    """Teacher JSON syntax mode; the existing action validator remains strict."""
    from cursibench.http_transport import post_json
    key = os.environ.get('OPENAI_API_KEY')
    _impl.workers.require(bool(key) and request.get('response_format') == 'json_object',
                          'teacher_json_mode_and_key_required')
    payload = {'model': request['model'], 'store': False,
        'max_output_tokens': request['max_output_tokens'],
        'reasoning': {'effort': request['reasoning_effort']},
        'text': {'format': {'type': 'json_object'}},
        'input': [{'role': 'developer', 'content': request['system_prompt']},
            {'role': 'user', 'content': [
                {'type': 'input_text', 'text': request['user_text']},
                {'type': 'input_image', 'image_url': request['image_data_url'],
                 'detail': request['image_detail']}]}]}
    body = post_json('https://sub2api.agentrouterhub.com/v1/responses', payload,
        {'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'}, timeout_seconds)
    text = '\n'.join(part['text'] for item in body.get('output', [])
        if item.get('type') == 'message' for part in item.get('content', [])
        if part.get('type') == 'output_text')
    return {'text': text, 'receipt': {'reported_model': body.get('model'),
        'status': body.get('status'), 'response_id': body.get('id'),
        'usage': body.get('usage'), 'transport': body.get('__cua_transport'),
        'teacher_response_format': 'json_object', 'action_validation_relaxed': False}}

_impl.teacher = SimpleNamespace(**{**vars(_impl.teacher),
                                  '_real_teacher_provider': _json_teacher_provider})
def __getattr__(name): return getattr(_impl, name)
if __name__ == '__main__': _impl.main()
