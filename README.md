# Revelio — AWS Cost Attribution Engine

**Attribute every dollar of AWS spend to an IAM identity, without relying on tags.**

---

## Business Problem

In a multi-team AWS environment, Finance asks the same question every month: *who is responsible for this cost?*

Tags are the standard answer — but they fail in practice:

- Engineers forget to tag resources at creation time
- Ephemeral infrastructure (Lambda, ECS tasks, Spot instances) is never tagged
- CI/CD pipelines assume roles that leave no team identifier
- Shared infrastructure (NAT Gateway, RDS clusters, EKS nodes) cannot be tagged to one team

The result is **unallocated spend** — cost lines that Finance cannot charge back and Engineering cannot explain. In organizations with 10+ teams and $50k+/month in AWS, this gap is typically 30–50% of total spend (AWS FinOps benchmark, Flexera 2024 State of the Cloud Report).

The usual fix — stricter tagging policies — only works on new resources. It does nothing about existing infrastructure or the identities behind assumed roles.

---

## Use Cases

### Finance — Monthly Chargeback

Without attribution, Finance sends each team an estimate based on account-level cost allocation. With Revelio, every line item in the CUR carries an `initiated_by` field (IAM user or role). Finance can produce an exact per-team invoice, not an estimate.

*Typical impact: reduces disputed chargeback lines by the share of spend previously flagged as "unallocated" — estimated at 30–50% of total cost rows in environments with mixed tagging compliance.*

### Engineering Lead — Cost Accountability

An engineering lead wants to know which engineers or pipelines are driving cost spikes. Tag-based dashboards show cost by resource type, not by creator. Revelio surfaces the top cost-generating IAM identities directly, including CI/CD assumed roles (`sessionIssuer` resolution). The lead can act on a specific identity, not a vague service category.

### CTO / Platform Team — Cost Governance without Blocking Deployments

Enforcing tags at deploy time (SCPs, CFN hooks) blocks engineers and creates friction. Revelio takes the opposite approach: ingest first, attribute retroactively from audit logs. There is no blocking gate. The platform team gets attribution coverage immediately across all existing resources, then uses the data to build targeted tag enforcement where it matters most.

---

## Solution Architecture

```
AWS CUR (Parquet)          ─┐
AWS CloudTrail (JSON)      ─┼──► S3 data lake ──► Glue crawlers ──► Glue Catalog
AWS Config snapshots (JSON) ─┘
                                                         │
                                          Glue PySpark job (daily 05:00 UTC)
                                          correlate.py: CUR × CloudTrail × Config
                                                         │
                                                 enriched-data/ (S3 Parquet)
                                                         │
                                              Athena views ──► dashboards
```

Three data sources feed a single S3 bucket (`raw-data/`). Three Glue crawlers run nightly to keep the Glue Catalog up to date. At 05:00 UTC, a scheduled Glue trigger launches the PySpark correlation job. The job reads CUR line items, looks up the creating identity in CloudTrail for each `resource_id`, falls back to AWS Config for resources without a CloudTrail match, and writes enriched output to `enriched-data/`.

The choice of Glue + Athena over a Lambda-based pipeline is deliberate: CUR files are Parquet, sometimes several GB per month. PySpark handles the join at scale without per-invocation memory limits.

---

## What I Built

### Correlation Engine (`lambda/correlation_engine.py`)

The core attribution logic. For each CUR line item, it extracts the `resource_id` and resolves the creating IAM identity from CloudTrail:

| CloudTrail event | Resource ID extracted |
|---|---|
| `RunInstances` | `instanceId` from `responseElements.instancesSet` |
| `CreateDBInstance` | `dBInstanceArn` from `responseElements` |
| `PutObject` | `arn:aws:s3:::<bucketName>` from `requestParameters` |
| `Invoke` | function name (with ARN fallback for Lambda) |

Lambda resources require a specific fallback: the CUR stores the full ARN (`arn:aws:lambda:region:account:function:name`), while CloudTrail only stores the function name. The engine splits on `:function:` and retries the lookup to avoid false negatives.

Output field: `initiated_by` — IAM username, role session name, or `not-found-in-cloudtrail`.

### KPI Calculator (`lambda/kpi.py`)

Computes from the enriched output:
- **Attribution rate** — % of total cost linked to an identity
- **Unknown cost %** — share of spend with no CloudTrail match
- **Top spenders** — top 3 IAM identities by attributed cost
- **Top unattributed services** — where the gaps are concentrated

On the included mock dataset (EC2, S3, RDS, Lambda across 6 identities): attribution rate lands at ~46%, with S3 analytics buckets and legacy EC2 instances as the main unattributed drivers. In a real environment with a complete CloudTrail history, this rate is expected to reach 70–85% depending on how long the trail has been active.

### Terraform Infrastructure (`cost-allocation-platform/`)

Three modules, deployed in sequence:

**`storage`** — single S3 bucket with `raw-data/` and `enriched-data/` prefixes, KMS CMK, lifecycle policy on enriched data.

**`data-collection`** — wires the three sources:
- CUR report definition (Parquet format, `SPLIT_COST_ALLOCATION_DATA`, Athena artifact) — `us-east-1` provider required, AWS limitation
- CloudTrail (multi-region, `WriteOnly` management events, KMS encrypted, log file validation)
- AWS Config recorder (all resource types, all regions)
- Three Glue crawlers (one per source), each with a separate least-privilege IAM role
- Glue Catalog tables with **Partition Projection** — Athena computes partitions mathematically, eliminating `GetPartitions` calls and the associated latency on large datasets

**`correlation-engine`** — the processing layer:
- Glue job v4.0, PySpark, `job-bookmark-enable` to process only new CUR partitions
- Glue Security Configuration: SSE-KMS on S3, CSE-KMS on job bookmarks, KMS on CloudWatch logs
- Scheduled trigger at `cron(0 5 * * ? *)` — no Lambda wrapper needed
- `max_concurrent_runs = 1` — prevents duplicate runs on overlapping schedules
- `max_retries = 0` — intentional (see Trade-offs)
- SNS alert on job failure
- Athena views defined in Terraform for downstream querying

### Demo Dashboard (`demo/dashboard.py`)

Local visualization of `enriched_costs.json`: KPI cards (attribution rate, total cost, unknown cost), before/after resource attribution comparison, cost breakdown by creator and by service.

---

## FinOps KPIs

| KPI | On mock dataset | At scale (estimated) |
|---|---|---|
| Attribution rate | ~46% | 70–85% with full CloudTrail history |
| Unknown cost % | ~54% | 15–30% (legacy + shared infra residual) |
| Top unattributed service | AmazonS3 (~$38 / 77% of gaps) | Shared buckets, analytics pipelines |
| Lambda attribution | 67% (2/3 functions) | Improves with consistent function naming |

Estimates at scale are based on FinOps Foundation benchmarks for organizations with 12+ months of CloudTrail history. The main remaining gap after attribution is shared infrastructure (NAT Gateway, EKS control plane, RDS clusters shared across teams) — which requires a cost-splitting model, not attribution.

---

## Trade-offs

**No retries on the Glue job.** If the CUR data for a given month is incomplete or corrupted, a retry would produce a partial enriched dataset and write it as authoritative output. The design fails fast instead: the SNS alert fires, a human reviews the raw data, and the job is re-triggered manually after the issue is resolved. The previous enriched dataset remains queryable in S3.

**Attribution is append-only.** The engine never deletes or overwrites enriched data for past months. If a CloudTrail event surfaces late (CloudTrail delivers within 15 minutes but occasionally delays), the next daily run picks it up via job bookmarks. Historical attribution improves over time without backfilling.

**CloudTrail as source of truth, not tags.** This means attribution is only as complete as the CloudTrail history. Resources created before the trail was active, or in regions not covered by the multi-region trail, will appear as `not-found-in-cloudtrail`. AWS Config snapshots partially cover this gap by providing resource metadata without requiring the creation event.

**No real-time attribution.** The pipeline runs once per day. This is a deliberate cost decision: Glue + Athena on a daily batch is significantly cheaper than a streaming pipeline (Kinesis + Lambda) for a use case where Finance needs monthly reports, not minute-level latency.

---

## Setup

### Prerequisites

- AWS account with CUR enabled (Billing → Cost & Usage Reports)
- CloudTrail active in all target regions
- Terraform >= 1.5
- AWS credentials with permissions for S3, Glue, CloudTrail, Config, IAM, KMS

### Deploy

```bash
cd cost-allocation-platform

cp terraform.tfvars.example terraform.tfvars
# Edit: aws_account_id, aws_region, alert_email

terraform init
terraform plan
terraform apply
```

Terraform creates all resources in dependency order: S3 + KMS first, then data sources and crawlers, then the correlation job.

The CUR report takes up to 24 hours for the first delivery after creation. CloudTrail and Config start delivering immediately.

### Run locally (mock data)

```bash
# Correlation engine
python lambda/handler.py

# KPI output
python -c "from lambda.kpi import compute_kpis, print_kpis; print_kpis(compute_kpis('output/enriched_costs.json'))"

# Dashboard
pip install -r demo/requirements.txt
python demo/dashboard.py
```

---

## Why This Project Matters

Tag-based FinOps is the default approach. It works well when tagging compliance is high and infrastructure is stable. It breaks down in practice: ephemeral resources, CI/CD pipelines, assumed roles, and legacy infrastructure all produce cost that tags cannot explain.

This project builds the alternative: **identity-based cost attribution using audit logs**. It treats CloudTrail as the authoritative record of who created what, and joins that record against the CUR at the resource level.

The design choices — Glue over Lambda, batch over streaming, fail-fast over retry — reflect production constraints: cost control, data integrity, and operational simplicity over feature completeness.

Relevant for: Cloud FinOps Engineer, Platform Engineer, Cloud Cost Optimization, FinOps Practitioner roles.
