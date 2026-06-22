from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/var/task")

import boto3
import structlog

from backend.core.config import get_settings
from backend.core.logging_config import configure_logging
from backend.models.ranking import (
    RankingResult,
    RankingStatus,
    RankingWeights,
)
from backend.repositories.dynamo_utils import floats_to_decimal
from backend.repositories.sessions import SessionRepository
from backend.services.ranker import RankerService

configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = structlog.get_logger(__name__)


def _ttl_timestamp(hours: int = 24) -> int:
    return int(time.time()) + hours * 3600


def _save_ranking(ranking: RankingResult) -> None:
    settings = get_settings()
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table(settings.dynamodb_table_name)
    item = {
        "PK": f"SESSION#{ranking.session_id}",
        "SK": f"RANKING#{ranking.ranking_job_id}",
        "ranking_job_id": ranking.ranking_job_id,
        "session_id": ranking.session_id,
        "status": ranking.status,
        "weights": floats_to_decimal(ranking.weights.model_dump()),
        "top_n": ranking.top_n,
        "ranked_candidates": floats_to_decimal(
            [rc.model_dump() for rc in ranking.ranked_candidates]
        ),
        "created_at": ranking.created_at,
        "completed_at": ranking.completed_at,
        "expires_at": ranking.expires_at,
    }
    if ranking.error_message:
        item["error_message"] = ranking.error_message
    table.put_item(Item=item)


def handler(event: dict, context: object) -> dict:
    records = event.get("Records", [])
    failed_message_ids: list[str] = []

    for record in records:
        message_id = record.get("messageId", "")
        try:
            body = json.loads(record["body"])
            _process_ranking_job(body)
        except Exception as exc:
            logger.error(
                "ranking_job_failed",
                message_id=message_id,
                error=str(exc),
                exc_info=True,
            )
            failed_message_ids.append(message_id)

    if failed_message_ids:
        return {"batchItemFailures": [{"itemIdentifier": mid} for mid in failed_message_ids]}
    return {}


def _process_ranking_job(body: dict) -> None:
    session_id: str = body["session_id"]
    ranking_job_id: str = body["ranking_job_id"]
    weights_raw: dict = body.get("weights", {})
    top_n: int = int(body.get("top_n", 20))

    log = logger.bind(session_id=session_id, ranking_job_id=ranking_job_id)
    log.info("ranking_job_started")

    settings = get_settings()

    weights = RankingWeights(
        semantic=weights_raw.get("semantic", 0.30),
        skills=weights_raw.get("skills", 0.25),
        trajectory=weights_raw.get("trajectory", 0.25),
        behavioral=weights_raw.get("behavioral", 0.20),
    )

    ranking = RankingResult(
        ranking_job_id=ranking_job_id,
        session_id=session_id,
        status=RankingStatus.PROCESSING,
        weights=weights,
        top_n=top_n,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=_ttl_timestamp(settings.session_ttl_hours),
    )

    try:
        session_repo = SessionRepository()
        session = session_repo.get(session_id)

        ranker = RankerService()
        log.info("running_ranking_engine")
        ranking = ranker.run_ranking(session=session, ranking_result=ranking)

        _save_ranking(ranking)
        log.info("ranking_job_complete", candidates_ranked=len(ranking.ranked_candidates))

    except Exception as exc:
        log.error("ranking_engine_error", error=str(exc))
        ranking.status = RankingStatus.FAILED
        ranking.error_message = str(exc)[:500]
        ranking.completed_at = datetime.now(timezone.utc).isoformat()
        _save_ranking(ranking)
        raise
