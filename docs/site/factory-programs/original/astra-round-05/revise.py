from pathlib import Path
p = Path('/workspace/factory.py')
s = p.read_text()
s = s.replace("workflow = 'Inspect", "workflow = 'Keep every local task status unchanged: do not close, archive, move, or delete any task. Only owner, priority and complexity may change. Inspect")
s = s.replace("Finish only after every selected task is verified.", "Finish only after every selected task is verified. Saved tasks must remain open in their original project and column.")
s = s.replace('fresh-rank-newest-two-v4', 'fresh-rank-newest-two-v5').replace('fresh-allocation-dependent-two-v4', 'fresh-allocation-dependent-two-v5').replace('fresh-direct-single-v4', 'fresh-direct-single-v5')
p.write_text(s)
print('Revised generator workflow notes to explicitly preserve local status and project placement after saving. Selection logic remains unchanged.')
