#!/usr/bin/env python3
from __future__ import annotations

import os

import aws_cdk as cdk
from stacks.auth_stack import TalentLensAuthStack
from stacks.compute_stack import TalentLensComputeStack
from stacks.storage_stack import TalentLensStorageStack

app = cdk.App()

account = os.environ.get("CDK_DEFAULT_ACCOUNT")
region = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
env = cdk.Environment(account=account, region=region)

allowed_origins = app.node.try_get_context("allowed_origins") or os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173"
)

auth_stack = TalentLensAuthStack(
    app,
    "TalentLensAuthStack",
    env=env,
    description="TalentLens AI — Cognito user pool and app client",
)

storage_stack = TalentLensStorageStack(
    app,
    "TalentLensStorageStack",
    env=env,
    description="TalentLens AI — S3, DynamoDB, OpenSearch Serverless, SQS",
)

compute_stack = TalentLensComputeStack(
    app,
    "TalentLensComputeStack",
    env=env,
    description="TalentLens AI — Lambda functions (API, parser, ranker)",
    user_pool_id=auth_stack.user_pool.user_pool_id,
    user_pool_client_id=auth_stack.user_pool_client.user_pool_client_id,
    resume_bucket=storage_stack.resume_bucket,
    table=storage_stack.table,
    parse_queue=storage_stack.parse_queue,
    rank_queue=storage_stack.rank_queue,
    opensearch_endpoint=storage_stack.vector_collection.attr_collection_endpoint,
    allowed_origins=allowed_origins,
)
compute_stack.add_dependency(auth_stack)
compute_stack.add_dependency(storage_stack)

# Grant the Lambda execution roles data-plane access to the OpenSearch
# Serverless collection. Role ARNs are derived from fixed, predictable role
# names (see TalentLensComputeStack.EXECUTION_ROLE_NAMES) rather than reading
# resolved tokens off the compute stack's resources. This avoids a circular
# CloudFormation dependency: compute already depends on storage for its S3 /
# DynamoDB / SQS resources, so storage cannot also depend on compute's
# resolved outputs. Because the account ID is known at synth time (from
# CDK_DEFAULT_ACCOUNT) and the role names are fixed strings, the ARNs can be
# computed here as plain strings with no actual cross-stack reference.
if account:
    storage_stack.grant_data_access(
        TalentLensComputeStack.execution_role_arns(account)
    )

cdk.Tags.of(app).add("Project", "TalentLensAI")
cdk.Tags.of(app).add("Environment", app.node.try_get_context("environment") or "poc")

app.synth()
