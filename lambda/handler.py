import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from cost_processor import load_cur
from correlation_engine import correlate

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CUR_PATH = os.path.join(BASE_DIR, "mock-data", "cur_mock.csv")
CLOUDTRAIL_PATH = os.path.join(BASE_DIR, "mock-data", "cloudtrail_mock.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "output", "enriched_costs.json")


def run():
    cur_rows = load_cur(CUR_PATH)

    with open(CLOUDTRAIL_PATH, encoding="utf-8") as f:
        cloudtrail_records = json.load(f)["Records"]

    enriched = correlate(cur_rows, cloudtrail_records)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2)

    print(f"Done — {len(enriched)} rows written to {OUTPUT_PATH}")
    for row in enriched:
        print(f"  {row['service']:12} | {row['resource_id'][:45]:45} | ${row['cost_usd']:.4f} | {row['initiated_by']}")


if __name__ == "__main__":
    run()
