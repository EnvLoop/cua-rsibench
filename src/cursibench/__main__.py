import argparse
import json
from .benchmark import run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CUA-RSIBench self-improvement loop")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    result = run_benchmark(args.rounds)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
