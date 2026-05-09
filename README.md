# cur-explorer

## Status

> ⚠️ This is a proof of concept using mock data.
> The correlation logic is validated. Production integration (real CUR + CloudTrail) is the next step.

**Next steps:**
- [ ] Connect to real S3 CUR export
- [ ] Query live CloudTrail via boto3
- [ ] Deploy as AWS Lambda

---

## Project Overview

**cur-explorer** is a FinOps utility designed to solve the "Missing Tag" problem in AWS cost attribution. By correlating billing data with audit logs, it identifies the specific IAM identity responsible for costs, even when resources are untagged.

---

## The Problem

Traditional cost allocation relies heavily on AWS Tags. However, in many environments, tagging is inconsistent, incomplete, or bypassed. This creates "dark costs" that cannot be attributed to a specific owner or team.

---

## The Solution: Tagless Attribution

Instead of relying on metadata (tags), this tool cross-references two primary data sources:

- **AWS Cost and Usage Report (CUR)** — provides granular cost data per `resource_id`
- **AWS CloudTrail** — tracks the API calls that created or modified those resources

By joining these datasets on the `resource_id`, cur-explorer determines the `initiated_by` identity directly from the event source.

---

## How it Works

1. **Ingestion** — parses the CUR files to extract costs at the resource level
2. **Correlation** — queries CloudTrail events to find the `Create*` or `Run*` actions associated with those specific Resource IDs
3. **Enrichment** — maps the IAM User, Role, or Session that triggered the resource creation to the corresponding cost line items
4. **Output** — generates an `enriched_costs.json` file

```
CUR (resource_id + cost)  +  CloudTrail (resource_id + user)  →  enriched_costs.json
```

---

## Key Output: enriched_costs.json

The final output provides a definitive link between spend and identity:

```json
{
  "resource_id": "i-0a123456789db",
  "cost_usd": 14.50,
  "initiated_by": "arn:aws:iam::123456789012:user/j.doe",
  "operation": "RunInstances"
}
```

---

## Strategic Value

- **Accountability** — proof of ownership for 100% of resources
- **Auditability** — direct link to CloudTrail events for every dollar spent
- **Frictionless FinOps** — eliminates the need to enforce complex tagging policies before achieving cost visibility

---

## Structure

```
cur-explorer/
├── lambda/
│   ├── handler.py            # Point d'entrée — lancer avec python lambda/handler.py
│   ├── cost_processor.py     # Lecture du CUR CSV
│   ├── correlation_engine.py # Logique de jointure CloudTrail + CUR
│   └── requirements.txt      # Aucune dépendance externe (stdlib uniquement)
├── mock-data/
│   ├── cur_mock.csv          # Faux CUR (EC2, S3, RDS, Lambda)
│   └── cloudtrail_mock.json  # Faux events CloudTrail
├── output/
│   └── enriched_costs.json   # Généré automatiquement à l'exécution
└── tests/
    └── test_handler.py
```

---

## Run

```bash
# Lancer le POC
python lambda/handler.py

# Lancer les tests
python tests/test_handler.py
```

---

## Correlation Logic by Service

| Service   | Join key                                 |
|-----------|------------------------------------------|
| EC2       | `instanceId` in `responseElements`       |
| S3        | `bucketName` → ARN `arn:aws:s3:::bucket` |
| RDS       | `dBInstanceArn` in `responseElements`    |
| Lambda    | `functionName` → full ARN                |
