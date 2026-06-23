# Revelio - Identity-Based AWS Cost Attribution Platform

## Overview

Revelio is a serverless FinOps platform that attributes AWS cloud costs to the actual resource creators by correlating billing records with AWS audit logs.

Traditional cloud cost allocation relies heavily on tagging strategies. In practice, tag coverage is often incomplete due to deployment automation, ephemeral workloads, and inconsistent engineering practices.

Revelio eliminates this limitation by performing identity-based cost attribution using AWS Cost and Usage Reports (CUR), CloudTrail audit events, and AWS Config metadata.

The platform enables organizations to drastically reduce unattributed cloud spend and improve showback and chargeback processes.

---

## Business Problem

Large AWS environments frequently suffer from poor tagging hygiene.

As a result:

* Finance teams cannot determine who owns cloud spend.
* Chargeback and showback processes become unreliable.
* Engineering teams are not accountable for their consumption.
* Significant portions of cloud costs remain unattributed.

Revelio addresses this challenge by attributing every possible cost line item to the IAM identity that created the underlying resource.

---

## Key Features

* Identity-based cost attribution without mandatory tagging.
* Correlation of AWS CUR and CloudTrail audit logs.
* AWS Config fallback for historical resource ownership.
* Attribution confidence scoring (HIGH, MEDIUM, LOW).
* Showback and chargeback-ready datasets.
* FinOps KPI generation.
* Athena analytical views for cost exploration.
* Streamlit dashboard for cost visualization.
* Incremental processing using Glue job bookmarks.
* Cost-controlled Athena Workgroup with query guardrails.

---

## Architecture

Daily processing pipeline:

1. AWS CUR delivers billing data to Amazon S3.
2. CloudTrail exports resource creation events.
3. AWS Config exports infrastructure metadata.
4. Glue Crawlers update the Glue Data Catalog.
5. A Glue ETL job correlates billing and audit datasets.
6. Enriched cost records are written back to S3 in Parquet format.
7. Athena provides serverless SQL analytics.
8. Dashboards and FinOps reports consume the enriched dataset.

The entire architecture is fully serverless and Infrastructure-as-Code driven.

---

## AWS Services

* Amazon S3
* AWS Cost & Usage Reports (CUR)
* AWS CloudTrail
* AWS Config
* AWS Glue
* AWS Glue Data Catalog
* Amazon Athena
* AWS KMS
* Amazon CloudWatch
* Amazon SNS
* AWS IAM
* Amazon DynamoDB

---

## Cost Attribution Strategy

Unlike traditional FinOps solutions relying solely on tags, Revelio performs attribution using:

```text
AWS CUR Resource ID
            +
CloudTrail Resource Creation Events
            ↓
IAM Identity Attribution
```

Confidence levels:

* HIGH → Direct CloudTrail match.
* MEDIUM → AWS Config metadata fallback.
* LOW → No ownership evidence found.

Tags remain optional supplementary metadata rather than mandatory prerequisites.

---

## FinOps Capabilities

| Capability                     | Status  |
| ------------------------------ | ------- |
| Cost Allocation                | ✓       |
| Showback                       | ✓       |
| Chargeback                     | ✓       |
| Attribution Confidence Scoring | ✓       |
| Tag Gap Analysis               | ✓       |
| Cost Governance                | ✓       |
| Shared Cost Allocation         | Planned |
| Forecasting                    | Planned |
| Unit Economics                 | Planned |

---

## Estimated Business Impact

The following figures are conservative estimates based on FinOps Foundation practices and enterprise cloud environments.

* Improve cloud cost attribution coverage from an estimated 40-60% to more than 90%.
* Reduce unattributed cloud spend by an estimated 50-80%.
* Reduce showback and chargeback report preparation time from days to minutes.
* Increase engineering accountability by exposing cost ownership at the IAM identity level.
* Accelerate FinOps maturity by reducing dependency on tagging compliance.

---

## Example Scenario

For an organization spending $100,000/month on AWS:

* Typical unattributed spend before implementation: $30,000-$50,000/month.
* Potential attributable spend after deployment: more than $90,000/month.
* Estimated visibility improvement: +40 percentage points or more.

---

## DevOps & Security

* Terraform Infrastructure as Code.
* Modular architecture.
* GitHub Actions CI/CD pipeline.
* OIDC federation with AWS (no long-lived credentials).
* Automated security scanning with Checkov.
* Least-privilege IAM model.
* KMS encryption across all storage and processing layers.
* TLS-only S3 access.
* Remote Terraform state locking.

---

## Technical Highlights

* Large-scale serverless data lake architecture.
* PySpark ETL on AWS Glue.
* Athena serverless analytics.
* Partition projection optimization.
* Incremental processing using Glue bookmarks.
* FinOps-oriented data modeling.
* Multi-source correlation engine.

---

## Future Improvements

* Shared infrastructure cost allocation.
* Unit economics (cost per customer, product or transaction).
* Cost anomaly detection.
* Multi-account AWS Organizations support.
* FinOps scorecards and maturity dashboards.
