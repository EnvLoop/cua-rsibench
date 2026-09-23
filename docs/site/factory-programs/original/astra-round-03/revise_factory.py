from pathlib import Path
p=Path('/workspace/factory.py')
s=p.read_text()
s=s.replace("'source-edit-single-v3'", "'source-edit-single-v4'")
s=s.replace("Keep a checklist of completed and remaining references.", "Keep an explicit checklist with each selected reference marked pending, saved, or visibly verified. Update a reference only after its own observed action; never infer that another task was edited earlier. After each save, check which selected references remain pending.")
start=s.index('def build():')
end=s.index("if __name__ == '__main__':")
new='''def build():
    import hashlib
    from collections import Counter
    approved = json.loads((INPUTS / 'examples.json').read_text())
    history = json.loads((INPUTS / 'historical-submissions.json').read_text())
    by_id = {r['record_id']: r for r in approved}
    assert len(by_id) == len(approved)
    # Complete compact trajectories retain selection evidence and both saved edits.
    # The direct episode preserves every demonstrated editing anchor.
    policy = {'episode-00': list(range(11)),
              'episode-04': list(range(25)),
              'episode-03': list(range(26))}
    groups, seen, duplicates = {}, set(), []
    for episode, steps in policy.items():
        groups[episode] = []
        for step in steps:
            row = by_id[f'{episode}:{step}:decision']
            assert row['source_split'] == 'train'
            assert row['representation'] == 'decision'
            assert row['episode_sha256'] and row['case_sha256']
            messages = row['messages']
            assert messages[-1]['role'] == 'assistant'
            response = json.loads(messages[-1]['content'])
            action = response['action']
            assert action['type'] in ('click', 'fill', 'select', 'press', 'back', 'done')
            assert isinstance(response['memory'], str)
            # Parse the actual observation from the final user message.
            user = next(m['content'] for m in reversed(messages[:-1]) if m['role'] == 'user')
            decoder = json.JSONDecoder()
            observation = None
            for offset, char in enumerate(user):
                if char != '{':
                    continue
                try:
                    obj, _ = decoder.raw_decode(user[offset:])
                except ValueError:
                    continue
                if isinstance(obj, dict) and isinstance(obj.get('observation'), dict):
                    observation = obj['observation']
                    break
            assert observation is not None, row['record_id']
            controls = {str(c['id']): c for c in observation['controls']}
            if action['type'] in ('click', 'fill', 'select'):
                assert str(action['control']) in controls, row['record_id']
                control = controls[str(action['control'])]
                if action['type'] == 'select':
                    assert control['tag'] == 'select', row['record_id']
                if action['type'] == 'fill':
                    assert control['tag'] in ('input', 'textarea'), row['record_id']
                    assert control.get('label') != 'Filter', row['record_id']
            if action['type'] == 'press':
                assert action['value'] in ('Enter', 'Tab', 'Escape')
            digest = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if digest in seen:
                duplicates.append(row['record_id'])
                continue
            seen.add(digest)
            groups[episode].append(row)
    ordered = []
    for offset in range(max(map(len, groups.values()))):
        for episode in ('episode-04', 'episode-03', 'episode-00'):
            if offset < len(groups[episode]):
                ordered.append(groups[episode][offset])
    ids = [r['record_id'] for r in ordered]
    assert all(f'episode-00:{i}:decision' in ids for i in range(11))
    assert 1 <= len(ordered) <= 64
    payload = ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\\n' for r in ordered)
    assert len(payload.encode()) <= 2_000_000
    digest = hashlib.sha256(payload.encode()).hexdigest()
    comparisons = []
    for prior in history:
        old = prior['record_ids']
        comparisons.append({'factory': prior['factory'], 'retained': len(set(old) & set(ids)),
                            'added': len(set(ids) - set(old)), 'removed': len(set(old) - set(ids)),
                            'same_order': ids == old, 'same_membership': set(ids) == set(old)})
        assert digest != prior['dataset_sha256']
        assert ids != old
    destination = ROOT / 'train_messages.jsonl'
    destination.write_text(payload)
    reread = [json.loads(line) for line in destination.read_text().splitlines()]
    assert reread == ordered
    assert all(r == by_id[r['record_id']] for r in reread)
    report = {'records': len(ordered), 'bytes': len(payload.encode()), 'sha256': digest,
              'episodes': dict(Counter(r['record_id'].split(':')[0] for r in ordered)),
              'actions': dict(Counter(json.loads(r['messages'][-1]['content'])['action']['type'] for r in ordered)),
              'representation': 'decision', 'duplicates_removed': duplicates,
              'historical_comparison': comparisons, 'record_ids': ids,
              'validation': 'Unchanged approved records; unique messages; native action types and current control references checked.',
              'failure_diagnosis': 'Episode-05 computed the correct pair but at step 15 falsely remembered saving the other target; it ended after one actual save. No records from that failed episode are included.',
              'selection_rationale': 'Preserve all direct anchors and complete ranking/allocation trajectories, including candidate inspection, both saves and final verification. Decision variants avoid repeated full histories.',
              'limitations': 'No student training or final-test evidence. Character and byte limits do not establish exact token counts.'}
    (ROOT / 'dataset_manifest.json').write_text(json.dumps(report, indent=2) + '\\n')
    print(json.dumps(report))

'''
s=s[:start]+new+s[end:]
p.write_text(s)
compile(s, str(p), 'exec')
print('Revised executable factory: explicit observed-progress checklist; complete verified decision trajectories; historical comparison and native-control validation.')
