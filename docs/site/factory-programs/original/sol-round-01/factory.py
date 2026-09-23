import argparse
import json
from pathlib import Path

INPUTS = Path("/inputs")
WORKSPACE = Path("/workspace")
VERIFIED_EPISODES = ("episode-00", "episode-01")


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_tasks():
    source = load_json(INPUTS / "sources.json")
    approved = {record["number"]: record for record in source["records"]}

    required = {5869, 5871, 5874, 5875, 5893, 5894}
    missing = sorted(required - approved.keys())
    if missing:
        raise ValueError(f"Approved source records are missing: {missing}")

    tasks = [
        {
            "id": "edit-ldap-notification-issue",
            "source_numbers": [5869, 5871],
            "mode": "direct",
            "select_numbers": [5869],
            "changes": {"owner": "Chen", "priority": 2, "score": 5},
            "notes": "Update only the selected LDAP notification issue and leave the comparison issue unchanged.",
        },
        {
            "id": "rank-recent-open-security",
            "source_numbers": [5874, 5875, 5893, 5894],
            "mode": "rank",
            "where": {
                "all": [
                    {"field": "state", "op": "eq", "value": "open"},
                    {"field": "updated_at", "op": "gte", "value": "2026-08-30T00:00:00Z"},
                ]
            },
            "order_by": [{"field": "updated_at", "direction": "desc"}],
            "limit": 2,
            "changes": {"owner": "Rivera", "priority": 1, "score": 8},
            "notes": "Prioritize the two most recently updated matching open issues.",
        },
    ]

    (WORKSPACE / "tasks.json").write_text(
        json.dumps(tasks, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return tasks


def parse_record_id(record_id):
    parts = record_id.split(":")
    if len(parts) != 3:
        raise ValueError(f"Unexpected record_id: {record_id}")
    episode, step_text, representation = parts
    return episode, int(step_text), representation


def emit_training_data():
    payload = load_json(INPUTS / "examples.json")
    records = payload if isinstance(payload, list) else payload.get("examples", [])
    if not isinstance(records, list):
        raise ValueError("Unsupported examples.json structure")

    by_episode = {episode: [] for episode in VERIFIED_EPISODES}
    seen = set()
    for record in records:
        if not isinstance(record, dict) or "record_id" not in record:
            continue
        episode, step, representation = parse_record_id(record["record_id"])
        if episode not in by_episode or representation != "decision":
            continue
        if record.get("representation") != "decision" or "messages" not in record:
            raise ValueError(f"Malformed approved decision record: {record['record_id']}")
        if record["record_id"] in seen:
            raise ValueError(f"Duplicate approved record_id: {record['record_id']}")
        seen.add(record["record_id"])
        by_episode[episode].append((step, record))

    for episode, episode_records in by_episode.items():
        if not episode_records:
            raise ValueError(f"No approved decision records for {episode}")
        episode_records.sort(key=lambda item: item[0])

    # Interleave episodes while preserving each workflow's internal order. This
    # prevents the longer ranking rollout from forming one large contiguous block.
    selected = []
    max_length = max(len(items) for items in by_episode.values())
    for position in range(max_length):
        for episode in VERIFIED_EPISODES:
            items = by_episode[episode]
            if position < len(items):
                selected.append(items[position][1])

    output = WORKSPACE / "train_messages.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for record in selected:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
    return len(selected), {episode: len(items) for episode, items in by_episode.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-training", action="store_true")
    args = parser.parse_args()

    tasks = build_tasks()
    count = 0
    mixture = {}
    if args.emit_training:
        count, mixture = emit_training_data()
    print(json.dumps({"task_count": len(tasks), "training_record_count": count, "mixture": mixture}))


if __name__ == "__main__":
    main()
