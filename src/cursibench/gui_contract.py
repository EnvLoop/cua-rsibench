"""Versioned common observation/action contract for generated training and evaluation."""
import json

VERSION='native-gui-v4'
MAX_OUTPUT_TOKENS=1024
MAX_MEMORY_CHARS=6000
CONTRACT='''Operate the native Kanboard GUI. Return exactly JSON {"action":{"type":"click/fill/select/press/back/done","control":"CURRENT visible control id","value":"text or option label"},"memory":"concise working notes"}. One action per turn. Use only controls in the current observation; IDs change after navigation. For select use the visible option label. Allowed keys are Enter, Tab and Escape. Preserve facts, task references and completed steps in memory. Save every required edit and visibly verify the result before done. The session is already logged in. No shell, SQL, application APIs, arbitrary URLs or file edits are available.'''


def prompt(instruction,observation,memory='',last_action=None):
    return CONTRACT+'\n'+json.dumps({'task':instruction,'observation':observation,
                                    'memory':memory,'last_action':last_action},ensure_ascii=False,sort_keys=True)


def json_object(text):
    clean=text.strip()
    if clean.startswith('```'):clean='\n'.join(clean.splitlines()[1:-1])
    result=json.loads(clean)
    if not isinstance(result,dict):raise ValueError('object required')
    return result
