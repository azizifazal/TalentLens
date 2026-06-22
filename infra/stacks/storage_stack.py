from __future__ import annotations

import json

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_opensearchserverless as aoss
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class TalentLensStorageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        account_id = Stack.of(self).account
        region = Stack.of(self).region

        # ---------------- S3 ----------------
        self.resume_bucket = s3.Bucket(
            self,
            "TalentLensResumeBucket",
            bucket_name=f"talentlens-resumes-{account_id}-{region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
            lifecycle_rules=[
                s3.LifecycleRule(
                    enabled=True,
                    expiration=Duration.hours(24),
                    id="delete-after-24-hours",
                )
            ],
        )

        # ---------------- DynamoDB ----------------
        self.table = dynamodb.TableV2(
            self,
            "TalentLensMainTable",
            table_name="talentlens-main",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing=dynamodb.Billing.on_demand(),
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=False,
        )
        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.STRING
            ),
        )

        # ---------------- SQS (FIFO queues for ordered per-session processing) ----------------
        self.parse_dlq = sqs.Queue(
            self,
            "ResumeParseDLQ",
            queue_name="resume-parse-dlq.fifo",
            fifo=True,
            retention_period=Duration.days(14),
        )
        self.parse_queue = sqs.Queue(
            self,
            "ResumeParseQueue",
            queue_name="resume-parse-queue.fifo",
            fifo=True,
            content_based_deduplication=False,
            visibility_timeout=Duration.seconds(150),
            retention_period=Duration.days(2),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3, queue=self.parse_dlq
            ),
        )

        self.rank_dlq = sqs.Queue(
            self,
            "RankJobDLQ",
            queue_name="rank-job-dlq.fifo",
            fifo=True,
            retention_period=Duration.days(14),
        )
        self.rank_queue = sqs.Queue(
            self,
            "RankJobQueue",
            queue_name="rank-job-queue.fifo",
            fifo=True,
            content_based_deduplication=False,
            visibility_timeout=Duration.seconds(950),
            retention_period=Duration.days(2),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=2, queue=self.rank_dlq
            ),
        )

        # ---------------- OpenSearch Serverless ----------------
        collection_name = "talentlens-vectors"

        encryption_policy = aoss.CfnSecurityPolicy(
            self,
            "TalentLensVectorEncryptionPolicy",
            name="talentlens-vector-encryption",
            type="encryption",
            policy=(
                '{"Rules":[{"ResourceType":"collection","Resource":'
                f'["collection/{collection_name}"]}}],"AWSOwnedKey":true}}'
            ),
        )

        network_policy = aoss.CfnSecurityPolicy(
            self,
            "TalentLensVectorNetworkPolicy",
            name="talentlens-vector-network",
            type="network",
            policy=(
                '[{"Rules":[{"ResourceType":"collection","Resource":'
                f'["collection/{collection_name}"]}},'
                '{"ResourceType":"dashboard","Resource":'
                f'["collection/{collection_name}"]}}],"AllowFromPublic":true}}]'
            ),
        )

        self.vector_collection = aoss.CfnCollection(
            self,
            "TalentLensVectorCollection",
            name=collection_name,
            type="VECTORSEARCH",
            description="TalentLens candidate and JD embedding vectors",
        )
        self.vector_collection.add_dependency(encryption_policy)
        self.vector_collection.add_dependency(network_policy)

        # Data access policy is attached in the compute stack once Lambda
        # execution roles exist, via grant_data_access().

        CfnOutput(self, "ResumeBucketName", value=self.resume_bucket.bucket_name)
        CfnOutput(self, "DynamoDBTableName", value=self.table.table_name)
        CfnOutput(self, "ParseQueueUrl", value=self.parse_queue.queue_url)
        CfnOutput(self, "RankQueueUrl", value=self.rank_queue.queue_url)
        CfnOutput(
            self,
            "OpenSearchCollectionEndpoint",
            value=self.vector_collection.attr_collection_endpoint,
        )

    def grant_data_access(self, principal_arns: list[str]) -> None:
        """Attach an OpenSearch Serverless data access policy for the given
        IAM principal ARNs (Lambda execution roles). Called from app.py after
        the compute stack's roles are created, to avoid a circular stack
        dependency between storage and compute."""
        policy = [
            {
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": ["collection/talentlens-vectors"],
                        "Permission": [
                            "aoss:CreateCollectionItems",
                            "aoss:DeleteCollectionItems",
                            "aoss:UpdateCollectionItems",
                            "aoss:DescribeCollectionItems",
                        ],
                    },
                    {
                        "ResourceType": "index",
                        "Resource": ["index/talentlens-vectors/*"],
                        "Permission": [
                            "aoss:CreateIndex",
                            "aoss:DeleteIndex",
                            "aoss:UpdateIndex",
                            "aoss:DescribeIndex",
                            "aoss:ReadDocument",
                            "aoss:WriteDocument",
                        ],
                    },
                ],
                "Principal": list(principal_arns),
            }
        ]
        aoss.CfnAccessPolicy(
            self,
            "TalentLensVectorDataAccessPolicy",
            name="talentlens-vector-data-access",
            type="data",
            policy=json.dumps(policy, separators=(",", ":")),
        )
