# TalentLens AI

AI-powered candidate ranking and shortlisting engine, built on AWS Bedrock, OpenSearch
Serverless, DynamoDB, S3, Cognito, and Lambda.

TalentLens moves beyond keyword filtering: it deeply parses job descriptions (including
behavioral success traits), parses resumes into structured profiles, and computes a 6-dimensional
Behavioral Signal Engine score, runs semantic vector search, matches success traits with an
AI-grounded evidence engine, and produces a ranked, explainable shortlist — all without ever
scoring candidates on company prestige.

Video Link: https://drive.google.com/file/d/1QuAWFMxtbytSGqOYOJYfQ0GPvn-nwbPL/view?usp=sharing
---

## 1. Repository Structure

```
talentlens/
├── backend/                   # FastAPI app + Lambda workers (Python 3.12)
│   ├── core/                  # config, auth (Cognito JWT), exceptions, logging
│   ├── models/                # Pydantic v2 models (candidate, session, ranking)
│   ├── repositories/          # DynamoDB + OpenSearch data access layer
│   ├── services/              # Bedrock client, parser, signals engine, ranker, traits matcher
│   ├── routes/                # FastAPI routers (sessions, resumes, rankings)
│   ├── workers/                # SQS-triggered Lambda handlers (parser, ranker)
│   ├── tests/                 # pytest unit + integration tests (moto-backed)
│   ├── main.py                # FastAPI app + Mangum Lambda handler
│   ├── Dockerfile.api/.parser/.ranker
│   └── requirements.txt
│
├── frontend/                  # React + Vite + TypeScript + Tailwind + Zustand
│   ├── src/
│   │   ├── api/                # Axios client, Cognito auth config, endpoint modules
│   │   ├── components/         # ScoreRing, CandidateCard, WeightPanel, BehavioralPanel...
│   │   ├── pages/               # Login, Dashboard, Session (wizard), Shortlist
│   │   ├── store/                # Zustand stores (auth, session, ranking)
│   │   └── types/                # TypeScript types mirroring backend Pydantic models
│   └── package.json
│
├── infra/                     # AWS CDK (Python)
│   ├── stacks/
│   │   ├── auth_stack.py       # Cognito User Pool + App Client
│   │   ├── storage_stack.py    # S3, DynamoDB, OpenSearch Serverless, SQS
│   │   └── compute_stack.py    # 3 Lambda functions, IAM roles, Function URL
│   ├── tests/                  # CDK assertion-based unit tests
│   └── app.py                  # Stack wiring entry point
│
├── .github/workflows/
│   ├── ci.yml                  # Lint + test backend, frontend, infra on every push/PR
│   └── deploy.yml              # Deploy to AWS on merge to main
│
└── pyproject.toml              # ruff lint/format config
```

---

## 2. Architecture Summary

```
React (Vite/TS) ──HTTPS──▶ Lambda Function URL (FastAPI via Mangum)
                                  │
                  ┌───────────────┼────────────────┐
                  ▼               ▼                ▼
             DynamoDB      S3 (resumes)      SQS (parse-queue,
          (single-table)                       rank-queue, FIFO)
                                                     │
                                        ┌────────────┴────────────┐
                                        ▼                         ▼
                                Parser Lambda              Ranker Lambda
                                (Textract/python-docx        (k-NN search +
                                 + Bedrock Claude +           composite scoring +
                                 Behavioral Signal Engine +   Bedrock explanations)
                                 Titan Embeddings)
                                        │                         │
                                        └───────────┬─────────────┘
                                                     ▼
                                        OpenSearch Serverless
                                          (candidate + JD vectors)
```

All three Lambda functions (`talentlens-api`, `talentlens-parser`, `talentlens-ranker`) are
Docker-image based, deployed via CDK with explicit, predictably-named IAM execution roles
(`talentlens-{api,parser,ranker}-execution-role`) so the OpenSearch Serverless data-access
policy can reference them without creating a circular CloudFormation stack dependency.

---

## 3. Prerequisites

- AWS account with **Bedrock model access enabled** for:
  - `anthropic.claude-3-sonnet-20240229-v1:0`
  - `amazon.titan-embed-text-v2:0`

  (Request access via the Bedrock console → Model access, before deploying.)
- AWS CLI v2, configured with credentials (`aws configure` or SSO)
- Node.js 20+ and npm
- Python 3.12+
- Docker (running locally — required to build the 3 Lambda container images)
- AWS CDK CLI v2: `npm install -g aws-cdk@2`

---

## 4. Local Development

### 4.1 Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values once infra is deployed (see step 5)

# Run tests
cd ..
python -m pytest backend/tests/ -v

# Run the API locally (requires valid AWS credentials in the environment
# for boto3 calls to DynamoDB/S3/OpenSearch/Bedrock/SQS to succeed)
uvicorn backend.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs` once running.

### 4.2 Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in API URL + Cognito IDs after deploying infra
npm run dev                  # http://localhost:5173
```

### 4.3 Infrastructure

```bash
cd infra
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run CDK unit tests
python -m pytest tests/ -v

# Validate templates synthesize without deploying
export CDK_DEFAULT_ACCOUNT=<your-account-id>
export CDK_DEFAULT_REGION=us-east-1
cdk synth
```

---

## 5. Deploying to AWS

### 5.1 One-time bootstrap

```bash
cd infra
export CDK_DEFAULT_ACCOUNT=<your-account-id>
export CDK_DEFAULT_REGION=us-east-1
cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION
```

### 5.2 Deploy stacks in order

The three stacks have a dependency chain: `compute` depends on both `auth` and `storage`.
Deploy in this order (or simply run `cdk deploy --all`, which respects the dependency graph
automatically):

```bash
# Deploy everything in dependency order
cdk deploy --all --require-approval never \
  -c allowed_origins="http://localhost:5173,https://your-frontend-domain.com"
```

Or deploy individually:

```bash
cdk deploy TalentLensAuthStack --require-approval never
cdk deploy TalentLensStorageStack --require-approval never
cdk deploy TalentLensComputeStack --require-approval never \
  -c allowed_origins="https://your-frontend-domain.com"
```

This will:
1. Create the Cognito User Pool + App Client
2. Create the S3 resume bucket (24h lifecycle), DynamoDB table (TTL-enabled), 4 SQS
   queues (2 FIFO queues + 2 DLQs), and the OpenSearch Serverless vector collection
3. Build and push 3 Docker images to ECR (via CDK asset bundling — requires Docker running)
4. Deploy the 3 Lambda functions with their IAM roles, SQS event source mappings, and the
   API Lambda's public Function URL
5. Attach the OpenSearch Serverless data-access policy granting the 3 Lambda execution
   roles read/write access to the vector collection

### 5.3 Capture stack outputs

```bash
aws cloudformation describe-stacks --stack-name TalentLensAuthStack \
  --query "Stacks[0].Outputs" --output table

aws cloudformation describe-stacks --stack-name TalentLensComputeStack \
  --query "Stacks[0].Outputs" --output table
```

You need: `UserPoolId`, `UserPoolClientId`, `ApiFunctionUrl`.

### 5.4 Configure the backend environment

The Lambda functions receive their configuration entirely through CDK-injected environment
variables (see `infra/stacks/compute_stack.py`) — no manual `.env` file is needed in
production. The `.env.example` in `backend/` is for **local development only**.

### 5.5 Configure and deploy the frontend

```bash
cd frontend
cat > .env.production <<EOF
VITE_API_BASE_URL=<ApiFunctionUrl from step 5.3>
VITE_COGNITO_USER_POOL_ID=<UserPoolId from step 5.3>
VITE_COGNITO_CLIENT_ID=<UserPoolClientId from step 5.3>
EOF

npm run build
# dist/ now contains the static production build.
```

Host `dist/` on any static host (S3 + CloudFront recommended for production; the included
`deploy.yml` GitHub Actions workflow automates an S3 + CloudFront deployment). For a quick
manual deployment:

```bash
aws s3 mb s3://your-talentlens-frontend-bucket
aws s3 website s3://your-talentlens-frontend-bucket --index-document index.html
aws s3 sync dist/ s3://your-talentlens-frontend-bucket --delete
```

---

## 6. CI/CD

### `.github/workflows/ci.yml`
Runs on every push and pull request to `main`/`develop`:
- **backend-test** — `pytest` (65 tests: signal engine, ranking models, Bedrock JSON parsing,
  ranker integration with mocks, DynamoDB repository integration via `moto`)
- **backend-lint** — `ruff check` + `ruff format --check`
- **frontend-test** — `tsc -b`, `eslint`, `vitest run` (11 tests), production build
- **infra-test** — CDK unit tests (19 tests, including a regression test for the
  `AWS_REGION` reserved-env-var bug) + `cdk synth`

### `.github/workflows/deploy.yml`
Runs on merge to `main` (or manual dispatch):
1. Re-runs the full CI suite as a gate
2. Deploys all 3 CDK stacks via OIDC-federated AWS credentials
   (`secrets.AWS_DEPLOY_ROLE_ARN` — configure an IAM role trusting GitHub's OIDC provider;
   never store long-lived AWS keys in GitHub secrets)
3. Builds the frontend with the live stack outputs injected as build-time env vars
4. Syncs the build to S3 and invalidates CloudFront

**Required GitHub repository secrets:**
| Secret | Description |
|---|---|
| `AWS_ACCOUNT_ID` | Target AWS account ID |
| `AWS_REGION` | Target region (defaults to `us-east-1`) |
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN for GitHub Actions OIDC federation |
| `FRONTEND_URL` | Production frontend origin (for Lambda CORS allow-list) |
| `FRONTEND_BUCKET_NAME` | S3 bucket serving the frontend |
| `CLOUDFRONT_DISTRIBUTION_ID` | (optional) CloudFront distribution to invalidate |

---

## 7. Testing Summary

| Suite | Count | Command |
|---|---|---|
| Backend unit + integration | 65 | `python -m pytest backend/tests/ -v` |
| Frontend unit | 11 | `cd frontend && npx vitest run` |
| CDK infrastructure | 19 | `cd infra && python -m pytest tests/ -v` |

All 95 tests pass against this codebase as committed. Key coverage includes:
- **Bias-free trajectory scoring**: an explicit unit test asserts that
  `compute_career_trajectory()` has no company-name parameter in its signature, and that
  identical career shapes at a famous vs. unknown company score identically.
- **Behavioral Signal Engine**: all 6 signals (Career Momentum, Learning Velocity, Role
  Consistency, Job Stability, Promotion Frequency, Upskilling Pattern) and the weighted
  composite are independently tested for bounds and directional correctness.
- **Ranking weight validation**: weights must sum to 1.0 in both the Pydantic model and the
  Zustand frontend store.
- **DynamoDB repositories**: tested against `moto`'s in-memory DynamoDB, including
  cross-user authorization checks.
- **CDK regression test**: explicitly asserts `AWS_REGION` is never set as a Lambda
  environment variable (it's reserved by the Lambda runtime and will fail deployment).

---

## 8. Key Design Decisions Worth Knowing

- **Bias prevention is structural, not just procedural.** `compute_career_trajectory()`
  literally cannot accept a company name — there's no parameter for it — enforced by a
  unit test that inspects the function signature.
- **Re-ranking is fast.** Adjusting weights and re-ranking does not re-call Bedrock for
  embeddings or signal computation — only the composite score formula and (if the top-10
  composition changed) explanations are recomputed.
- **SQS FIFO queues** are used (not standard queues) so that resume parsing and ranking
  jobs within the same session process in order, with per-message deduplication IDs
  preventing duplicate processing on retry.
- **DynamoDB Decimal handling**: a dedicated `dynamo_utils.py` module converts Python
  floats to `Decimal` before every write and back to `float`/`int` on every read, since
  `boto3`'s DynamoDB resource API rejects native floats.
- **Cognito JWT verification** uses a locally-cached JWKS (1-hour TTL) rather than calling
  Cognito on every request, keeping the API Lambda's auth overhead minimal.
