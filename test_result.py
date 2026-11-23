import argparse
import json
from pathlib import Path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check a saved ChatStat result.")
    parser.add_argument("result", nargs="?", type=Path, help="Path to the saved result JSON")
    result_path = parser.parse_args().result
    if result_path is None:
        checkpoints = Path(__file__).parent / "backend" / ".checkpoints"
        result_path = max(
            checkpoints.glob("*/09_final_result.json"),
            key=lambda path: path.stat().st_mtime,
            default=None,
        )
    if result_path is None:
        parser.error("Pass a result file or generate a ChatStat checkpoint first.")

    with result_path.open(encoding="utf-8") as stream:
        data = json.load(stream, parse_constant=lambda _: None)
    print("Cleaned JSON size:", len(json.dumps(data, allow_nan=False)))
