# TalentLens Deployment Guide

## Current Live Environment

| Resource | Value |
|---|---|
| AWS Account | 022784798053 |
| Region | us-east-1 |
| Frontend URL | https://d2ky0iqvbzxus.cloudfront.net |
| API URL | https://izjdvv4mshj2b334e67szsidga0ljndx.lambda-url.us-east-1.on.aws/ |
| CloudFront ID | E1XZFFKONJ3KTG |
| Frontend S3 | talentlens-frontend-022784798053 |
| OpenSearch | mdrvcocyj2izo28qek81.us-east-1.aoss.amazonaws.com |
| Cognito Pool | us-east-1_Sq0dthN4S |
| Cognito Client | gap4a5ko95q1a1vcu48efak51 |

## Deploy Everything (Windows)

```powershell
cd "C:\Users\Fazal Azizi\Desktop\talentlens-ai-fullstack\talentlens"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\deploy.ps1
```

## Deploy Backend Only (after code changes)

```powershell
cd "C:\Users\Fazal Azizi\Desktop\talentlens-ai-fullstack\talentlens\infra"
.\.venv\Scripts\Activate.ps1
$env:CDK_DEFAULT_ACCOUNT="022784798053"; $env:CDK_DEFAULT_REGION="us-east-1"
cdk deploy TalentLensComputeStack --require-approval never -c "allowed_origins=https://d2ky0iqvbzxus.cloudfront.net" -c "environment=poc"
```

## Deploy Frontend Only (after UI changes)

```powershell
cd "C:\Users\Fazal Azizi\Desktop\talentlens-ai-fullstack\talentlens\frontend"
npm run build
aws s3 sync dist/ s3://talentlens-frontend-022784798053 --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id E1XZFFKONJ3KTG --paths "/*"
```

## Check Lambda Logs

```powershell
# API Lambda
aws logs tail /aws/lambda/talentlens-api --since 10m --region us-east-1 --format short

# Parser Lambda
aws logs tail /aws/lambda/talentlens-parser --since 10m --region us-east-1 --format short

# Ranker Lambda
aws logs tail /aws/lambda/talentlens-ranker --since 10m --region us-east-1 --format short
```

## Delete OpenSearch Indices (when schema changes)

Run from project root with backend venv or system Python that has opensearch-py installed:

```powershell
python -c "
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

session = boto3.Session(region_name='us-east-1')
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, 'us-east-1', 'aoss', session_token=creds.token)
client = OpenSearch(
    hosts=[{'host': 'mdrvcocyj2izo28qek81.us-east-1.aoss.amazonaws.com', 'port': 443}],
    http_auth=auth, use_ssl=True, verify_certs=True,
    connection_class=RequestsHttpConnection
)
for idx in ['candidate-profiles', 'job-descriptions']:
    try:
        print(f'Deleted {idx}:', client.indices.delete(index=idx))
    except Exception as e:
        print(f'Error: {e}')
"
```

## Update Lambda CORS

```powershell
cd "C:\Users\Fazal Azizi\Desktop\talentlens-ai-fullstack\talentlens"
'{"AllowOrigins":["https://d2ky0iqvbzxus.cloudfront.net"],"AllowMethods":["GET","POST","DELETE"],"AllowHeaders":["authorization","content-type"],"MaxAge":3600}' | Out-File -FilePath "cors.json" -Encoding utf8NoBOM
aws lambda update-function-url-config --function-name talentlens-api --region us-east-1 --cors file://cors.json
```

## Verify Credentials

```powershell
aws sts get-caller-identity
# Expected: Account = 022784798053, User = Faz-0406
```

## Cost Monitoring

```powershell
aws ce get-cost-and-usage --time-period Start=2026-06-01,End=2026-06-30 --granularity MONTHLY --metrics "UnblendedCost" --group-by Type=DIMENSION,Key=SERVICE --region us-east-1 --query "ResultsByTime[0].Groups[?Metrics.UnblendedCost.Amount>'0'].{Service:Keys[0],Cost:Metrics.UnblendedCost.Amount}" --output table
```

## Known AOSS Constraints

- Document IDs not supported in index operations (auto-generated only)
- `refresh=True` not supported
- `index.knn.space_type` not supported in settings
- `engine: nmslib` not supported — use `faiss`
- Eventual consistency — retry reads with backoff after writes
