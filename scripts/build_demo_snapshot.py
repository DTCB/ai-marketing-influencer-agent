"""Generate the bundled demo case from the same business logic as the API."""

import argparse
import json
from pathlib import Path

from modules.web_campaign import build_demo_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the bundled case matches its sources")
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "web" / "demo.json"
    snapshot = json.dumps(build_demo_snapshot(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != snapshot:
            raise SystemExit("Run python -m scripts.build_demo_snapshot to update web/demo.json.")
    else:
        target.write_text(snapshot, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
