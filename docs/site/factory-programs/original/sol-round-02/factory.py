import argparse
import json
from collections import defaultdict
from pathlib import Path

INPUTS = Path("/inputs")
WORKSPACE = Path("/workspace")
TASK_SOURCE_SETS = {(5874,), (5875, 5893)}


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_tasks():
    source = load_json(INPUTS / "sources.json")
    approved = {record["number"] for record in source["records"]}
    required = {5874, 5875, 5893}
    missing = sorted(required - approved)
    if missing:
        raise ValueError(f"Approved source records are missing: {missing}")

    tasks = [
        {
            "id": "edit-dashboard-membership-issue",
            "source_numbers": [5874],
            "mode": "direct",
            "select_numbers": [5874],
            "changes": {"owner": "Singh", "priority": 2, "score": 5},
            "notes": "Apply the requested fields to the sole selected issue, save them, and verify the saved task.",
        },
        {
            "id": "rank-open-login-issue",
            "source_numbers": [5875, 5893],
            "mode": "rank",
            "where": {"field": "state", "op": "eq", "value": "open"},
            "order_by": [{"field": "updated_at", "direction": "desc"}],
            "limit": 1,
            "changes": {"owner": "Chen", "priority": 1, "score": 8},
            "notes": "Select the highest-ranked issue matching the immutable open-state condition, then save and verify it.",
        },
    ]
    (WORKSPACE / "tasks.json").write_text(
        json.dumps(tasks, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return tasks


def get_examples():
    payload = load_json(INPUTS / "examples.json")
    records = payload if isinstance(payload, list) else payload.get("examples", [])
    if not isinstance(records, list):
        raise ValueError("Unsupported examples.json structure")
    return records


def parse_record_id(record_id):
    parts = record_id.rsplit(":", 2)
    if len(parts) != 3:
        raise ValueError(f"Unexpected record_id: {record_id}")
    return parts[0], int(parts[1]), parts[2]


def matching_decisions():
    grouped = defaultdict(list)
    seen_ids = set()
    for record in get_examples():
        if not isinstance(record, dict) or "record_id" not in record:
            continue
        episode, step, suffix = parse_record_id(record["record_id"])
        source_numbers = tuple(record.get("source_numbers", []))
        if source_numbers not in TASK_SOURCE_SETS or suffix != "decision":
            continue
        if record.get("representation") != "decision" or not isinstance(record.get("messages"), list):
            raise ValueError(f"Malformed approved decision record: {record['record_id']}")
        if record["record_id"] in seen_ids:
            raise ValueError(f"Duplicate record_id: {record['record_id']}")
        seen_ids.add(record["record_id"])
        grouped[episode].append((step, record))

    for items in grouped.values():
        items.sort(key=lambda pair: pair[0])
    return grouped


def emit_training_data():
    grouped = matching_decisions()
    source_sets = {
        tuple(items[0][1]["source_numbers"])
        for items in grouped.values()
        if items
    }
    missing = TASK_SOURCE_SETS - source_sets
    if missing:
        raise ValueError(f"No approved verified episode for source sets: {sorted(missing)}")

    episodes = sorted(grouped, key=lambda episode: (len(grouped[episode]), episode))
    selected = []
    max_length = max(len(grouped[episode]) for episode in episodes)
    for position in range(max_length):
        for episode in episodes:
            if position < len(grouped[episode]):
                selected.append(grouped[episode][position][1])

    output = WORKSPACE / "train_messages.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for record in selected:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
    return len(selected), {episode: len(grouped[episode]) for episode in episodes}


def inspect_examples():
    summary = defaultdict(lambda: {"decision": 0, "history": 0, "sources": None})
    for record in get_examples():
        if not isinstance(record, dict) or "record_id" not in record:
            continue
        episode, _, representation = parse_record_id(record["record_id"])
        if representation in ("decision", "history"):
            summary[episode][representation] += 1
        summary[episode]["sources"] = record.get("source_numbers")
    return dict(sorted(summary.items()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-training", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()

    tasks = build_tasks()
    result = {"task_count": len(tasks)}
    if args.inspect:
        result["examples"] = inspect_examples()
    if args.emit_training:
        count, mixture = emit_training_data()
        result.update({"training_record_count": count, "mixture": mixture})
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
