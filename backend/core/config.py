from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"
    aws_account_id: str = ""

    # Cognito
    cognito_user_pool_id: str
    cognito_client_id: str

    # DynamoDB
    dynamodb_table_name: str = "talentlens-main"

    # S3
    s3_bucket_name: str

    # OpenSearch Serverless
    opensearch_endpoint: str  # e.g. https://xxxx.us-east-1.aoss.amazonaws.com

    # SQS
    sqs_parse_queue_url: str
    sqs_rank_queue_url: str

    # Bedrock
    bedrock_model_id: str = "amazon.nova-pro-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_max_tokens: int = 4096

    # App
    allowed_origins: str = "http://localhost:5173"
    session_ttl_hours: int = 24
    max_candidates_per_session: int = 500
    max_file_size_mb: int = 10

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def jwks_url(self) -> str:
        return (
            f"https://cognito-idp.{self.aws_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}/.well-known/jwks.json"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
