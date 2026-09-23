from pathlib import Path
p = Path('/workspace/factory.py')
s = p.read_text()
s = s[:s.index("if __name__ == '__main__':")]
s += '''def assemble():
    import hashlib
    from collections import Counter
    approved = json.loads((INPUTS / 'examples.json').read_text())
    canonical = lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    membership = {canonical(row) for row in approved}
    # Each decision retains its original observation and incoming memory.
    # Remove an initial navigation detour and a redundant return/reopen pair.
    policy = [('episode-00', set()), ('episode-01', {0, 10, 11})]
    selected, seen, audit = [], set(), []
    for episode_id, excluded in policy:
        episode = json.loads((INPUTS / (episode_id + '.json')).read_text())
        verification = episode['verification']
        assert verification['success'] is True
        assert not verification['wrong_tables']
        assert verification['correct_target_tasks'] == verification['target_tasks'] == 1
        assert episode.get('infrastructure_error') is None
        trace = {int(item['step']): item for item in episode['trace']}
        candidates = [row for row in approved if row['representation'] == 'decision' and row['record_id'].startswith(episode_id + ':')]
        candidates.sort(key=lambda row: int(row['record_id'].split(':')[1]))
        retained = []
        for row in candidates:
            step = int(row['record_id'].split(':')[1])
            if step in excluded:
                continue
            answer = json.loads(row['messages'][-1]['content'])
            item = trace[step]
            assert json.loads(item['response']) == answer
            outcome = item['outcome']
            kind = answer['action']['type']
            assert (outcome.get('done') is True if kind == 'done' else outcome.get('executed') == kind)
            assert not outcome.get('error')
            fingerprint = canonical(row['messages'])
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            assert canonical(row) in membership
            selected.append(row)
            retained.append(step)
        assert retained
        assert any(json.loads(row['messages'][-1]['content'])['action']['type'] == 'done' for row in selected if row['record_id'].startswith(episode_id + ':'))
        audit.append({'episode': episode_id, 'verification': verification, 'retained_steps': retained, 'excluded_steps': sorted(excluded)})
    assert 1 <= len(selected) <= 256
    text = ''.join(json.dumps(row, ensure_ascii=False) + '\\n' for row in selected)
    assert len(text.encode('utf-8')) <= 2_000_000
    target = ROOT / 'train_messages.jsonl'
    target.write_text(text)
    reread = [json.loads(line) for line in target.read_text().splitlines()]
    assert reread == selected
    assert all(canonical(row) in membership for row in reread)
    report = {'records': len(selected), 'bytes': len(text.encode('utf-8')), 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'representation': 'decision', 'ordering': 'direct then ranking; chronological within each episode', 'deduplication': 'exact canonical messages; no repeated representations', 'episode_counts': dict(Counter(row['record_id'].split(':')[0] for row in selected)), 'episodes': audit}
    (ROOT / 'dataset_audit.json').write_text(json.dumps(report, indent=2) + '\\n')
    print(json.dumps(report))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['generate', 'assemble'], default='generate', nargs='?')
    args = parser.parse_args()
    if args.command == 'generate':
        generate()
    else:
        assemble()
'''
p.write_text(s)
print('Extended factory.py with verified decision-record assembly and audit output.')
