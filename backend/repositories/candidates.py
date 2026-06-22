from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import boto3
import structlog
from boto3.dynamodb.conditions import Key

from backend.core.config import get_settings
from backend.core.exceptions import CandidateNotFoundError
from backend.models.candidate import (
    Candidate,
    CandidateListItem,
    CandidateProfile,
    CandidateSignals,
    ParseStatus,
)
from backend.repositories.dynamo_utils import decimals_to_float, floats_to_decimal

logger = structlog.get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ttl_timestamp(hours: int = 24) -> int:
    return int(time.time()) + hours * 3600


def _candidate_from_item(item: dict[str, Any]) -> Candidate:
    item = decimals_to_float(item)
    profile: CandidateProfile | None = None
    if item.get("profile"):
        profile = CandidateProfile.model_validate(item["profile"])

    signals: CandidateSignals | None = None
    if item.get("signals"):
        signals = CandidateSignals.model_validate(item["signals"])

    return Candidate(
        candidate_id=item["candidate_id"],
        session_id=item["session_id"],
        file_name=item.get("file_name", ""),
        s3_key=item.get("s3_key", ""),
        parse_status=ParseStatus(item.get("parse_status", ParseStatus.QUEUED)),
        parse_error=item.get("parse_error"),
        embedding_id=item.get("embedding_id"),
        profile=profile,
        signals=signals,
        created_at=item.get("created_at", ""),
        expires_at=int(item.get("expires_at", 0)),
    )


class CandidateRepository:
    def __init__(self) -> None:
        settings = get_settings()
        self._table_name = settings.dynamodb_table_name
        self._ttl_hours = settings.session_ttl_hours
        dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self._table = dynamodb.Table(self._table_name)

    def create(self, session_id: str, candidate_id: str, file_name: str, s3_key: str) -> Candidate:
        now = _now_iso()
        ttl = _ttl_timestamp(self._ttl_hours)
        item: dict[str, Any] = {
            "PK": f"SESSION#{session_id}",
            "SK": f"CANDIDATE#{candidate_id}",
            "candidate_id": candidate_id,
            "session_id": session_id,
            "file_name": file_name,
            "s3_key": s3_key,
            "parse_status": ParseStatus.QUEUED,
            "created_at": now,
            "expires_at": ttl,
        }
        self._table.put_item(Item=item)
        logger.info("candidate_created", candidate_id=candidate_id, session_id=session_id)
        return _candidate_from_item(item)

    def get(self, session_id: str, candidate_id: str) -> Candidate:
        resp = self._table.get_item(
            Key={
                "PK": f"SESSION#{session_id}",
                "SK": f"CANDIDATE#{candidate_id}",
            }
        )
        item = resp.get("Item")
        if not item:
            raise CandidateNotFoundError(candidate_id)
        return _candidate_from_item(item)

    def list_by_session(self, session_id: str) -> list[CandidateListItem]:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"SESSION#{session_id}") & Key("SK").begins_with("CANDIDATE#")
            )
        )
        results: list[CandidateListItem] = []
        for item in resp.get("Items", []):
            profile_data = item.get("profile") or {}
            results.append(
                CandidateListItem(
                    candidate_id=item["candidate_id"],
                    file_name=item.get("file_name", ""),
                    parse_status=ParseStatus(item.get("parse_status", ParseStatus.QUEUED)),
                    full_name=profile_data.get("full_name", ""),
                    current_title=profile_data.get("current_title", ""),
                    current_company=profile_data.get("current_company", ""),
                    parse_error=item.get("parse_error"),
                )
            )
        return results

    def list_ready_by_session(self, session_id: str) -> list[Candidate]:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"SESSION#{session_id}") & Key("SK").begins_with("CANDIDATE#")
            ),
            FilterExpression="#ps = :ready",
            ExpressionAttributeNames={"#ps": "parse_status"},
            ExpressionAttributeValues={":ready": ParseStatus.READY},
        )
        return [_candidate_from_item(item) for item in resp.get("Items", [])]

    def update_status(
        self,
        session_id: str,
        candidate_id: str,
        status: ParseStatus,
        error: str | None = None,
    ) -> None:
        update_expr = "SET parse_status = :status, updated_at = :now"
        expr_values: dict[str, Any] = {":status": status, ":now": _now_iso()}
        if error is not None:
            update_expr += ", parse_error = :err"
            expr_values[":err"] = error
        self._table.update_item(
            Key={
                "PK": f"SESSION#{session_id}",
                "SK": f"CANDIDATE#{candidate_id}",
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )

    def update_parsed(
        self,
        session_id: str,
        candidate_id: str,
        profile: CandidateProfile,
        signals: CandidateSignals,
        embedding_id: str,
    ) -> None:
        self._table.update_item(
            Key={
                "PK": f"SESSION#{session_id}",
                "SK": f"CANDIDATE#{candidate_id}",
            },
            UpdateExpression=(
                "SET parse_status = :status, #profile = :profile, "
                "#signals = :signals, embedding_id = :eid, updated_at = :now"
            ),
            ExpressionAttributeNames={
                "#profile": "profile",
                "#signals": "signals",
            },
            ExpressionAttributeValues={
                ":status": ParseStatus.READY,
                ":profile": floats_to_decimal(profile.model_dump()),
                ":signals": floats_to_decimal(signals.model_dump()),
                ":eid": embedding_id,
                ":now": _now_iso(),
            },
        )

    def update_traits_match(
        self,
        session_id: str,
        candidate_id: str,
        traits_match_score: int,
        traits_breakdown: list[dict[str, Any]],
    ) -> None:
        self._table.update_item(
            Key={
                "PK": f"SESSION#{session_id}",
                "SK": f"CANDIDATE#{candidate_id}",
            },
            UpdateExpression=("SET signals.traits_match = :tm, updated_at = :now"),
            ExpressionAttributeValues={
                ":tm": floats_to_decimal(
                    {
                        "traits_match_score": traits_match_score,
                        "traits_breakdown": traits_breakdown,
                    }
                ),
                ":now": _now_iso(),
            },
        )

    def delete_by_session(self, session_id: str) -> None:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"SESSION#{session_id}") & Key("SK").begins_with("CANDIDATE#")
            ),
            ProjectionExpression="PK, SK",
        )
        with self._table.batch_writer() as batch:
            for item in resp.get("Items", []):
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
