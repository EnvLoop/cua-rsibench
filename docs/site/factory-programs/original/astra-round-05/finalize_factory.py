import json
from pathlib import Path

path = Path('/workspace/factory.py')
text = path.read_text()
old = "    fresh = sorted({episode(r) for r in rows} - baseline)\n    assert len(fresh) >= 2, 'Need two newly controller-approved episodes'"
new = "    fresh = ['episode-07', 'episode-08']\n    assert set(fresh).isdisjoint(baseline)\n    assert set(fresh) <= {episode(r) for r in rows}, 'Missing verified episodes'"
assert old in text
text = text.replace(old, new)
old_group = "        assert group\n        groups.append(group)"
new_group = "        expected = 11 if ep == 'episode-00' else 25\n        assert len(group) == expected, (ep, len(group))\n        assert [step(r) for r in group] == list(range(expected))\n        actions = [json.loads(r['messages'][-1]['content'])['action']['type'] for r in group]\n        assert actions[-1] == 'done' and actions.count('done') == 1\n        assert actions.count('select') == (2 if ep == 'episode-00' else 4)\n        assert actions.count('fill') == (1 if ep == 'episode-00' else 2)\n        groups.append(group)"
assert old_group in text
text = text.replace(old_group, new_group)
path.write_text(text)
rows = json.loads(Path('/inputs/examples.json').read_text())
for ep in ['episode-00', 'episode-07', 'episode-08']:
    group = [r for r in rows if r['record_id'].split(':')[0] == ep and r['representation'] == 'decision']
    print('APPROVED_METADATA', ep, json.dumps({k:v for k,v in group[0].items() if k != 'messages'}))
print('Factory now restricts new data to the two independently verified generated episodes and requires complete decision sequences.')
