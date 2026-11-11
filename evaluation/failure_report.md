# Failure Mode Analysis

- **Total alert files evaluated:** 20
- **Passed:** 17
- **Failed:** 3

## Failure categories

| Category | Count | Affected alert types |
|---|---|---|
| No Terraform plan generated | 3 | pod_pending, replica_mismatch, service_unavaible |
| Terraform validation failed | 3 | pod_pending, replica_mismatch, service_unavaible |
| Other API error | 1 | pod_pending |

## Failures by alert file

| Alert file | Failure count |
|---|---|
| pod_pending.json | 3 |
| replica_mismatch.json | 2 |
| service_unavaible.json | 2 |
