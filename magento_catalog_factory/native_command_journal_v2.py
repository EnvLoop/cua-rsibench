"""Current exact absent-object replies, preserving original journal mechanics."""
import hashlib
import inspect
import json
import re
import textwrap
from tools import magento_dedicated_train_lane_v066 as original


def exact_absence(args, result):
    if result.returncode != 1 or not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        return False
    try:
        if json.loads(result.stdout) != []:
            return False
    except ValueError:
        return False
    if len(args) == 2 and args[0] == 'inspect':
        target = args[1]
        expected = 'no such object: ' + target.lower()
    elif len(args) == 3 and args[:2] == ('network', 'inspect'):
        target = args[2]
        expected = 'network ' + target.lower() + ' not found'
    else:
        return False
    if not isinstance(target, str) or not re.fullmatch(r'envloop-magento[-a-z0-9]+', target):
        return False
    actual = result.stderr.strip().lower()
    return actual in (expected, 'error: ' + expected, 'error response from daemon: ' + expected)


def expected_stopped_service(args, result):
    return bool(len(args) == 5 and args[0] == 'exec' and
                args[1] in [pair[0] for pair in original.PAIRS] and
                args[2:] == ('supervisorctl', 'status', 'cron') and
                result.returncode == 3 and result.stderr == '' and
                re.fullmatch(r'cron\s+STOPPED\s+Not started\s*', result.stdout))


def load_run():
    source = textwrap.dedent(inspect.getsource(original.CommandJournal.run))
    if hashlib.sha256(source.encode()).hexdigest() != '4e92d3eded7d7c15e262a1fd293d1ec4c29551f1f497865449fc36d40082e6a8':
        raise ValueError('Original command-journal source changed')
    # This helper changes only recognition before the unchanged raw result is
    # journalled. It neither rewrites stdout/stderr nor repeats a command.
    old = '''    absent = (allow_absent and result.returncode != 0 and
              ("No such object" in stderr or
               "not found" in stderr.lower()))'''
    if source.count(old) != 1:
        raise ValueError('Pinned original absent-result branch changed')
    source = source.replace(old, '    absent = allow_absent and exact_absence(docker_args, result)')
    append = '    self._append({"event": "result", "label": label,'
    if source.count(append) != 1:
        raise ValueError('Original raw-result append changed')
    source = source.replace(append, '''    if expected_stopped_service(docker_args, result):
        self._diagnostic(label, "stdout", stdout)
    self._append({"event": "result", "label": label,
                  "expected_stopped_service": expected_stopped_service(docker_args, result),''')
    marker = '    if result.returncode != 0:\n'
    if source.count(marker) != 1:
        raise ValueError('Original failure-result branch changed')
    source = source.replace(marker, '    if result.returncode != 0 and not expected_stopped_service(docker_args, result):\n')
    namespace = {**original.__dict__, 'exact_absence': exact_absence,
                 'expected_stopped_service': expected_stopped_service}
    exec(compile(source, 'magento-current-exact-absence-journal', 'exec'), namespace)
    return namespace['run']


class CommandJournal(original.CommandJournal):
    run = load_run()
