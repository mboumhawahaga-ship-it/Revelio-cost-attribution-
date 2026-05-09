import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))

from cost_processor import load_cur
from correlation_engine import build_resource_index, correlate

CUR_PATH = os.path.join(os.path.dirname(__file__), "..", "mock-data", "cur_mock.csv")
CLOUDTRAIL_PATH = os.path.join(os.path.dirname(__file__), "..", "mock-data", "cloudtrail_mock.json")


def load_cloudtrail():
    import json
    with open(CLOUDTRAIL_PATH, encoding="utf-8") as f:
        return json.load(f)["Records"]


def test_load_cur_returns_rows():
    rows = load_cur(CUR_PATH)
    assert len(rows) > 0


def test_cur_has_expected_columns():
    rows = load_cur(CUR_PATH)
    assert "lineItem/ResourceId" in rows[0]
    assert "lineItem/UnblendedCost" in rows[0]
    assert "resourceTags/user:Owner" not in rows[0]
    assert "resourceTags/user:Project" not in rows[0]


def test_resource_index_maps_instance_to_user():
    records = load_cloudtrail()
    index = build_resource_index(records)
    assert index.get("i-0abc123def456789a") == "alice@corp.com"
    assert index.get("i-0def456abc789012b") == "bob@corp.com"


def test_correlate_enriches_all_rows():
    rows = load_cur(CUR_PATH)
    records = load_cloudtrail()
    enriched = correlate(rows, records)
    assert len(enriched) == len(rows)
    for row in enriched:
        assert "initiated_by" in row
        assert "cost_usd" in row


def test_correlate_alice_ec2():
    rows = load_cur(CUR_PATH)
    records = load_cloudtrail()
    enriched = correlate(rows, records)
    alice_ec2 = next(r for r in enriched if r["resource_id"] == "i-0abc123def456789a")
    assert alice_ec2["initiated_by"] == "alice@corp.com"
    assert alice_ec2["cost_usd"] == 0.0416
    assert "owner_tag" not in alice_ec2
    assert "project_tag" not in alice_ec2


def test_all_services_resolved_via_cloudtrail():
    rows = load_cur(CUR_PATH)
    records = load_cloudtrail()
    enriched = correlate(rows, records)
    for row in enriched:
        assert row["initiated_by"] != "not-found-in-cloudtrail", \
            f"{row['resource_id']} not resolved by CloudTrail"


def test_no_tags_needed_for_attribution():
    """Attribution must work even with no tag columns in CUR."""
    rows = [{
        "lineItem/ResourceId": "i-0abc123def456789a",
        "lineItem/ProductCode": "AmazonEC2",
        "lineItem/Operation": "RunInstances",
        "lineItem/UsageStartDate": "2024-01-01T00:00:00Z",
        "lineItem/UsageAmount": "1.0",
        "lineItem/UnblendedCost": "0.0416",
    }]
    records = load_cloudtrail()
    enriched = correlate(rows, records)
    assert enriched[0]["initiated_by"] == "alice@corp.com"


if __name__ == "__main__":
    tests = [test_load_cur_returns_rows, test_cur_has_expected_columns,
             test_resource_index_maps_instance_to_user, test_correlate_enriches_all_rows,
             test_correlate_alice_ec2, test_all_services_resolved_via_cloudtrail,
             test_no_tags_needed_for_attribution]
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
