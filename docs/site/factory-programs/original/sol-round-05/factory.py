import argparse
import json
from pathlib import Path

INPUTS = Path("/inputs")
WORKSPACE = Path("/workspace")
SELECTED_EPISODES = ("episode-06", "episode-05")
EXPECTED_SOURCES = {
    "episode-06": (5876,),
    "episode-05": (5877, 5894),
}


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_tasks():
    payload = load_json(INPUTS / "sources.json")
    approved = {record["number"] for record in payload["records"]}
    required = {5876, 5878, 5879}
    missing = sorted(required - approved)
    if missing:
        raise ValueError(f"Approved source records are missing: {missing}")

    tasks = [
        {
            "id": "edit-activity-email-exposure",
            "source_numbers": [5876],
            "mode": "direct",
            "select_numbers": [5876],
            "changes": {"owner": "Singh", "priority": 2, "score": 5},
            "notes": "Edit the sole selected issue, save all requested fields, and verify the saved task values.",
        },
        {
            "id": "rank-open-project-probing",
            "source_numbers": [5878, 5879],
            "mode": "rank",
            "where": {"field": "state", "op": "eq", "value": "open"},
            "order_by": [{"field": "updated_at", "direction": "desc"}],
            "limit": 1,
            "changes": {"owner": "Chen", "priority": 1, "score": 8},
            "notes": "Apply the requested changes only to the highest-ranked issue matching the immutable open-state condition, then save and verify it.",
        },
    ]
    (WORKSPACE / "tasks.json").write_text(
        json.dumps(tasks, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return tasks


def approved_examples():
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


def select_training_records():
    by_episode = {episode: [] for episode in SELECTED_EPISODES}
    seen_ids = set()

    for record in approved_examples():
        if not isinstance(record, dict) or "record_id" not in record:
            continue
        episode, step, representation = parse_record_id(record["record_id"])
        if episode not in by_episode or representation != "decision":
            continue
        if record.get("representation") != "decision":
            raise ValueError(f"Representation mismatch: {record['record_id']}")
        if tuple(record.get("source_numbers", [])) != EXPECTED_SOURCES[episode]:
            raise ValueError(f"Unexpected provenance for {record['record_id']}")
        if not isinstance(record.get("messages"), list):
            raise ValueError(f"Malformed approved record: {record['record_id']}")
        if record["record_id"] in seen_ids:
            raise ValueError(f"Duplicate approved record: {record['record_id']}")
        seen_ids.add(record["record_id"])
        by_episode[episode].append((step, record))

    for episode, records in by_episode.items():
        records.sort(key=lambda item: item[0])
        if not records:
            raise ValueError(f"No approved decision records for {episode}")
        expected_steps = list(range(records[-1][0] + 1))
        actual_steps = [step for step, _ in records]
        if actual_steps != expected_steps:
            raise ValueError(f"Incomplete decision sequence for {episode}: {actual_steps}")

    selected = []
    max_steps = max(len(records) for records in by_episode.values())
    for position in range(max_steps):
        for episode in SELECTED_EPISODES:
            records = by_episode[episode]
            if position < len(records):
                selected.append(records[position][1])
    return selected, {episode: len(records) for episode, records in by_episode.items()}


def emit_training_data():
    selected, mixture = select_training_records()
    output = WORKSPACE / "train_messages.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for record in selected:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
    return len(selected), mixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-training", action="store_true")
    args = parser.parse_args()

    tasks = build_tasks()
    result = {"task_count": len(tasks)}
    if args.emit_training:
        count, mixture = emit_training_data()
        result.update({"training_record_count": count, "mixture": mixture})
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
