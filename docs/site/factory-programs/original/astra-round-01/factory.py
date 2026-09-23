import json
from pathlib import Path
import argparse

ROOT = Path('/workspace')
INPUTS = Path('/inputs')

def generate():
    source = json.loads((INPUTS / 'sources.json').read_text())
    records = {r['number']: r for r in source['records']}
    # Use authentic source facts to choose candidates; insertion order is deliberately unranked.
    tagged = sorted((r for r in records.values() if r['state'] == 'open' and 'triage needed' in r['labels']), key=lambda r: (r['updated_at'], r['number']))
    assert len(tagged) >= 3
    oldest, middle, newest = tagged[0], tagged[1], tagged[-1]
    closed = max((r for r in records.values() if r['state'] == 'closed'), key=lambda r: r['updated_at'])
    tasks = [
        {'id': 'source-edit-single', 'source_numbers': [middle['number'], oldest['number']], 'mode': 'direct', 'select_numbers': [oldest['number']], 'changes': {'owner': 'Chen', 'priority': 2, 'score': 5}, 'notes': 'Workflow: edit the selected task, save, and inspect its saved fields. Preserve unrelated tasks and the archive project.'},
        {'id': 'source-rank-open-triage', 'source_numbers': [oldest['number'], closed['number'], newest['number']], 'mode': 'rank', 'where': {'all': [{'field': 'state', 'op': 'eq', 'value': 'open'}, {'field': 'labels', 'op': 'contains', 'value': 'triage needed'}]}, 'order_by': [{'field': 'updated_at', 'direction': 'desc'}], 'limit': 1, 'changes': {'owner': 'Rivera', 'priority': 3, 'score': 8}, 'notes': 'Workflow: apply the source metadata condition before ranking by source update time. Edit only the selected task, save, and inspect its saved fields. Preserve unrelated tasks and the archive project.'}
    ]
    for task in tasks:
        assert set(task['source_numbers']) <= records.keys()
    (ROOT / 'tasks.json').write_text(json.dumps(tasks, indent=2) + '\n')
    print(json.dumps({'generated': tasks, 'source_snapshot': source.get('snapshot_sha256')}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['generate'], default='generate', nargs='?')
    args = parser.parse_args()
    generate()
