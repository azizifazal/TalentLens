from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import boto3
import structlog

from backend.core.config import get_settings
from backend.core.exceptions import SessionNotFoundError, UnauthorizedError
from backend.models.session import JDRequirements, Session, SessionStatus, SessionSummary
from backend.repositories.dynamo_utils import decimals_to_float, floats_to_decimal

logger = structlog.get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ttl_timestamp(hours: int = 24) -> int:
    return int(time.time()) + hours * 3600


def _session_from_item(item: dict[str, Any]) -> Session:
    item = decimals_to_float(item)
    req_raw = item.get("jd_requirements")
    jd_req: JDRequirements | None = None
    if req_raw:
        jd_req = JDRequirements.model_validate(req_raw)

    return Session(
        session_id=item["session_id"],
        user_id=item["user_id"],
        job_title=item.get("job_title", ""),
        status=SessionStatus(item.get("status", SessionStatus.CREATED)),
        created_at=item.get("created_at", ""),
        updated_at=item.get("updated_at", ""),
        expires_at=int(item.get("expires_at", 0)),
        candidate_count=int(item.get("candidate_count", 0)),
        jd_raw_text=item.get("jd_raw_text", ""),
        jd_embedding_id=item.get("jd_embedding_id"),
        jd_requirements=jd_req,
    )


class SessionRepository:
    def __init__(self) -> None:
        settings = get_settings()
        self._table_name = settings.dynamodb_table_name
        self._ttl_hours = settings.session_ttl_hours
        self._dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self._table = self._dynamodb.Table(self._table_name)

    def create(self, user_id: str, job_title: str, session_id: str) -> Session:
        now = _now_iso()
        ttl = _ttl_timestamp(self._ttl_hours)
        item = {
            "PK": f"SESSION#{session_id}",
            "SK": "METADATA",
            "GSI1PK": f"USER#{user_id}",
            "GSI1SK": f"SESSION#{now}",
            "session_id": session_id,
            "user_id": user_id,
            "job_title": job_title,
            "status": SessionStatus.CREATED,
            "created_at": now,
            "updated_at": now,
            "expires_at": ttl,
            "candidate_count": 0,
            "jd_raw_text": "",
        }
        self._table.put_item(Item=item)
        logger.info("session_created", session_id=session_id, user_id=user_id)
        return _session_from_item(item)

    def get(self, session_id: str, user_id: str | None = None) -> Session:
        resp = self._table.get_item(Key={"PK": f"SESSION#{session_id}", "SK": "METADATA"})
        item = resp.get("Item")
        if not item:
            raise SessionNotFoundError(session_id)
        session = _session_from_item(item)
        if user_id and session.user_id != user_id:
            raise UnauthorizedError()
        return session

    def list_by_user(self, user_id: str) -> list[SessionSummary]:
        resp = self._table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": f"USER#{user_id}"},
            ScanIndexForward=False,
        )
        results: list[SessionSummary] = []
        for item in resp.get("Items", []):
            results.append(
                SessionSummary(
                    session_id=item["session_id"],
                    job_title=item.get("job_title", ""),
                    status=SessionStatus(item.get("status", SessionStatus.CREATED)),
                    candidate_count=int(item.get("candidate_count", 0)),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
            )
        return results

    def update_jd(
        self,
        session_id: str,
        jd_raw_text: str,
        jd_requirements: JDRequirements,
        embedding_id: str,
    ) -> None:
        now = _now_iso()
        self._table.update_item(
            Key={"PK": f"SESSION#{session_id}", "SK": "METADATA"},
            UpdateExpression=(
                "SET #status = :status, jd_raw_text = :raw, "
                "jd_requirements = :req, jd_embedding_id = :eid, "
                "updated_at = :now"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": SessionStatus.JD_ANALYZED,
                ":raw": jd_raw_text,
                ":req": floats_to_decimal(jd_requirements.model_dump()),
                ":eid": embedding_id,
                ":now": now,
            },
        )

    def increment_candidate_count(self, session_id: str) -> None:
        self._table.update_item(
            Key={"PK": f"SESSION#{session_id}", "SK": "METADATA"},
            UpdateExpression=(
                "SET candidate_count = if_not_exists(candidate_count, :zero) + :one, "
                "#status = :status, updated_at = :now"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":status": SessionStatus.INGESTING,
                ":now": _now_iso(),
            },
        )

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        self._table.update_item(
            Key={"PK": f"SESSION#{session_id}", "SK": "METADATA"},
            UpdateExpression="SET #status = :status, updated_at = :now",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status, ":now": _now_iso()},
        )

    def delete(self, session_id: str, user_id: str) -> None:
        self.get(session_id, user_id)
        self._table.delete_item(Key={"PK": f"SESSION#{session_id}", "SK": "METADATA"})
        logger.info("session_deleted", session_id=session_id)
