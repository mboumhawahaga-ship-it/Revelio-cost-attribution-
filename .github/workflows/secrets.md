# Required GitHub Secrets

Configure these in: Settings → Secrets and variables → Actions

| Secret                | Description                                              |
|-----------------------|----------------------------------------------------------|
| `AWS_ROLE_ARN`        | IAM role ARN for OIDC auth (fmt/validate steps)          |
| `AWS_ROLE_ARN_PLAN`   | IAM role ARN with read-only permissions (plan step)      |
| `AWS_ROLE_ARN_APPLY`  | IAM role ARN with deploy permissions (apply step)        |
| `TF_STATE_BUCKET`     | S3 bucket name for Terraform remote state                |
| `TF_LOCK_TABLE`       | DynamoDB table name for state locking                    |

## IAM Role Trust Policy (OIDC)

Each role must trust GitHub's OIDC provider. Minimal trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/CUR-explorer:*"
        }
      }
    }
  ]
}
```

## Recommended IAM permissions per role

- **PLAN role**: `ReadOnlyAccess` + `s3:GetObject` on state bucket
- **APPLY role**: least-privilege scoped to resources Terraform manages
  (never `AdministratorAccess`)
