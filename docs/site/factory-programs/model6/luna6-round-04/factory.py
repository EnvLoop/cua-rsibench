import json
from pathlib import Path

ROOT = Path('/workspace')

# Generate compact, distinct direct-edit and conditional-ranking lessons.
tasks = [
    {
        'id': 'edit-login-triage',
        'source_numbers': [5893],
        'mode': 'direct',
        'select_numbers': [5893],
        'changes': {'owner': 'Chen', 'priority': 2, 'score': 5},
        'notes': 'Triage the open login issue.'
    },
    {
        'id': 'rank-recent-triage',
        'source_numbers': [5869, 5893],
        'mode': 'rank',
        'where': {'all': [
            {'field': 'state', 'op': 'eq', 'value': 'open'},
            {'field': 'labels', 'op': 'contains', 'value': 'triage needed'}
        ]},
        'order_by': [{'field': 'updated_at', 'direction': 'desc'}],
        'limit': 1,
        'changes': {'owner': 'Rivera', 'priority': 2, 'score': 6},
        'notes': 'Prioritize the most recently updated open item labeled triage needed.'
    }
]
(ROOT / 'tasks.json').write_text(json.dumps(tasks, ensure_ascii=True, indent=2) + '\n')

# Emit only controller-approved records for verified episodes, excluding historical IDs.
examples = json.loads(Path('/inputs/examples.json').read_text())
historical = json.loads(Path('/inputs/historical-submissions.json').read_text())
submissions = historical if isinstance(historical, list) else historical.get('submissions', [])
historical_ids = {
    rid for submission in submissions if isinstance(submission, dict)
    for rid in submission.get('record_ids', [])
}
verified_episodes = {'episode-00', 'episode-01', 'episode-02', 'episode-03'}
groups = {}
for record in examples:
    rid = record.get('record_id', '')
    parts = rid.split(':')
    if len(parts) != 3:
        continue
    episode, step, representation = parts
    if episode not in verified_episodes or representation != 'decision':
        continue
    groups[(episode, step)] = record

new_episodes = sorted({episode for episode, _ in groups if episode not in {'episode-00', 'episode-01'}})
selected = [groups[key] for key in sorted(groups) if key[0] in new_episodes and groups[key]['record_id'] not in historical_ids]
if not selected:
    selected = [groups[key] for key in sorted(groups) if groups[key]['record_id'] not in historical_ids]
assert selected, 'No non-historical approved decision records available'
(ROOT / 'train_messages.jsonl').write_text(''.join(json.dumps(r, separators=(',', ':'), ensure_ascii=True) + '\n' for r in selected))
print(json.dumps({'task_count': len(tasks), 'task_ids': [task['id'] for task in tasks], 'selected_records': len(selected)}))
