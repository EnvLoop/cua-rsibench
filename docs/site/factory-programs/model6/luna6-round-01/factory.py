import json
from pathlib import Path

examples = json.loads(Path('/inputs/examples.json').read_text())
history = json.loads(Path('/inputs/historical-submissions.json').read_text())

# Use only approved decision records from the two independently verified episodes.
groups = {}
for record in examples:
    if record.get('representation') != 'decision':
        continue
    episode = record.get('record_id', '').split(':', 1)[0]
    if episode in ('episode-00', 'episode-01'):
        groups.setdefault(episode, []).append(record)
for records in groups.values():
    records.sort(key=lambda item: int(item['record_id'].split(':')[1]))
assert groups.get('episode-00') and groups.get('episode-01'), 'Both verified lessons must be represented'

# Keep the mixture balanced and within the 64-record full-coverage contract.
limit = min(64, sum(map(len, groups.values())))
selected = []
while len(selected) < limit:
    progressed = False
    for episode in ('episode-00', 'episode-01'):
        position = sum(1 for item in selected if item['record_id'].startswith(episode + ':'))
        if position < len(groups[episode]) and len(selected) < limit:
            selected.append(groups[episode][position])
            progressed = True
    if not progressed:
        break

submissions = history if isinstance(history, list) else history.get('submissions', [])
historical_ids = {rid for submission in submissions if isinstance(submission, dict) for rid in submission.get('record_ids', [])}
assert not historical_ids.intersection(item['record_id'] for item in selected)
Path('/workspace/train_messages.jsonl').write_text(''.join(json.dumps(item, separators=(',', ':'), ensure_ascii=True) + '\n' for item in selected))
print(json.dumps({'selected': len(selected), 'episodes': {episode: sum(item['record_id'].startswith(episode + ':') for item in selected) for episode in groups}}))
