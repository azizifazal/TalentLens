from __future__ import annotations

import json
import re
from typing import Any

import boto3
import structlog
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.core.config import get_settings
from backend.core.exceptions import BedrockError

logger = structlog.get_logger(__name__)


class BedrockClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._region = settings.aws_region
        self._model_id = settings.bedrock_model_id
        self._embed_model_id = settings.bedrock_embedding_model_id
        self._max_tokens = settings.bedrock_max_tokens
        self._client = boto3.client("bedrock-runtime", region_name=self._region)

    @retry(
        retry=retry_if_exception_type((ClientError, BedrockError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def invoke_claude(
        self,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> str:
        """Invoke the configured Amazon Nova model via the Converse API.

        The method is intentionally named ``invoke_claude`` so that all
        existing callers (routes, services) require no changes.  Internally
        it uses the Bedrock Converse API which is compatible with Amazon Nova
        models (nova-pro, nova-lite, nova-micro) as well as Claude 3+.
        """
        messages = [{"role": "user", "content": [{"text": user_prompt}]}]

        kwargs: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens or self._max_tokens},
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        try:
            response = self._client.converse(**kwargs)
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            if not content:
                raise BedrockError("Empty response from Nova model")
            text = content[0].get("text", "")
            if not text:
                raise BedrockError("No text in Nova model response")
            return text
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code in ("ThrottlingException", "ServiceUnavailableException"):
                logger.warning("bedrock_throttled", model=self._model_id)
                raise
            logger.error("bedrock_client_error", error=str(exc), code=error_code)
            raise BedrockError(str(exc))

    def invoke_claude_json(
        self,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        raw = self.invoke_claude(user_prompt, system_prompt, max_tokens)
        return self._parse_json_response(raw)

    def invoke_claude_json_list(
        self,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> list[Any]:
        raw = self.invoke_claude(user_prompt, system_prompt, max_tokens)
        cleaned = self._clean_json_string(raw)
        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                for v in result.values():
                    if isinstance(v, list):
                        return v
            return []
        except json.JSONDecodeError as exc:
            logger.error("json_list_parse_failed", error=str(exc), raw=raw[:500])
            return []

    @retry(
        retry=retry_if_exception_type((ClientError, BedrockError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def get_embedding(self, text: str) -> list[float]:
        truncated = text[:8000]
        body = {"inputText": truncated, "dimensions": 1024, "normalize": True}
        try:
            response = self._client.invoke_model(
                modelId=self._embed_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
            response_body = json.loads(response["body"].read())
            embedding: list[float] = response_body.get("embedding", [])
            if not embedding:
                raise BedrockError("Empty embedding response")
            return embedding
        except ClientError as exc:
            logger.error("embedding_error", error=str(exc))
            raise BedrockError(str(exc))

    @staticmethod
    def _clean_json_string(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        return text.strip()

    def _parse_json_response(self, raw: str) -> dict[str, Any]:
        cleaned = self._clean_json_string(raw)
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
            raise BedrockError(f"Expected dict, got {type(result).__name__}")
        except json.JSONDecodeError as exc:
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            logger.error("json_parse_failed", error=str(exc), raw=cleaned[:500])
            raise BedrockError(f"Invalid JSON in Nova model response: {exc}")
