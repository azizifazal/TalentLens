# Implementation Plan: TalentLens Deployment

## Overview

This plan takes TalentLens from its current codebase state to a fully deployed, verified
AWS application. Tasks are grouped into six deployment phases plus an alternative
one-shot path via `deploy.sh`. All commands are written for **bash** (Git Bash or WSL on
Windows). Run each task in the project root (`talentlens/`) unless a specific directory
is noted.

The `deploy.sh` script automates phases 3–6 end-to-end (see Phase 7). Phases 1–2 are
manual pre-flight steps that must be confirmed by the operator before any automation
runs. Phase 2 (test suites) is the quality gate — do not deploy if any suite is red.

---

## Tasks

- [ ] 1. Phase 1 — Pre-deployment Verification
  - [ ] 1.1 Verify AWS CLI is configured and targeting the correct account/region
    - Run the following command and confirm the output shows account `022784798053` and
      region `us-east-1`:
      ```bash
      aws sts get-caller-identity
      aws configure get region
      ```
    - **Success**: `Account` field equals `022784798053`; region equals `us-east-1`.
    - **If it fails**: Run `aws configure` (access key / secret key flow) or
      `aws configure sso` for SSO-based credentials. Ensure the profile is active.
    - _Requirements: 1.1, 1.4_

  - [ ] 1.2 Verify Docker Desktop is running
    - Run:
      ```bash
      docker info
      ```
    - **Success**: Output shows server info without errors.
    - **If it fails**: Start Docker Desktop and wait for the whale icon to stop
      animating, then retry.
    - _Requirements: 1.3_

  - [ ] 1.3 Verify required CLI tools are installed with correct versions
    - Run:
      ```bash
      node --version    # must be 20+
      python3 --version # must be 3.12+
      cdk --version     # must be 2.x
      aws --version
      npm --version
      ```
    - **Success**: All commands resolve without "not found" errors; Node ≥ 20, Python ≥ 3.12, CDK ≥ 2.x.
    - **If Node is wrong version**: Use `nvm install 20 && nvm use 20`.
    - **If CDK is missing**: `npm install -g aws-cdk@2`
    - **If Python version is wrong**: Install Python 3.12 from https://python.org and
      ensure `python3` on PATH resolves to it.
    - _Requirements: 1.1, 1.2_

  - [ ] 1.4 Verify Bedrock model access is enabled
    - In the AWS console, navigate to **Amazon Bedrock → Model access** in `us-east-1`.
    - Confirm both models show "Access granted":
      - `amazon.nova-pro-v1:0` (Amazon Nova Pro)
      - `amazon.titan-embed-text-v2:0` (Titan Embeddings V2)
    - **If access is not granted**: Click "Manage model access", select both models,
      and submit. Access is usually granted within a few minutes.
    - **Note**: There is no CLI command to request model access; this must be done
      through the console. The deployment will succeed without this step, but Lambda
      functions will return errors at runtime when Bedrock is invoked.
    - _Requirements: 8.1_

- [ ] 2. Phase 2 — Run Test Suites (Quality Gate)
  - [ ] 2.1 Run backend test suite
    - From the project root, run:
      ```bash
      python -m pytest backend/tests/ -v
      ```
      Or using make:
      ```bash
      make backend-test
      ```
    - **Success**: All 65 tests pass (`65 passed`). No errors or failures.
    - **If it fails**: Fix failing tests before proceeding. Do not deploy with a red
      backend suite.
    - _Requirements: 10.1, 10.2_

  - [ ]* 2.2 Write property tests for pre-flight and CDK synthesis (Phase 2 optional)
    - Implement property-based tests in `infra/tests/` using Hypothesis:
      - **Property 1: Pre-flight nonzero on missing tool** — generate subsets of
        `{aws, cdk, docker, node, npm, python3}` and assert script exits nonzero with
        the missing tool name in the error message.
        - `# Feature: talentlens-deployment, Property 1`
        - Test file: `infra/tests/test_preflight.py`
        - _Requirements: 1.2_
      - **Property 2: FRONTEND_URL default when unset** — generate environments with
        and without `FRONTEND_URL` exported; assert resolved value equals
        `http://localhost:5173` when unset.
        - `# Feature: talentlens-deployment, Property 2`
        - Test file: `infra/tests/test_preflight.py`
        - _Requirements: 1.7_
      - **Property 5: Lambda execution roles have predictable names** — for any valid
        CDK app config, synthesise the template and assert all three role names
        (`talentlens-{api,parser,ranker}-execution-role`) are present.
        - `# Feature: talentlens-deployment, Property 5`
        - Test file: `infra/tests/test_compute_stack.py`
        - _Requirements: 3.7_
      - **Property 11: All three Lambda functions receive correct Bedrock model IDs**
        — synthesise template and assert `BEDROCK_MODEL_ID=amazon.nova-pro-v1:0`,
        `BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0`, and no
        `AWS_REGION` in any Lambda's environment variables.
        - `# Feature: talentlens-deployment, Property 11`
        - Test file: `infra/tests/test_compute_stack.py`
        - _Requirements: 8.2_
      - **Property 10: AllowedOrigins in template** — generate valid origin URL strings
        and assert each appears in the Lambda Function URL CORS `AllowedOrigins`.
        - `# Feature: talentlens-deployment, Property 10`
        - Test file: `infra/tests/test_compute_stack.py`
        - _Requirements: 7.5_
      - **Property 12: No long-lived keys in deploy.yml** — read `deploy.yml` content
        and assert `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` do not appear as
        secrets or env vars in any deployment job step.
        - `# Feature: talentlens-deployment, Property 12`
        - Test file: `infra/tests/test_cicd.py`
        - _Requirements: 10.3_
    - _Requirements: 1.2, 1.7, 3.7, 7.5, 8.2, 10.3_

  - [ ] 2.3 Run frontend test suite
    - From the project root, run:
      ```bash
      cd frontend && npx vitest run
      ```
      Or using make:
      ```bash
      make frontend-test
      ```
    - **Success**: All 11 tests pass. No TypeScript type errors.
    - **If it fails**: Run `npm install` inside `frontend/` first to ensure dependencies
      are installed, then retry.
    - _Requirements: 10.1, 10.2_

  - [ ] 2.4 Run CDK infrastructure tests
    - From the project root, run:
      ```bash
      cd infra && python -m pytest tests/ -v
      ```
      Or using make:
      ```bash
      make infra-test
      ```
    - **Success**: All 19 CDK assertion tests pass.
    - **If it fails**: Run `pip install -r infra/requirements.txt` inside a venv first,
      then retry.
    - _Requirements: 10.1, 10.2_

  - [ ] 2.5 Checkpoint — all test suites green
    - Confirm outputs from tasks 2.1, 2.3, and 2.4 show zero failures before
      proceeding to deployment.
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Phase 3 — CDK Infrastructure Bootstrap
  - [ ] 3.1 Set up Python venv for infra and install CDK dependencies
    - Run from the project root:
      ```bash
      cd infra
      python3 -m venv .venv
      source .venv/bin/activate       # Windows Git Bash: source .venv/Scripts/activate
      pip install --upgrade pip
      pip install -r requirements.txt
      ```
    - **Success**: `pip install` completes without errors. `cdk synth` should work.
    - **If it fails**: Confirm `python3 --version` is 3.12+ and try again.
    - _Requirements: 2.5_

  - [ ] 3.2 Run CDK bootstrap for account 022784798053 / us-east-1
    - With the infra venv active and from inside the `infra/` directory, run:
      ```bash
      export CDK_DEFAULT_ACCOUNT=022784798053
      export CDK_DEFAULT_REGION=us-east-1
      cdk bootstrap aws://022784798053/us-east-1
      ```
    - **Success**: Output ends with `✅  Environment aws://022784798053/us-east-1 bootstrapped.`
      (Re-running on an already-bootstrapped account is safe — it will just confirm no
      changes needed.)
    - **If it fails**: Verify AWS credentials (`aws sts get-caller-identity`) and that
      the venv is active. Check CloudFormation in the console for the `CDKToolkit` stack.
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 3.3 Write property and unit tests for bootstrap phase
    - Implement in `infra/tests/test_bootstrap.py`:
      - **Property 4: CDK env vars set before bootstrap** — for any (account, region)
        pair, assert `CDK_DEFAULT_ACCOUNT` and `CDK_DEFAULT_REGION` are set before
        `cdk bootstrap` is called.
        - `# Feature: talentlens-deployment, Property 4`
        - _Requirements: 2.4_
      - Unit test: verify `.venv` creation and `pip install -r requirements.txt`
        executes before bootstrap (mock subprocess).
    - _Requirements: 2.4, 2.5_

- [ ] 4. Phase 4 — Deploy CDK Stacks
  - [ ] 4.1 Deploy TalentLensAuthStack
    - From inside `infra/` with the venv active:
      ```bash
      cdk deploy TalentLensAuthStack \
        --require-approval never \
        -c "environment=poc"
      ```
    - **Success**: CloudFormation stack reaches `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
      Outputs include `UserPoolId` and `UserPoolClientId`.
    - **If it fails**: Check the CloudFormation console for the stack events. Look for
      IAM permission errors (the deploying role needs `cognito-idp:*` and
      `cloudformation:*`). Fix the error and re-run — CDK deploy is idempotent.
    - _Requirements: 3.1, 3.2_

  - [ ] 4.2 Deploy TalentLensStorageStack
    - From inside `infra/` with the venv active:
      ```bash
      cdk deploy TalentLensStorageStack \
        --require-approval never \
        -c "environment=poc"
      ```
    - **Success**: CloudFormation stack reaches `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
      Resources created: S3 bucket, DynamoDB table, 4 SQS FIFO queues, OpenSearch
      Serverless collection.
    - **Note**: OpenSearch Serverless collection provisioning can take 5–10 minutes on
      first deploy. This is normal.
    - **If it fails**: Check CloudFormation events. OpenSearch requires
      `aoss:*` IAM permissions on the deploying role.
    - _Requirements: 3.1, 3.2_

  - [ ] 4.3 Deploy TalentLensComputeStack (builds and pushes Docker images to ECR)
    - From inside `infra/` with the venv active:
      ```bash
      cdk deploy TalentLensComputeStack \
        --require-approval never \
        -c "allowed_origins=http://localhost:5173" \
        -c "environment=poc"
      ```
    - **Success**: CloudFormation stack reaches `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
      Three Lambda functions created. `ApiFunctionUrl` output is present.
    - **Note**: First deploy builds three Docker images and pushes them to ECR. This
      can take 10–20 minutes total. Subsequent deploys are faster if the image layers
      are cached.
    - **If Docker build fails**: Ensure Docker Desktop is running and you have enough
      disk space (>5 GB free). Check `Dockerfile.api`, `Dockerfile.parser`,
      `Dockerfile.ranker` for syntax errors.
    - **If ECR push fails**: Confirm your IAM role has `ecr:*` permissions and run
      `aws ecr get-login-password | docker login --username AWS --password-stdin
      022784798053.dkr.ecr.us-east-1.amazonaws.com` to re-authenticate.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 8.2_

  - [ ]* 4.4 Write property tests for ComputeStack CDK synthesis
    - Implement in `infra/tests/test_compute_stack.py`:
      - **Property 6: Missing stack output causes nonzero exit** — generate subsets of
        `{UserPoolId, UserPoolClientId, ApiFunctionUrl}` and assert the output-capture
        logic exits nonzero with the missing key name in the error.
        - `# Feature: talentlens-deployment, Property 6`
        - Test file: `infra/tests/test_output_capture.py`
        - _Requirements: 4.4_
      - **Property 9: CORS re-deploy conditional on default origin** — assert re-deploy
        is triggered if and only if `FRONTEND_URL == http://localhost:5173`.
        - `# Feature: talentlens-deployment, Property 9`
        - Test file: `infra/tests/test_cors_logic.py`
        - _Requirements: 7.1, 7.3_
    - _Requirements: 4.4, 7.1, 7.3_

  - [ ] 4.5 Checkpoint — all three stacks deployed and green
    - Run:
      ```bash
      aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --region us-east-1 \
        --query "StackSummaries[?contains(StackName,'TalentLens')].{Name:StackName,Status:StackStatus}" \
        --output table
      ```
    - **Success**: All three stacks (`TalentLensAuthStack`, `TalentLensStorageStack`,
      `TalentLensComputeStack`) appear with `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Phase 5 — Frontend Build and Deploy
  - [ ] 5.1 Capture CloudFormation outputs (UserPoolId, UserPoolClientId, ApiFunctionUrl)
    - Run:
      ```bash
      USER_POOL_ID=$(aws cloudformation describe-stacks \
        --stack-name TalentLensAuthStack \
        --region us-east-1 \
        --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
        --output text)

      USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks \
        --stack-name TalentLensAuthStack \
        --region us-east-1 \
        --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
        --output text)

      API_URL=$(aws cloudformation describe-stacks \
        --stack-name TalentLensComputeStack \
        --region us-east-1 \
        --query "Stacks[0].Outputs[?OutputKey=='ApiFunctionUrl'].OutputValue" \
        --output text)

      echo "UserPoolId:       $USER_POOL_ID"
      echo "UserPoolClientId: $USER_POOL_CLIENT_ID"
      echo "API URL:          $API_URL"
      ```
    - **Success**: All three variables are non-empty.
    - **If any variable is empty**: The corresponding stack did not deploy correctly.
      Check CloudFormation outputs in the console for that stack.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ] 5.2 Build frontend with live stack outputs injected
    - Write the production env file then build:
      ```bash
      cd frontend

      cat > .env.production <<EOF
      VITE_API_BASE_URL=${API_URL}
      VITE_COGNITO_USER_POOL_ID=${USER_POOL_ID}
      VITE_COGNITO_CLIENT_ID=${USER_POOL_CLIENT_ID}
      EOF

      npm install
      npm run build
      ```
    - **Success**: `frontend/dist/` directory is created containing `index.html` and
      hashed asset files.
    - **If build fails**: Check `frontend/` for TypeScript errors: `npx tsc --noEmit`.
      Fix any type errors, then re-run `npm run build`.
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 5.3 Write property test for .env.production content
    - Implement in `infra/tests/test_frontend_build.py`:
      - **Property 7: .env.production contains all three stack outputs** — generate
        (pool-id, client-id, api-url) triples; write the file; assert all three
        `VITE_*` keys are present with the correct (un-transposed) values.
        - `# Feature: talentlens-deployment, Property 7`
        - _Requirements: 5.2_
    - _Requirements: 5.2_

  - [ ] 5.4 Deploy frontend to S3 static website bucket
    - Run (substituting the captured `AWS_ACCOUNT_ID`):
      ```bash
      FRONTEND_BUCKET="talentlens-frontend-022784798053"
      AWS_REGION="us-east-1"

      # Create bucket (idempotent — ignore error if already exists)
      aws s3api create-bucket \
        --bucket "$FRONTEND_BUCKET" \
        --region "$AWS_REGION" 2>/dev/null || true

      # Enable static website hosting (SPA: error document = index.html)
      aws s3 website "s3://${FRONTEND_BUCKET}" \
        --index-document index.html \
        --error-document index.html

      # Disable public access block
      aws s3api put-public-access-block \
        --bucket "$FRONTEND_BUCKET" \
        --public-access-block-configuration \
          "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

      # Apply public read bucket policy
      aws s3api put-bucket-policy \
        --bucket "$FRONTEND_BUCKET" \
        --policy '{
          "Version": "2012-10-17",
          "Statement": [{
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::'"$FRONTEND_BUCKET"'/*"
          }]
        }'

      # Sync dist/ to S3, removing stale files
      cd frontend
      aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" \
        --delete \
        --region "$AWS_REGION"

      echo "Frontend URL: http://${FRONTEND_BUCKET}.s3-website-${AWS_REGION}.amazonaws.com"
      ```
    - **Success**: `aws s3 sync` exits 0 and prints the number of files uploaded.
      The website URL is accessible over HTTP.
    - **If bucket creation fails with `BucketAlreadyOwnedByYou`**: That's fine — the
      `|| true` suppresses it. Re-running the full block is safe.
    - **If `put-public-access-block` fails**: Check IAM permissions include `s3:PutBucketPublicAccessBlock`.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 11.3, 11.5_

  - [ ]* 5.5 Write property test for S3 sync idempotency
    - Implement in `infra/tests/test_s3_sync.py`:
      - **Property 13: S3 sync idempotency with --delete** — mock `aws s3 sync` and
        generate arbitrary `dist/` file sets; assert running the sync twice produces the
        same final object set as running it once (no stale objects).
        - `# Feature: talentlens-deployment, Property 13`
        - _Requirements: 11.5_
    - _Requirements: 11.5_

- [ ] 6. Phase 6 — CORS Wiring and Post-Deployment Verification
  - [ ] 6.1 Update Lambda CORS with the real frontend URL
    - Derive the frontend URL from the bucket name, then re-deploy only ComputeStack:
      ```bash
      FRONTEND_BUCKET="talentlens-frontend-022784798053"
      AWS_REGION="us-east-1"
      FRONTEND_WEBSITE_URL="http://${FRONTEND_BUCKET}.s3-website-${AWS_REGION}.amazonaws.com"

      cd infra
      source .venv/bin/activate   # ensure venv is active
      cdk deploy TalentLensComputeStack \
        --require-approval never \
        -c "allowed_origins=${FRONTEND_WEBSITE_URL}" \
        -c "environment=poc"
      ```
    - **Success**: Stack reaches `UPDATE_COMPLETE`. Lambda Function URL CORS now lists
      the S3 website URL as an allowed origin.
    - **If deploy fails**: This is non-fatal. Note the exact `FRONTEND_WEBSITE_URL`
      value and re-run the command manually once the issue is resolved. The application
      is already deployed; only browser cross-origin requests will be affected.
    - **Skip this task if** `FRONTEND_URL` was already set to the production URL before
      deploying (i.e., you passed it explicitly in tasks 4.3 / 7.1).
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 6.2 Smoke test — verify API health endpoint returns HTTP 200
    - Run (replace `<API_URL>` with the captured value from task 5.1):
      ```bash
      curl -s -o /dev/null -w "%{http_code}" "${API_URL}health"
      ```
    - **Success**: Output is `200`.
    - **If output is 503 / 5xx (cold start timeout)**: Wait 30 seconds and retry. The
      Lambda may be initialising its Docker container on first invocation.
    - **If output is 403**: Check Lambda Function URL auth mode is `NONE` in the
      CloudFormation console.
    - **If `curl` is not available**: Use PowerShell:
      `(Invoke-WebRequest "${API_URL}health").StatusCode`
    - _Requirements: 9.3_

  - [ ] 6.3 Smoke test — verify frontend is accessible over HTTP
    - Run (replace with the S3 website URL from task 5.4):
      ```bash
      FRONTEND_URL="http://talentlens-frontend-022784798053.s3-website-us-east-1.amazonaws.com"
      curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL"
      ```
    - **Success**: Output is `200`.
    - Verify SPA routing works for unknown paths:
      ```bash
      curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}/some-unknown-route"
      ```
      **Success**: Output is `200` (S3 routes all 404s to `index.html`).
    - **If output is 403**: Confirm the bucket policy and public access block were set
      correctly in task 5.4. Re-run the `put-public-access-block` and
      `put-bucket-policy` commands.
    - **If output is 404**: Confirm `aws s3 sync` completed and `index.html` is present:
      `aws s3 ls s3://talentlens-frontend-022784798053/`
    - _Requirements: 9.4, 9.5_

  - [ ] 6.4 Checkpoint — deployment complete, print summary
    - Print the full deployment summary:
      ```bash
      echo "====== TalentLens AI — Deployment Summary ======"
      echo "Frontend URL:       http://talentlens-frontend-022784798053.s3-website-us-east-1.amazonaws.com"
      echo "API URL:            ${API_URL}"
      echo "User Pool ID:       ${USER_POOL_ID}"
      echo "User Pool Client:   ${USER_POOL_CLIENT_ID}"
      echo "AWS Account:        022784798053"
      echo "Region:             us-east-1"
      ```
    - **Next steps**:
      1. Open the frontend URL in a browser and sign up via Cognito.
      2. (Optional) Set up CloudFront in front of S3 for HTTPS, then re-run:
         `FRONTEND_URL=https://your-cf-domain.cloudfront.net ./deploy.sh`
      3. (Optional) Configure GitHub Actions secrets for automated CI/CD (see task 7.1
         and `deploy.yml`).
    - Ensure all tests pass, ask the user if questions arise.
    - _Requirements: 9.1, 9.2_

- [ ] 7. Alternative — Run Everything via deploy.sh (phases 3–6 combined)
  - [ ] 7.1 Run full deployment via deploy.sh
    - This single command executes all steps from CDK bootstrap through CORS update.
      Run it from the project root after completing phases 1 and 2:
      ```bash
      chmod +x deploy.sh
      ./deploy.sh
      ```
      To set a known production frontend URL (e.g. a pre-created CloudFront domain)
      and skip the CORS re-deploy step:
      ```bash
      FRONTEND_URL=https://your-cf-domain.cloudfront.net ./deploy.sh
      ```
    - **What the script does** (phases 3–6 automated):
      1. Pre-flight checks (tools, Docker, credentials)
      2. CDK bootstrap (idempotent)
      3. `cdk deploy --all` (Auth → Storage → Compute)
      4. Captures CloudFormation outputs
      5. Writes `frontend/.env.production` and runs `npm run build`
      6. Creates S3 bucket, enables website hosting, runs `aws s3 sync`
      7. Re-deploys ComputeStack with real CORS origin (if FRONTEND_URL was default)
      8. Prints deployment summary
    - **Success**: Script exits 0 and the summary block is printed.
    - **If the script fails mid-way**: It uses `set -euo pipefail`, so it exits at the
      first error with a descriptive `[ERROR]` message. Fix the reported issue and
      re-run — all steps are idempotent.
    - **If CORS update step warns but does not fail**: The application is deployed. Note
      the warning message and re-run with the correct `FRONTEND_URL`.
    - _Requirements: 1.1–1.7, 2.1–2.5, 3.1–3.8, 4.1–4.5, 5.1–5.5, 6.1–6.6, 7.1–7.5,
      9.1–9.5, 11.1–11.5_

---

## Notes

- Tasks marked with `*` are optional property/unit test sub-tasks that can be skipped
  for a faster first deployment. Run them to build the property-test safety net.
- Phases 1 and 2 are manual / local — they must be completed before running any
  CDK commands or `deploy.sh`.
- Phase 7 (deploy.sh) covers the same ground as phases 3–6 and can be used instead.
  Phases 3–6 are provided as granular steps for operators who need to debug or re-run
  individual stages.
- **Re-run safety**: All deployment steps are idempotent. Re-running after a partial
  failure is always safe.
- **First deploy time**: Expect 15–25 minutes total (Docker image builds + OpenSearch
  Serverless provisioning). Subsequent deploys are much faster.
- Each task references specific requirements for traceability.
- Property tests validate universal correctness properties across many generated inputs.
- Checkpoints ensure incremental validation between phases.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4"] },
    { "id": 1, "tasks": ["2.1", "2.3", "2.4"] },
    { "id": 2, "tasks": ["2.2", "2.5"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["3.2"] },
    { "id": 5, "tasks": ["3.3", "4.1", "4.2"] },
    { "id": 6, "tasks": ["4.3"] },
    { "id": 7, "tasks": ["4.4", "4.5"] },
    { "id": 8, "tasks": ["5.1"] },
    { "id": 9, "tasks": ["5.2"] },
    { "id": 10, "tasks": ["5.3", "5.4"] },
    { "id": 11, "tasks": ["5.5", "6.1"] },
    { "id": 12, "tasks": ["6.2", "6.3"] },
    { "id": 13, "tasks": ["6.4"] },
    { "id": 14, "tasks": ["7.1"] }
  ]
}
```
