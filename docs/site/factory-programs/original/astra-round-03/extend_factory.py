from pathlib import Path
p = Path('/workspace/factory.py')
s = p.read_text()
s = s[:s.index("if __name__ == '__main__':")]
s += '''def build():
    import hashlib
    from collections import Counter
    approved = json.loads((INPUTS / 'examples.json').read_text())
    by_id = {r['record_id']: r for r in approved}
    assert len(by_id) == len(approved)
    # Preserve direct editing; emphasize complete multi-target selection and editing.
    # Keep three inherited ranking transitions as additional evidence/selection practice.
    policy = {
        'episode-00': list(range(11)),
        'episode-01': [8, 10, 12],
        'episode-02': [i for i in range(27) if i != 4],
        'episode-03': [i for i in range(26) if i not in (10, 11)],
    }
    groups = {}
    seen = set()
    duplicates = []
    for episode, steps in policy.items():
        groups[episode] = []
        for step in steps:
            record_id = f'{episode}:{step}:decision'
            row = by_id[record_id]
            assert row['source_split'] == 'train'
            assert row['representation'] == 'decision'
            assert row['episode_sha256'] and row['case_sha256']
            assert row['messages'][-1]['role'] == 'assistant'
            output = json.loads(row['messages'][-1]['content'])
            assert output['action']['type'] in ('click', 'fill', 'select', 'back', 'done', 'scroll', 'wait')
            digest = hashlib.sha256(json.dumps(row['messages'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if digest in seen:
                duplicates.append(record_id)
                continue
            seen.add(digest)
            groups[episode].append(row)
    # Deterministic round-robin interleaving preserves within-episode order while
    # exposing both selection families early in the fixed training schedule.
    ordered = []
    episode_order = ['episode-03', 'episode-02', 'episode-00', 'episode-01']
    for offset in range(max(map(len, groups.values()))):
        for episode in episode_order:
            if offset < len(groups[episode]):
                ordered.append(groups[episode][offset])
    assert 1 <= len(ordered) <= 64
    payload = ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\\n' for r in ordered)
    assert len(payload.encode()) <= 2_000_000
    destination = ROOT / 'train_messages.jsonl'
    destination.write_text(payload)
    reread = [json.loads(line) for line in destination.read_text().splitlines()]
    assert reread == ordered
    assert all(r == by_id[r['record_id']] for r in reread)
    sizes = [sum(len(json.dumps(m['content'], ensure_ascii=False)) for m in r['messages']) for r in ordered]
    report = {
        'records': len(ordered),
        'episodes': dict(Counter(r['record_id'].split(':')[0] for r in ordered)),
        'actions': dict(Counter(json.loads(r['messages'][-1]['content'])['action']['type'] for r in ordered)),
        'representation': 'decision',
        'duplicates_removed': duplicates,
        'excluded': {'episode-02:4:decision': 'Malformed filter action', 'episode-03:10:decision': 'Redundant RUNBOOK revisit', 'episode-03:11:decision': 'Redundant RUNBOOK revisit'},
        'bytes': len(payload.encode()),
        'message_characters_total': sum(sizes),
        'message_characters_max': max(sizes),
        'token_budget_note': 'No tokenizer installed; character sizes are diagnostics, not verified token counts.',
        'sha256': hashlib.sha256(payload.encode()).hexdigest(),
        'record_ids': [r['record_id'] for r in ordered],
        'validation': 'Every exported object equals an approved controller record. No messages or provenance modified.',
        'hypothesis': 'Selection evidence, explicit edit transitions and second-target continuation may address premature completion; student improvement is untested.'
    }
    (ROOT / 'dataset_manifest.json').write_text(json.dumps(report, indent=2) + '\\n')
    print(json.dumps(report))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['generate', 'build'], default='generate', nargs='?')
    args = parser.parse_args()
    {'generate': generate, 'build': build}[args.command]()
'''
p.write_text(s)
compile(s, str(p), 'exec')
print('Extended factory.py with reproducible approved-record selection, deduplication, interleaving and export.')
