from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from stacks.auth_stack import TalentLensAuthStack
from stacks.compute_stack import TalentLensComputeStack
from stacks.storage_stack import TalentLensStorageStack

TEST_ENV = cdk.Environment(account="123456789012", region="us-east-1")


class _Stacks:
    def __init__(self) -> None:
        self.app = cdk.App()
        self.auth_stack = TalentLensAuthStack(self.app, "TestAuthStack", env=TEST_ENV)
        self.storage_stack = TalentLensStorageStack(
            self.app, "TestStorageStack", env=TEST_ENV
        )
        self.compute_stack = TalentLensComputeStack(
            self.app,
            "TestComputeStack",
            env=TEST_ENV,
            user_pool_id=self.auth_stack.user_pool.user_pool_id,
            user_pool_client_id=self.auth_stack.user_pool_client.user_pool_client_id,
            resume_bucket=self.storage_stack.resume_bucket,
            table=self.storage_stack.table,
            parse_queue=self.storage_stack.parse_queue,
            rank_queue=self.storage_stack.rank_queue,
            opensearch_endpoint="https://test.us-east-1.aoss.amazonaws.com",
            allowed_origins="https://app.talentlens.ai",
        )


@pytest.fixture(scope="module")
def stacks() -> _Stacks:
    return _Stacks()


@pytest.fixture(scope="module")
def auth_stack(stacks: _Stacks) -> TalentLensAuthStack:
    return stacks.auth_stack


@pytest.fixture(scope="module")
def storage_stack(stacks: _Stacks) -> TalentLensStorageStack:
    return stacks.storage_stack


@pytest.fixture(scope="module")
def compute_stack(stacks: _Stacks) -> TalentLensComputeStack:
    return stacks.compute_stack


class TestAuthStack:
    def test_creates_cognito_user_pool(self, auth_stack: TalentLensAuthStack):
        template = Template.from_stack(auth_stack)
        template.resource_count_is("AWS::Cognito::UserPool", 1)

    def test_user_pool_requires_email_signin(self, auth_stack: TalentLensAuthStack):
        template = Template.from_stack(auth_stack)
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "AutoVerifiedAttributes": ["email"],
            },
        )

    def test_password_policy_requires_complexity(self, auth_stack: TalentLensAuthStack):
        template = Template.from_stack(auth_stack)
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "Policies": {
                    "PasswordPolicy": Match.object_like(
                        {
                            "MinimumLength": 8,
                            "RequireLowercase": True,
                            "RequireUppercase": True,
                            "RequireNumbers": True,
                        }
                    )
                }
            },
        )

    def test_creates_app_client_without_secret(self, auth_stack: TalentLensAuthStack):
        template = Template.from_stack(auth_stack)
        template.has_resource_properties(
            "AWS::Cognito::UserPoolClient",
            {"GenerateSecret": False},
        )


class TestStorageStack:
    def test_creates_dynamodb_table_with_ttl(self, storage_stack: TalentLensStorageStack):
        template = Template.from_stack(storage_stack)
        template.has_resource_properties(
            "AWS::DynamoDB::GlobalTable",
            {
                "TimeToLiveSpecification": Match.object_like(
                    {"AttributeName": "expires_at", "Enabled": True}
                )
            },
        )

    def test_s3_bucket_blocks_public_access(self, storage_stack: TalentLensStorageStack):
        template = Template.from_stack(storage_stack)
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                }
            },
        )

    def test_s3_bucket_has_encryption(self, storage_stack: TalentLensStorageStack):
        template = Template.from_stack(storage_stack)
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": Match.object_like(
                    {
                        "ServerSideEncryptionConfiguration": Match.array_with(
                            [
                                Match.object_like(
                                    {
                                        "ServerSideEncryptionByDefault": {
                                            "SSEAlgorithm": "AES256"
                                        }
                                    }
                                )
                            ]
                        )
                    }
                )
            },
        )

    def test_creates_four_sqs_queues_including_dlqs(
        self, storage_stack: TalentLensStorageStack
    ):
        template = Template.from_stack(storage_stack)
        template.resource_count_is("AWS::SQS::Queue", 4)

    def test_parse_queue_is_fifo(self, storage_stack: TalentLensStorageStack):
        template = Template.from_stack(storage_stack)
        template.has_resource_properties(
            "AWS::SQS::Queue",
            {"QueueName": "resume-parse-queue.fifo", "FifoQueue": True},
        )

    def test_creates_opensearch_serverless_collection(
        self, storage_stack: TalentLensStorageStack
    ):
        template = Template.from_stack(storage_stack)
        template.has_resource_properties(
            "AWS::OpenSearchServerless::Collection",
            {"Type": "VECTORSEARCH"},
        )


class TestComputeStack:
    def test_creates_three_lambda_functions(self, compute_stack: TalentLensComputeStack):
        template = Template.from_stack(compute_stack)
        template.resource_count_is("AWS::Lambda::Function", 3)

    def test_api_function_has_function_url(self, compute_stack: TalentLensComputeStack):
        template = Template.from_stack(compute_stack)
        template.resource_count_is("AWS::Lambda::Url", 1)

    def test_api_function_url_has_no_auth(self, compute_stack: TalentLensComputeStack):
        template = Template.from_stack(compute_stack)
        template.has_resource_properties(
            "AWS::Lambda::Url",
            {"AuthType": "NONE"},
        )

    def test_parser_and_ranker_have_sqs_event_sources(
        self, compute_stack: TalentLensComputeStack
    ):
        template = Template.from_stack(compute_stack)
        template.resource_count_is("AWS::Lambda::EventSourceMapping", 2)

    def test_ranker_function_has_long_timeout(self, compute_stack: TalentLensComputeStack):
        template = Template.from_stack(compute_stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"FunctionName": "talentlens-ranker", "Timeout": 900},
        )

    def test_parser_function_reserved_concurrency(
        self, compute_stack: TalentLensComputeStack
    ):
        template = Template.from_stack(compute_stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"FunctionName": "talentlens-parser", "ReservedConcurrentExecutions": 5},
        )

    def test_lambda_env_does_not_set_reserved_aws_region_var(
        self, compute_stack: TalentLensComputeStack
    ):
        """Regression test: AWS_REGION is reserved by the Lambda runtime and
        setting it manually causes a deployment failure."""
        template = Template.from_stack(compute_stack)
        functions = template.find_resources("AWS::Lambda::Function")
        for resource in functions.values():
            env_vars = (
                resource.get("Properties", {})
                .get("Environment", {})
                .get("Variables", {})
            )
            assert "AWS_REGION" not in env_vars

    def test_execution_role_names_are_fixed_and_predictable(self):
        names = TalentLensComputeStack.EXECUTION_ROLE_NAMES
        assert "talentlens-api-execution-role" in names
        assert "talentlens-parser-execution-role" in names
        assert "talentlens-ranker-execution-role" in names

    def test_execution_role_arns_builds_correct_format(self):
        arns = TalentLensComputeStack.execution_role_arns("123456789012")
        assert all(arn.startswith("arn:aws:iam::123456789012:role/") for arn in arns)
        assert len(arns) == 3
