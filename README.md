# Revelio — identity-based AWS cost attribution (proof of concept)

Answers one question FinOps teams ask every month: **who created this resource, and what did it cost?** — without relying on tags.

It joins the AWS Cost and Usage Report (what was billed, per resource) with CloudTrail (who did what, per API call), and produces a cost line per resource with the identity that created it and a confidence level.

This is a local proof of concept, standard-library Python, run against mock data. There is no AWS deployment. The "what it would take for production" section is explicit about that.

---

## The problem

Cost allocation in AWS is built on tags: `Owner`, `Team`, `CostCenter`. In real accounts a large share of resources are untagged or mistagged — created by hand, by CI, by autoscaling, by someone who left. Those costs end up in an "unallocated" bucket that nobody owns.

Yet AWS already knows who created every resource: the `RunInstances`, `CreateBucket`, `CreateDBInstance` call is in CloudTrail, with the IAM identity that made it. That evidence is never joined to the bill.

## The goal

1. Read cost lines from a CUR export and resolve each `lineItem/ResourceId`.
2. Build an index from CloudTrail: resource id → identity that created it (or, failing that, last acted on it).
3. Join the two and label every cost line with an identity and a confidence level.
4. Aggregate by identity, service and confidence so a FinOps analyst can see who owns unallocated spend, and where the remaining gaps are.

## What the POC does today

| Feature | Where | Notes |
|---|---|---|
| CUR parsing (real column names, real resource-id formats) | `src/revelio/cur.py` | S3 = bucket name, Lambda/RDS/DynamoDB = ARN, EC2 = instance id |
| CloudTrail identity resolution | `src/revelio/cloudtrail.py` | IAM users, **assumed roles** (SSO login or CI session name + role), root, AWS services |
| Creation vs activity events | `src/revelio/cloudtrail.py` | 6 creation events, 11 activity events across EC2, S3, RDS, Lambda, DynamoDB |
| Priority rules | `build_index()` | earliest creation event wins; otherwise latest activity event |
| Confidence scoring | `src/revelio/engine.py` | HIGH = creation event · MEDIUM = activity event only · LOW = no evidence |
| Aggregation | `summarize()` | by identity, service, confidence; attribution rate weighted by cost |
| CLI | `python -m revelio` | writes `enriched_costs.json` + `summary.json` |
| Streamlit dashboard | `dashboard/app.py` | KPIs, cost by identity / confidence / service, unattributed list |
| Tests | `tests/` | 26 pytest cases, including the "creator ≠ last user" case |
| CI | GitHub Actions | flake8 + pytest on Python 3.10 and 3.12 + CLI smoke run |

Not implemented: AWS Config as a second evidence source, multi-account, any AWS deployment. See roadmap.

## Why "creation event" matters

The first version of this POC used `PutObject` and `Invoke` as evidence of ownership. That attributes a Lambda to whoever invoked it last, and a bucket to whatever pipeline wrote to it — the opposite of what a chargeback needs. The engine now separates the two:

- a **creation** event (`RunInstances`, `CreateBucket`, `CreateFunction20150331`, …) proves who created the resource → HIGH;
- an **activity** event (`StopInstances`, `PutObject`, `ModifyDBInstance`, …) only proves someone used it → MEDIUM, and only if no creation event exists in the trail (typically because the resource predates the 90-day CloudTrail event-history window).

`tests/test_engine.py::test_creator_not_last_user_is_attributed` pins that behaviour: Alice creates an instance, Bob stops it two days later, the cost goes to Alice.

## Mock dataset

The mock is built to be unflattering on purpose. `mock-data/cur_mock.csv` has 168 cost lines over 3 days for 14 resources; `mock-data/cloudtrail_mock.json` has 15 events. Running the engine on it gives:

```
168 cost lines, 14 resources
total $83.09  attributed $59.55 (72%)  unattributed $23.54

identity                               cost  resources
github-actions-deploy                 23.62  3
unattributed                          23.54  3
charlie@corp.com                      21.40  2
bob                                    6.57  1
alice@corp.com                         3.51  2
autoscaling.amazonaws.com              3.28  1
dana@corp.com                          0.63  1
root                                   0.54  1
```

The 72 % is a property of the mock, not a claim about real accounts: three resources (an old EC2 instance, a 2019 backup bucket, a read replica) have no CloudTrail trace at all, which is exactly what happens with resources older than the retention window. The interesting output is the list of *what* is unattributed and why.

## Run it

```bash
pip install -e ".[dev]"
pytest -q

python -m revelio --cur mock-data/cur_mock.csv --cloudtrail mock-data/cloudtrail_mock.json
# → output/enriched_costs.json, output/summary.json

pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

To try it on real data: export a CUR (CSV, with `lineItem/ResourceId` enabled) and a CloudTrail lookup (`aws cloudtrail lookup-events --output json` or an S3 trail file). The parsers only read the columns listed in `cur.py::REQUIRED_COLUMNS`.

## Output schema

Each enriched line:

```json
{
  "resource_id": "i-0a1b2c3d4e5f60001",
  "service": "AmazonEC2",
  "usage_start": "2024-03-01T00:00:00Z",
  "cost_usd": 0.2736,
  "attributed_to": "alice@corp.com",
  "identity_type": "AssumedRole",
  "role": "AWSReservedSSO_DeveloperAccess_abc123",
  "confidence": "HIGH",
  "evidence_event": "RunInstances",
  "evidence_time": "2024-03-01T08:12:00Z"
}
```

## Known limits of this POC

- CloudTrail event history only covers 90 days; older resources need an organisation trail archived to S3, or AWS Config resource history.
- Resources created by CloudFormation / Terraform are attributed to the CI role (correct) but not to the engineer who merged the change — that needs a second join on the deployment pipeline.
- Costs are attributed to the *creator*, not shared. A bucket used by three teams is still charged to whoever created it. Shared-cost allocation is a separate problem.
- Cross-account: the mock is single-account. The resource-id → account mapping is in the CUR (`lineItem/UsageAccountId`) but not used yet.

## What it would take for production

This is a roadmap, not a description of the current code.

1. Storage: CUR delivered to S3 in Parquet; CloudTrail organisation trail to S3.
2. Compute: run the same engine as a Glue Python shell job or a scheduled Lambda (it has no dependencies), partitioned by billing month.
3. Query: Glue crawler + Athena over the enriched output; the summary becomes a view.
4. Second evidence source: AWS Config `configurationItem` history for resources with no CloudTrail creation event.
5. Infrastructure as code and CI/CD for the above.

## Project history

The first commit was a 90-line script joining 5 CUR rows with 5 CloudTrail events on `resource_id`. This version keeps the same idea and fixes what a real trail would break: assumed-role identities, multiple events per resource, creation vs usage, and a dataset where not everything resolves.

## License

MIT
