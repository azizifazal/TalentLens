# Requirements Document

## Introduction

This document captures the deployment requirements for TalentLens AI — a full-stack AWS
application consisting of a FastAPI backend deployed across three Docker-based Lambda
functions (api, parser, ranker), a React/Vite/TypeScript frontend, and an AWS CDK
infrastructure layer (AuthStack, StorageStack, ComputeStack). The deployment process spans
pre-flight verification, CDK bootstrap and stack deployment, frontend build and S3
hosting, CORS wiring, CloudFormation output capture, and post-deployment smoke testing.
The target environment is AWS account `022784798053`, region `us-east-1`.

The `deploy.sh` script at the project root automates the end-to-end flow. These
requirements formalise what that script — and any equivalent CI/CD pipeline — must
guarantee.

---

## Glossary

- **Deploy_Script**: The `deploy.sh` bash script at the project root that orchestrates
  the full deployment flow.
- **CDK_CLI**: The AWS Cloud Development Kit CLI v2 (`cdk`) used to synthesise and deploy
  CloudFormation stacks.
- **AuthStack**: The `TalentLensAuthStack` CloudFormation stack that provisions the
  Cognito User Pool and App Client.
- **StorageStack**: The `TalentLensStorageStack` CloudFormation stack that provisions S3,
  DynamoDB, OpenSearch Serverless, and SQS FIFO queues.
- **ComputeStack**: The `TalentLensComputeStack` CloudFormation stack that provisions the
  three Docker-image Lambda functions and their IAM roles.
- **Lambda_API**: The `talentlens-api` Lambda function (FastAPI via Mangum, 512 MB,
  30 s timeout) that handles HTTP requests through a public Function URL.
- **Lambda_Parser**: The `talentlens-parser` Lambda function (1024 MB, 120 s timeout)
  that consumes messages from the SQS FIFO parse queue.
- **Lambda_Ranker**: The `talentlens-ranker` Lambda function (1024 MB, 900 s timeout)
  that consumes messages from the SQS FIFO rank queue.
- **ECR**: Amazon Elastic Container Registry, where CDK pushes the Docker image assets
  for the three Lambda functions during deployment.
- **Frontend_Build**: The production static bundle produced by `npm run build` (Vite)
  in the `frontend/` directory, output to `frontend/dist/`.
- **Frontend_Bucket**: The S3 bucket named `talentlens-frontend-{AWS_ACCOUNT_ID}` that
  hosts the frontend static website.
- **Stack_Outputs**: The CloudFormation output values (`UserPoolId`,
  `UserPoolClientId`, `ApiFunctionUrl`) used to wire the frontend and verify
  deployment success.
- **CORS_Config**: The `AllowedOrigins` list on the Lambda_API Function URL that
  controls which origins the browser accepts responses from.
- **Bedrock_Model**: The Amazon Nova Pro foundation model
  (`amazon.nova-pro-v1:0`) used for text generation.
- **Bedrock_Embedding_Model**: The Amazon Titan Embeddings v2 model
  (`amazon.titan-embed-text-v2:0`) used for vector generation.
- **Health_Endpoint**: The `GET /health` HTTP endpoint exposed by Lambda_API that
  returns a 200 OK when the function is reachable.
- **OpenSearch_Collection**: The `talentlens-vectors` OpenSearch Serverless collection
  used for semantic vector search.
- **Preflight_Check**: A verification step that confirms all required tools and
  credentials are available before any deployment action is taken.

---

## Requirements

### Requirement 1: Pre-Deployment Prerequisites Verification

**User Story:** As a developer or CI pipeline, I want all prerequisites verified before
any deployment action runs, so that failures are caught early with clear error messages
rather than mid-way through a long deployment.

#### Acceptance Criteria

1. WHEN the Deploy_Script starts, THE Deploy_Script SHALL verify that the following CLI
   tools are available on the PATH: `aws`, `cdk`, `docker`, `node`, `npm`, `python3`.
2. WHEN any required CLI tool is not found on the PATH, THE Deploy_Script SHALL exit with
   a non-zero status code and print an error message identifying the missing tool and its
   installation source.
3. WHEN the Docker daemon is not running, THE Deploy_Script SHALL exit with a non-zero
   status code and print an error message instructing the operator to start Docker.
4. WHEN the active AWS credentials cannot be verified via `aws sts get-caller-identity`,
   THE Deploy_Script SHALL exit with a non-zero status code and print an error message
   directing the operator to run `aws configure` or configure SSO.
5. WHEN the active AWS account ID differs from the configured target account ID, THE
   Deploy_Script SHALL print a warning and proceed using the active account ID.
6. WHEN all Preflight_Checks pass, THE Deploy_Script SHALL print a confirmation message
   showing the resolved AWS account ID and region before proceeding.
7. WHEN the `FRONTEND_URL` environment variable is not set, THE Deploy_Script SHALL
   default to `http://localhost:5173` as the initial allowed CORS origin.

---

### Requirement 2: CDK Infrastructure Bootstrap

**User Story:** As a developer, I want CDK bootstrapped against the target account and
region before any stacks are deployed, so that CDK asset staging resources exist and
re-running bootstrap on an already-bootstrapped account is safe.

#### Acceptance Criteria

1. WHEN the Deploy_Script runs the bootstrap step, THE CDK_CLI SHALL execute
   `cdk bootstrap aws://{account}/{region}` targeting the resolved AWS account ID and
   `us-east-1`.
2. WHEN the CDK toolkit stack already exists in the target account, THE CDK_CLI SHALL
   complete the bootstrap step without error (idempotent behaviour).
3. WHEN CDK bootstrap fails, THE Deploy_Script SHALL exit with a non-zero status code and
   print an error message before any stack deployment is attempted.
4. WHEN bootstrap is invoked, THE Deploy_Script SHALL set `CDK_DEFAULT_ACCOUNT` and
   `CDK_DEFAULT_REGION` environment variables to the resolved values before calling
   `cdk bootstrap`.
5. WHEN bootstrap is invoked, THE Deploy_Script SHALL activate a Python virtual
   environment in `infra/.venv` and install the CDK Python dependencies from
   `infra/requirements.txt` before calling `cdk bootstrap`.

---

### Requirement 3: CDK Stack Deployment

**User Story:** As a developer, I want all three CDK stacks deployed in dependency order
(Auth → Storage → Compute), so that each stack's outputs are available to dependent
stacks and Docker images are built and pushed to ECR automatically.

#### Acceptance Criteria

1. WHEN the Deploy_Script runs the stack deployment step, THE CDK_CLI SHALL deploy all
   three stacks (AuthStack, StorageStack, ComputeStack) using `cdk deploy --all`.
2. THE CDK_CLI SHALL deploy the stacks in dependency order: AuthStack first, StorageStack
   second, ComputeStack third, respecting the `add_dependency` declarations in `app.py`.
3. WHEN deploying the ComputeStack, THE CDK_CLI SHALL build and push Docker images for
   Lambda_API, Lambda_Parser, and Lambda_Ranker to ECR using the Dockerfiles
   `Dockerfile.api`, `Dockerfile.parser`, and `Dockerfile.ranker` in the `backend/`
   directory.
4. WHEN deploying the ComputeStack, THE CDK_CLI SHALL pass the `allowed_origins` context
   variable containing the current `FRONTEND_URL` value.
5. WHEN any stack deployment fails, THE Deploy_Script SHALL exit with a non-zero status
   code and print an error message.
6. WHEN all stacks are deployed successfully, THE CDK_CLI SHALL output the CloudFormation
   stack outputs to stdout.
7. THE ComputeStack SHALL create Lambda execution roles with the predictable names
   `talentlens-api-execution-role`, `talentlens-parser-execution-role`, and
   `talentlens-ranker-execution-role` so that the OpenSearch Serverless data-access
   policy can reference them without a circular stack dependency.
8. WHEN deploying in a fresh account for the first time, THE Deploy_Script SHALL inform
   the operator that the initial deployment may take 10–20 minutes due to Docker image
   builds and OpenSearch Serverless provisioning.

---

### Requirement 4: CloudFormation Output Capture and Environment Wiring

**User Story:** As a developer, I want the Stack_Outputs captured and validated
immediately after CDK deployment, so that subsequent steps (frontend build, CORS update)
have the correct values and missing outputs are caught before the frontend is built.

#### Acceptance Criteria

1. WHEN all stacks are deployed, THE Deploy_Script SHALL retrieve `UserPoolId` from the
   `TalentLensAuthStack` outputs using the AWS CLI.
2. WHEN all stacks are deployed, THE Deploy_Script SHALL retrieve `UserPoolClientId` from
   the `TalentLensAuthStack` outputs using the AWS CLI.
3. WHEN all stacks are deployed, THE Deploy_Script SHALL retrieve `ApiFunctionUrl` from
   the `TalentLensComputeStack` outputs using the AWS CLI.
4. IF any of the three required Stack_Outputs are empty or missing, THEN THE
   Deploy_Script SHALL exit with a non-zero status code and print an error message
   identifying which output is missing.
5. WHEN all three Stack_Outputs are captured, THE Deploy_Script SHALL print each value
   to stdout before proceeding to the frontend build step.

---

### Requirement 5: Frontend Production Build

**User Story:** As a developer, I want the frontend built with live backend environment
variables injected at build time, so that the production bundle communicates with the
deployed API and Cognito pool rather than localhost placeholders.

#### Acceptance Criteria

1. WHEN the frontend build step runs, THE Deploy_Script SHALL install frontend
   dependencies by running `npm install` in the `frontend/` directory.
2. WHEN the frontend build step runs, THE Deploy_Script SHALL write a `.env.production`
   file in the `frontend/` directory containing `VITE_API_BASE_URL`,
   `VITE_COGNITO_USER_POOL_ID`, and `VITE_COGNITO_CLIENT_ID`, populated from the
   captured Stack_Outputs.
3. WHEN the `.env.production` file is written, THE Deploy_Script SHALL run
   `npm run build` in the `frontend/` directory to produce the Frontend_Build in
   `frontend/dist/`.
4. IF the frontend build fails, THEN THE Deploy_Script SHALL exit with a non-zero status
   code and print an error message.
5. WHEN the frontend build completes successfully, THE Deploy_Script SHALL confirm
   completion before proceeding to the S3 deployment step.

---

### Requirement 6: Frontend S3 Deployment

**User Story:** As a developer, I want the Frontend_Build synced to the Frontend_Bucket
with static website hosting enabled, so that users can access the application over HTTP
without any additional hosting infrastructure.

#### Acceptance Criteria

1. WHEN the S3 deployment step runs, THE Deploy_Script SHALL create the Frontend_Bucket
   named `talentlens-frontend-{AWS_ACCOUNT_ID}` in `us-east-1` if it does not already
   exist.
2. WHEN the Frontend_Bucket exists, THE Deploy_Script SHALL not fail due to the bucket
   already existing (idempotent create behaviour).
3. WHEN the Frontend_Bucket is configured, THE Deploy_Script SHALL enable S3 static
   website hosting with `index.html` as both the index and error document, routing all
   404 responses to `index.html` to support client-side routing (SPA behaviour).
4. WHEN enabling static website hosting, THE Deploy_Script SHALL disable the S3 public
   access block on the Frontend_Bucket and apply a bucket policy granting
   `s3:GetObject` to all principals (`"Principal": "*"`).
5. WHEN syncing the Frontend_Build, THE Deploy_Script SHALL run `aws s3 sync dist/
   s3://{Frontend_Bucket} --delete` to upload all files and remove stale files.
6. WHEN the S3 sync completes, THE Deploy_Script SHALL derive the Frontend website URL
   as `http://{Frontend_Bucket}.s3-website-{region}.amazonaws.com` and store it for
   use in the CORS update step.

---

### Requirement 7: CORS Configuration Update

**User Story:** As a developer, I want the Lambda_API Function URL CORS configuration
updated with the real frontend URL after the frontend is deployed to S3, so that the
browser does not block API responses due to a mismatched origin.

#### Acceptance Criteria

1. WHEN the initial `FRONTEND_URL` value is the default `http://localhost:5173`, THE
   Deploy_Script SHALL re-deploy the ComputeStack passing the actual Frontend website
   URL as the `allowed_origins` context variable.
2. WHEN the CORS update re-deploy runs, THE CDK_CLI SHALL update the Lambda_API Function
   URL CORS configuration with the correct `AllowedOrigins` list.
3. WHEN the `FRONTEND_URL` environment variable was explicitly set to a non-default value
   before running the Deploy_Script, THE Deploy_Script SHALL skip the CORS update
   re-deploy step (the correct origin was already passed during the initial `cdk deploy
   --all`).
4. IF the CORS update re-deploy fails, THEN THE Deploy_Script SHALL print a warning
   message explaining how to re-run with the correct `FRONTEND_URL` and continue without
   exiting with an error.
5. WHEN the CORS update completes, THE Lambda_API Function URL SHALL include the
   Frontend website URL in its `AllowedOrigins` list, permitting cross-origin requests
   from the browser.

---

### Requirement 8: Bedrock Model Access Verification

**User Story:** As a developer or CI pipeline, I want confirmation that the required
Bedrock foundation models are accessible in the target account before deploying backend
infrastructure that depends on them, so that runtime failures from missing model access
are prevented.

#### Acceptance Criteria

1. THE Deploy_Script documentation SHALL state that operators must enable access for
   `amazon.nova-pro-v1:0` and `amazon.titan-embed-text-v2:0` in the Bedrock console
   before running the deployment.
2. WHEN the ComputeStack Lambda environment variables are configured, THE ComputeStack
   SHALL inject `BEDROCK_MODEL_ID=amazon.nova-pro-v1:0` and
   `BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0` into all three Lambda
   functions (Lambda_API, Lambda_Parser, Lambda_Ranker).
3. WHEN Lambda_Parser or Lambda_Ranker invoke a Bedrock model and the model is not
   accessible, THE Lambda function SHALL return an error response with a descriptive
   message rather than crashing silently.

---

### Requirement 9: Post-Deployment Smoke Testing

**User Story:** As a developer or CI pipeline, I want automated smoke tests run after
deployment to confirm the application is reachable and functional, so that broken
deployments are detected immediately without manual browser testing.

#### Acceptance Criteria

1. WHEN deployment completes, THE Deploy_Script SHALL print the Frontend website URL,
   API URL, User Pool ID, User Pool Client ID, AWS account, and region to stdout as a
   deployment summary.
2. WHEN the deployment summary is printed, THE Deploy_Script SHALL exit with status code
   0 to indicate successful completion.
3. WHEN a smoke test is run against the Health_Endpoint (`GET {ApiFunctionUrl}/health`),
   THE Lambda_API SHALL respond with HTTP 200 within 10 seconds of a cold-start
   invocation.
4. WHEN the Frontend website URL is accessed over HTTP, THE Frontend_Bucket SHALL return
   the `index.html` file with HTTP 200.
5. WHEN a request is made to a non-existent frontend route (e.g., `/some-unknown-path`),
   THE Frontend_Bucket SHALL return `index.html` with HTTP 200 to support client-side
   routing.

---

### Requirement 10: CI/CD Pipeline Deployment

**User Story:** As a team, I want the deployment automated via GitHub Actions on merge
to `main`, so that every merged change is deployed to AWS without manual intervention
and without storing long-lived AWS credentials in GitHub.

#### Acceptance Criteria

1. WHEN code is merged to the `main` branch, THE GitHub_Actions_Workflow SHALL
   re-execute the full CI test suite (backend pytest, frontend vitest, CDK assertion
   tests) as a gate before deploying.
2. IF any CI test fails, THEN THE GitHub_Actions_Workflow SHALL halt the deployment and
   report the failure without deploying any infrastructure changes.
3. WHEN the CI gate passes, THE GitHub_Actions_Workflow SHALL authenticate to AWS using
   OIDC federation via the `AWS_DEPLOY_ROLE_ARN` repository secret, without requiring
   long-lived AWS access keys stored in GitHub secrets.
4. WHEN the GitHub_Actions_Workflow deploys, THE GitHub_Actions_Workflow SHALL pass the
   `FRONTEND_URL` repository secret as the `allowed_origins` context variable so that
   CORS is configured correctly for the production domain on the first deploy.
5. WHEN frontend assets are deployed, THE GitHub_Actions_Workflow SHALL sync the
   Frontend_Build to the `FRONTEND_BUCKET_NAME` repository secret value using
   `aws s3 sync`.
6. WHERE the `CLOUDFRONT_DISTRIBUTION_ID` repository secret is set, THE
   GitHub_Actions_Workflow SHALL create a CloudFront invalidation for `/*` after
   syncing the frontend to S3.
7. WHEN any deployment step in the GitHub_Actions_Workflow fails, THE
   GitHub_Actions_Workflow SHALL exit with a non-zero status code, leaving the
   previously deployed version running.

---

### Requirement 11: Deployment Idempotency and Re-Run Safety

**User Story:** As a developer, I want to be able to re-run the deployment script
against an already-deployed environment without causing errors or unintended resource
changes, so that CORS updates and hotfixes can be applied safely.

#### Acceptance Criteria

1. WHEN the Deploy_Script is re-run against a fully deployed environment, THE
   Deploy_Script SHALL complete successfully without manual cleanup of existing
   resources.
2. WHEN `cdk deploy --all` is re-run with no infrastructure changes, THE CDK_CLI SHALL
   detect that no changes are required and skip stack updates without error.
3. WHEN the Frontend_Bucket already exists, THE Deploy_Script SHALL not fail during the
   bucket creation step.
4. WHEN the `FRONTEND_URL` environment variable is set to a CloudFront or custom domain
   before re-running, THE Deploy_Script SHALL pass that value as `allowed_origins` to
   `cdk deploy TalentLensComputeStack`, updating the Lambda_API CORS configuration to
   reflect the new origin.
5. WHEN the S3 sync step is re-run, THE Deploy_Script SHALL use `--delete` to remove
   files from the Frontend_Bucket that are no longer present in the local
   `frontend/dist/` build output.
