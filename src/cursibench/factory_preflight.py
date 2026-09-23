"""Exact local token accounting before reserving or spending training resources."""
import hashlib
import json
from pathlib import Path
from .training_contract import schedule


class SubmissionRejected(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__(json.dumps(report, sort_keys=True))


def inspect_rows(rows, tokenizer, steps=32, profile='factory-v1'):
    config, indices = schedule(len(rows), steps, profile)
    lengths = []
    violations = []
    for row in rows:
        messages = row['messages']
        prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=False,
                    add_generation_prompt=True, enable_thinking=False)
        prefix = tokenizer.encode(prompt, add_special_tokens=False)
        target = tokenizer.encode(messages[-1]['content'], add_special_tokens=False)
        if tokenizer.eos_token_id is not None:
            target.append(tokenizer.eos_token_id)
        total = len(prefix) + len(target)
        lengths.append((total, len(target)))
        if total > config['sequence_tokens'] or len(target) > 512:
            violations.append({'record_id': row.get('record_id'),
                               'sequence_tokens': total, 'target_tokens': len(target)})
    scheduled = sum(lengths[i][0] - 1 for batch in indices for i in batch)
    report = {'records': len(rows), 'scheduled_tokens': scheduled,
              'max_sequence': max(x[0] for x in lengths),
              'max_target': max(x[1] for x in lengths),
              'record_violations': violations,
              'limits': {'sequence_tokens': config['sequence_tokens'],
                         'scheduled_tokens': config['scheduled_tokens'], 'target_tokens': 512}}
    report['accepted'] = not violations and scheduled <= config['scheduled_tokens']
    return report


def preflight_rows(rows):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen3.5-4B', local_files_only=True)
    report = inspect_rows(rows, tokenizer)
    if not report['accepted']:
        raise SubmissionRejected(report)
    return report


def preflight(data):
    data = Path(data)
    rows = [json.loads(line) for line in data.read_text().splitlines() if line.strip()]
    report = preflight_rows(rows)
    return dict(report, data_sha256=hashlib.sha256(data.read_bytes()).hexdigest())
