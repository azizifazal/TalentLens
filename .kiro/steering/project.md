# TalentLens AI — Project Steering

## What This Project Is

TalentLens is a full-stack AI-powered candidate ranking and shortlisting engine deployed on AWS. It parses job descriptions and resumes, computes a 6-dimension Behavioral Signal Engine score, runs semantic vector search, and produces a ranked explainable shortlist — without using company prestige as a signal.

## Live Deployment

- **Frontend**: https://d2ky0iqvbzxus.cloudfront.net (CloudFront + private S3)
- **API**: https://izjdvv4mshj2b334e67szsidga0ljndx.lambda-url.us-east-1.on.aws/
- **AWS Account**: 022784798053
- **Region**: us-east-1
- **CloudFront Distribution**: E1XZFFKONJ3KTG
- **Frontend S3 Bucket**: talentlens-frontend-022784798053
- **OpenSearch Endpoint**: https://mdrvcocyj2izo28qek81.us-east-1.aoss.amazonaws.com
- **Cognito User Pool**: us-east-1_Sq0dthN4S
- **Cognito Client ID**: gap4a5ko95q1a1vcu48efak51

## Stack Overview

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite 5 + TypeScript + Tailwind CSS + Zustand |
| Backend | FastAPI + Mangum (Lambda handler) + Pydantic v2 |
| AI | Amazon Nova Pro (amazon.nova-pro-v1:0) + Titan Embeddings v2 |
| Vector DB | OpenSearch Serverless (VECTORSEARCH collection) |
| Database | DynamoDB single-table |
| Storage | S3 (resumes, 24h lifecycle) |
| Queue | SQS FIFO (parse-queue, rank-queue + 2 DLQs) |
| Auth | AWS Cognito JWT with locally-cached JWKS (1h TTL) |
| Infra | AWS CDK v2 (Python) — 3 stacks |
| CI/CD | GitHub Actions (ci.yml + deploy.yml) |

## Repository Layout

```
talentlens/
├── backend/                  # FastAPI + Lambda workers (Python 3.12)
│   ├── core/                 # config, auth, exceptions, logging
│   ├── models/               # Pydantic v2 models
│   ├── repositories/         # DynamoDB + OpenSearch data access
│   ├── services/             # Bedrock, parser, signals, ranker, traits matcher
│   ├── routes/               # FastAPI routers (sessions, resumes, rankings)
│   ├── workers/              # SQS-triggered Lambda handlers
│   ├── tests/                # pytest unit + integration (moto-backed)
│   └── main.py               # FastAPI app + Mangum(app, lifespan="off", api_gateway_base_path=None)
├── frontend/                 # React + Vite + TypeScript
│   └── src/
│       ├── api/              # Axios client + Cognito auth + endpoint modules
│       ├── components/       # UI components
│       ├── pages/            # Login, Dashboard, Session, Shortlist
│       ├── store/            # Zustand stores (auth, session, ranking)
│       └── types/            # TypeScript types mirroring Pydantic models
├── infra/                    # AWS CDK (Python)
│   └── stacks/               # auth_stack, storage_stack, compute_stack
├── deploy.ps1                # Windows PowerShell one-shot deployment script
├── deploy.sh                 # Bash one-shot deployment script
└── .kiro/steering/           # Kiro steering files
```

## CDK Stacks

| Stack | Resources |
|---|---|
| TalentLensAuthStack | Cognito User Pool + App Client |
| TalentLensStorageStack | S3 resume bucket, DynamoDB, OpenSearch Serverless, SQS FIFO x4 |
| TalentLensComputeStack | 3 Docker Lambda functions + IAM roles + Function URL + CORS |

Stack dependency: Auth → Storage → Compute.

## Lambda Functions

| Function | Memory | Timeout | Trigger |
|---|---|---|---|
| talentlens-api | 512 MB | 30s | HTTP (Function URL) |
| talentlens-parser | 1024 MB | 120s | SQS (resume-parse-queue.fifo) |
| talentlens-ranker | 1024 MB | 900s | SQS (rank-job-queue.fifo) |

All 3 are Docker-image based (AMD64), built from `backend/Dockerfile.{api,parser,ranker}` with build context = `backend/`.

## IAM Execution Roles (fixed names)

- `talentlens-api-execution-role`
- `talentlens-parser-execution-role`
- `talentlens-ranker-execution-role`

Fixed names allow the OpenSearch Serverless data-access policy to reference them without circular CDK stack dependencies.
