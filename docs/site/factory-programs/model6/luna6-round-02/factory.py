import json
from pathlib import Path

ROOT = Path('/workspace')

# Keep the GUI tasks small while covering editing and conditional ranking.
tasks = [
    {
        'id': 'edit-open-security',
        'source_numbers': [5871, 5874],
        'mode': 'direct',
        'select_numbers': [5871],
        'changes': {'owner': 'Chen', 'priority': 2, 'score': 5},
        'notes': 'Triage the selected open security issue; retain the other imported issue unchanged.'
    },
    {
        'id': 'rank-open-security',
        'source_numbers': [5871, 5874],
        'mode': 'rank',
        'where': {'field': 'state', 'op': 'eq', 'value': 'open'},
        'order_by': [{'field': 'updated_at', 'direction': 'desc'}],
        'limit': 1,
        'changes': {'owner': 'Rivera', 'priority': 1, 'score': 8},
        'notes': 'Prioritize the most recently updated open issue.'
    }
]
(ROOT / 'tasks.json').write_text(json.dumps(tasks, ensure_ascii=True, indent=2) + '\n')

examples = json.loads(Path('/inputs/examples.json').read_text())
history_data = json.loads(Path('/inputs/historical-submissions.json').read_text())

# Retain only records from verified episodes, preferring compact decision variants.
verified = {'episode-00', 'episode-01'}
groups = {}
for record in examples:
    rid = record.get('record_id', '')
    episode = rid.split(':', 1)[0]
    if episode in verified:
        groups.setdefault(episode, {})
        index = int(rid.split(':')[1])
        groups[episode].setdefault(index, {})[record.get('representation')] = record

available = [episode for episode in ('episode-00', 'episode-01') if groups.get(episode)]
assert len(available) >= 2, 'Need verified records from two independent episodes'
selected = []
# Interleave episodes and keep history context only where a decision record is absent.
for index in range(max(len(groups[e]) for e in available)):
    for episode in available:
        variants = groups[episode].get(index, {})
        record = variants.get('decision') or variants.get('history')
        if record is not None:
            selected.append(record)

submissions = history_data if isinstance(history_data, list) else history_data.get('submissions', [])
historical_ids = {rid for submission in submissions if isinstance(submission, dict) for rid in submission.get('record_ids', [])}
selected = [r for r in selected if r['record_id'] not in historical_ids]
assert selected, 'No non-historical approved records selected'
(ROOT / 'train_messages.jsonl').write_text(''.join(json.dumps(r, separators=(',', ':'), ensure_ascii=True) + '\n' for r in selected))
print(json.dumps({'tasks': len(tasks), 'selected_records': len(selected), 'episodes': available}))
