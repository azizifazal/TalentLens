from __future__ import annotations

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_events
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class TalentLensComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        user_pool_id: str,
        user_pool_client_id: str,
        resume_bucket: s3.Bucket,
        table: dynamodb.TableV2,
        parse_queue: sqs.Queue,
        rank_queue: sqs.Queue,
        opensearch_endpoint: str,
        allowed_origins: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        common_env = {
            "COGNITO_USER_POOL_ID": user_pool_id,
            "COGNITO_CLIENT_ID": user_pool_client_id,
            "DYNAMODB_TABLE_NAME": table.table_name,
            "S3_BUCKET_NAME": resume_bucket.bucket_name,
            "OPENSEARCH_ENDPOINT": opensearch_endpoint,
            "SQS_PARSE_QUEUE_URL": parse_queue.queue_url,
            "SQS_RANK_QUEUE_URL": rank_queue.queue_url,
            "BEDROCK_MODEL_ID": "amazon.nova-pro-v1:0",
            "BEDROCK_EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
            "BEDROCK_MAX_TOKENS": "4096",
            "ALLOWED_ORIGINS": allowed_origins,
            "SESSION_TTL_HOURS": "24",
            "MAX_CANDIDATES_PER_SESSION": "500",
            "MAX_FILE_SIZE_MB": "10",
            "LOG_LEVEL": "INFO",
        }

        # Explicit, predictably-named execution roles. Using fixed role names
        # (rather than CDK's auto-generated ones) lets app.py compute the
        # resulting role ARNs as plain strings at synth time, so the
        # OpenSearch Serverless data-access policy can be attached to the
        # storage stack without creating a circular cross-stack dependency
        # between compute (which needs storage's resources) and storage
        # (which would otherwise need compute's role ARNs as CFN exports).
        api_role = iam.Role(
            self,
            "TalentLensApiRole",
            role_name="talentlens-api-execution-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        parser_role = iam.Role(
            self,
            "TalentLensParserRole",
            role_name="talentlens-parser-execution-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        ranker_role = iam.Role(
            self,
            "TalentLensRankerRole",
            role_name="talentlens-ranker-execution-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # ---------------- API Lambda ----------------
        self.api_function = lambda_.DockerImageFunction(
            self,
            "TalentLensApiFunction",
            function_name="talentlens-api",
            code=lambda_.DockerImageCode.from_image_asset(
                directory="../backend",
                file="Dockerfile.api",
                platform=ecr_assets.Platform.LINUX_AMD64,
            ),
            memory_size=512,
            timeout=Duration.seconds(30),
            environment=common_env,
            architecture=lambda_.Architecture.X86_64,
            role=api_role,
        )

        self.api_function_url = self.api_function.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=allowed_origins.split(","),
                allowed_methods=[
                    lambda_.HttpMethod.GET,
                    lambda_.HttpMethod.POST,
                    lambda_.HttpMethod.DELETE,
                ],
                allowed_headers=["Authorization", "Content-Type"],
                max_age=Duration.hours(1),
            ),
        )

        # ---------------- Parser Lambda ----------------
        self.parser_function = lambda_.DockerImageFunction(
            self,
            "TalentLensParserFunction",
            function_name="talentlens-parser",
            code=lambda_.DockerImageCode.from_image_asset(
                directory="../backend",
                file="Dockerfile.parser",
                platform=ecr_assets.Platform.LINUX_AMD64,
            ),
            memory_size=1024,
            timeout=Duration.seconds(120),
            environment=common_env,
            architecture=lambda_.Architecture.X86_64,
            reserved_concurrent_executions=5,
            role=parser_role,
        )
        self.parser_function.add_event_source(
            lambda_events.SqsEventSource(
                parse_queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
        )

        # ---------------- Ranker Lambda ----------------
        self.ranker_function = lambda_.DockerImageFunction(
            self,
            "TalentLensRankerFunction",
            function_name="talentlens-ranker",
            code=lambda_.DockerImageCode.from_image_asset(
                directory="../backend",
                file="Dockerfile.ranker",
                platform=ecr_assets.Platform.LINUX_AMD64,
            ),
            memory_size=1024,
            timeout=Duration.seconds(900),
            environment=common_env,
            architecture=lambda_.Architecture.X86_64,
            reserved_concurrent_executions=3,
            role=ranker_role,
        )
        self.ranker_function.add_event_source(
            lambda_events.SqsEventSource(
                rank_queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
        )

        # ---------------- IAM Permissions (least privilege) ----------------
        all_functions = [self.api_function, self.parser_function, self.ranker_function]

        for fn in all_functions:
            table.grant_read_write_data(fn)
            resume_bucket.grant_read_write(fn)

        parse_queue.grant_send_messages(self.api_function)
        parse_queue.grant_consume_messages(self.parser_function)
        rank_queue.grant_send_messages(self.api_function)
        rank_queue.grant_consume_messages(self.ranker_function)

        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/"
                "amazon.nova-pro-v1:0",
                f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/"
                "amazon.titan-embed-text-v2:0",
            ],
        )
        textract_policy = iam.PolicyStatement(
            actions=[
                "textract:DetectDocumentText",
                "textract:AnalyzeDocument",
            ],
            resources=["*"],
        )
        opensearch_policy = iam.PolicyStatement(
            actions=["aoss:APIAccessAll"],
            resources=[
                f"arn:aws:aoss:{Stack.of(self).region}:{Stack.of(self).account}:"
                "collection/*"
            ],
        )

        for fn in [self.api_function, self.parser_function, self.ranker_function]:
            fn.add_to_role_policy(bedrock_policy)
            fn.add_to_role_policy(opensearch_policy)
        self.parser_function.add_to_role_policy(textract_policy)

        CfnOutput(self, "ApiFunctionUrl", value=self.api_function_url.url)
        CfnOutput(self, "ApiFunctionName", value=self.api_function.function_name)
        CfnOutput(self, "ParserFunctionName", value=self.parser_function.function_name)
        CfnOutput(self, "RankerFunctionName", value=self.ranker_function.function_name)

    # Fixed, predictable role names — must match the role_name= values above.
    EXECUTION_ROLE_NAMES: list[str] = [
        "talentlens-api-execution-role",
        "talentlens-parser-execution-role",
        "talentlens-ranker-execution-role",
    ]

    @staticmethod
    def execution_role_arns(account_id: str) -> list[str]:
        """Build IAM role ARNs as plain strings from the fixed role names.

        Deliberately does NOT read .role_arn off the Lambda constructs: doing
        so would create a CloudFormation cross-stack export/import from
        compute -> storage, which combined with storage's own dependency on
        compute (for grant_data_access) would form a circular dependency.
        Since the role names are fixed at synth time, the ARNs are fully
        known without needing an actual resource reference.
        """
        return [
            f"arn:aws:iam::{account_id}:role/{name}"
            for name in TalentLensComputeStack.EXECUTION_ROLE_NAMES
        ]
