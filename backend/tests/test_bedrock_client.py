from __future__ import annotations

import json

import pytest

from backend.core.exceptions import BedrockError
from backend.services.bedrock import BedrockClient


@pytest.fixture
def bedrock_client(mocker) -> BedrockClient:
    mocker.patch("boto3.client")
    return BedrockClient()


class TestCleanJsonString:
    def test_strips_markdown_json_fence(self, bedrock_client):
        raw = '```json\n{"key": "value"}\n```'
        cleaned = bedrock_client._clean_json_string(raw)
        assert cleaned == '{"key": "value"}'

    def test_strips_plain_markdown_fence(self, bedrock_client):
        raw = '```\n{"key": "value"}\n```'
        cleaned = bedrock_client._clean_json_string(raw)
        assert cleaned == '{"key": "value"}'

    def test_passes_through_clean_json(self, bedrock_client):
        raw = '{"key": "value"}'
        cleaned = bedrock_client._clean_json_string(raw)
        assert cleaned == '{"key": "value"}'

    def test_strips_surrounding_whitespace(self, bedrock_client):
        raw = '  \n  {"key": "value"}  \n  '
        cleaned = bedrock_client._clean_json_string(raw)
        assert cleaned == '{"key": "value"}'


class TestParseJsonResponse:
    def test_parses_valid_json_object(self, bedrock_client):
        raw = '{"required_skills": ["Python", "AWS"]}'
        result = bedrock_client._parse_json_response(raw)
        assert result["required_skills"] == ["Python", "AWS"]

    def test_parses_json_wrapped_in_markdown(self, bedrock_client):
        raw = '```json\n{"role_level": "senior"}\n```'
        result = bedrock_client._parse_json_response(raw)
        assert result["role_level"] == "senior"

    def test_extracts_json_from_surrounding_text(self, bedrock_client):
        raw = 'Here is the analysis:\n{"score": 85}\nThat is my assessment.'
        result = bedrock_client._parse_json_response(raw)
        assert result["score"] == 85

    def test_raises_bedrock_error_on_unparseable_text(self, bedrock_client):
        raw = "This is not JSON at all and has no braces"
        with pytest.raises(BedrockError):
            bedrock_client._parse_json_response(raw)

    def test_raises_bedrock_error_when_result_is_list_not_dict(self, bedrock_client):
        raw = '["item1", "item2"]'
        with pytest.raises(BedrockError):
            bedrock_client._parse_json_response(raw)
