from __future__ import annotations

import csv
import io
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from backend.core.auth import CurrentUser, verify_token
from backend.core.config import get_settings
from backend.core.exceptions import RankingNotFoundError, ValidationError
from backend.models.ranking import (
    RankingResult,
    RankingStatus,
    RankingWeights,
    RankRequest,
    RankResponse,
)
from backend.repositories.candidates import CandidateRepository
from backend.repositories.dynamo_utils import decimals_to_float, floats_to_decimal
from backend.repositories.sessions import SessionRepository

router = APIRouter(prefix="/sessions/{session_id}", tags=["rankings"])
logger = structlog.get_logger(__name__)


def _ttl_timestamp(hours: int = 24) -> int:
    return int(time.time()) + hours * 3600


def _ranking_from_item(item: dict[str, Any]) -> RankingResult:
    item = decimals_to_float(item)
    weights_raw = item.get("weights", {})
    weights = RankingWeights(
        semantic=weights_raw.get("semantic", 0.30),
        skills=weights_raw.get("skills", 0.25),
        trajectory=weights_raw.get("trajectory", 0.25),
        behavioral=weights_raw.get("behavioral", 0.20),
    )
    from backend.models.ranking import (
        BehavioralBreakdown,
        Confidence,
        RankedCandidate,
        ScoreBreakdown,
    )

    ranked_raw = item.get("ranked_candidates", [])
    ranked = []
    for r in ranked_raw:
        bd = r.get("score_breakdown", {})
        bbd = r.get("behavioral_breakdown", {})
        ranked.append(
            RankedCandidate(
                rank=int(r.get("rank", 0)),
                candidate_id=r.get("candidate_id", ""),
                full_name=r.get("full_name", ""),
                current_title=r.get("current_title", ""),
                current_company=r.get("current_company", ""),
                composite_score=float(r.get("composite_score", 0)),
                score_breakdown=ScoreBreakdown(
                    semantic_fit=float(bd.get("semantic_fit", 0)),
                    skills_match=float(bd.get("skills_match", 0)),
                    trajectory=float(bd.get("trajectory", 0)),
                    behavioral=float(bd.get("behavioral", 0)),
                ),
                behavioral_breakdown=BehavioralBreakdown(
                    career_momentum=int(bbd.get("career_momentum", 0)),
                    learning_velocity=int(bbd.get("learning_velocity", 0)),
                    role_consistency=int(bbd.get("role_consistency", 0)),
                    job_stability=int(bbd.get("job_stability", 0)),
                    promotion_frequency=int(bbd.get("promotion_frequency", 0)),
                    upskilling_pattern=int(bbd.get("upskilling_pattern", 0)),
                ),
                traits_match_score=float(r.get("traits_match_score", 0)),
                explanation=r.get("explanation", ""),
                strengths=list(r.get("strengths", [])),
                gaps=list(r.get("gaps", [])),
                behavioral_highlights=list(r.get("behavioral_highlights", [])),
                confidence=Confidence(r.get("confidence", Confidence.MEDIUM)),
            )
        )
    return RankingResult(
        ranking_job_id=item["ranking_job_id"],
        session_id=item["session_id"],
        status=RankingStatus(item.get("status", RankingStatus.PROCESSING)),
        weights=weights,
        top_n=int(item.get("top_n", 20)),
        ranked_candidates=ranked,
        created_at=item.get("created_at", ""),
        completed_at=item.get("completed_at"),
        expires_at=int(item.get("expires_at", 0)),
        error_message=item.get("error_message"),
    )


def _save_ranking(ranking: RankingResult, table: Any) -> None:
    item: dict[str, Any] = {
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


@router.post("/rank", response_model=RankResponse, status_code=202)
async def start_ranking(
    session_id: str,
    body: RankRequest,
    current_user: CurrentUser = Depends(verify_token),
) -> RankResponse:
    settings = get_settings()
    session_repo = SessionRepository()
    session = session_repo.get(session_id, current_user["user_id"])

    if not session.jd_requirements or not session.jd_embedding_id:
        raise ValidationError("Job description must be analyzed before ranking")

    if not body.weights.validate_sum():
        raise ValidationError("Ranking weights must sum to 1.0")

    candidate_repo = CandidateRepository()
    ready_candidates = candidate_repo.list_ready_by_session(session_id)
    if not ready_candidates:
        raise ValidationError(
            "No candidates ready for ranking. Please wait for parsing to complete."
        )

    ranking_job_id = str(uuid.uuid4())
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    message = {
        "session_id": session_id,
        "ranking_job_id": ranking_job_id,
        "weights": body.weights.model_dump(),
        "top_n": body.top_n,
        "user_id": current_user["user_id"],
    }
    sqs.send_message(
        QueueUrl=settings.sqs_rank_queue_url,
        MessageBody=json.dumps(message),
        MessageGroupId=session_id,
        MessageDeduplicationId=ranking_job_id,
    )

    import boto3 as _boto3

    dynamodb = _boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table(settings.dynamodb_table_name)
    ranking = RankingResult(
        ranking_job_id=ranking_job_id,
        session_id=session_id,
        status=RankingStatus.PROCESSING,
        weights=body.weights,
        top_n=body.top_n,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=_ttl_timestamp(settings.session_ttl_hours),
    )
    _save_ranking(ranking, table)

    logger.info("ranking_job_queued", ranking_job_id=ranking_job_id, session_id=session_id)
    return RankResponse(
        ranking_job_id=ranking_job_id,
        status=RankingStatus.PROCESSING,
        message="Ranking job started",
    )


@router.get("/rankings", response_model=RankingResult)
async def get_rankings(
    session_id: str,
    job_id: str = Query(...),
    current_user: CurrentUser = Depends(verify_token),
) -> RankingResult:
    settings = get_settings()
    session_repo = SessionRepository()
    session_repo.get(session_id, current_user["user_id"])

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table(settings.dynamodb_table_name)
    resp = table.get_item(Key={"PK": f"SESSION#{session_id}", "SK": f"RANKING#{job_id}"})
    item = resp.get("Item")
    if not item:
        raise RankingNotFoundError(job_id)
    return _ranking_from_item(item)


@router.get("/candidates/{candidate_id}")
async def get_candidate(
    session_id: str,
    candidate_id: str,
    current_user: CurrentUser = Depends(verify_token),
) -> dict[str, Any]:
    session_repo = SessionRepository()
    session_repo.get(session_id, current_user["user_id"])

    candidate_repo = CandidateRepository()
    candidate = candidate_repo.get(session_id, candidate_id)
    return candidate.model_dump()


@router.get("/export")
async def export_csv(
    session_id: str,
    job_id: str = Query(...),
    current_user: CurrentUser = Depends(verify_token),
) -> StreamingResponse:
    settings = get_settings()
    session_repo = SessionRepository()
    session_repo.get(session_id, current_user["user_id"])

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table(settings.dynamodb_table_name)
    resp = table.get_item(Key={"PK": f"SESSION#{session_id}", "SK": f"RANKING#{job_id}"})
    item = resp.get("Item")
    if not item:
        raise RankingNotFoundError(job_id)

    ranking = _ranking_from_item(item)

    output = io.StringIO()
    fieldnames = [
        "rank",
        "full_name",
        "current_title",
        "current_company",
        "composite_score",
        "semantic_fit",
        "skills_match",
        "trajectory",
        "behavioral",
        "career_momentum",
        "learning_velocity",
        "role_consistency",
        "job_stability",
        "promotion_frequency",
        "upskilling_pattern",
        "traits_match_score",
        "confidence",
        "explanation",
        "strengths",
        "gaps",
        "behavioral_highlights",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for rc in ranking.ranked_candidates:
        writer.writerow(
            {
                "rank": rc.rank,
                "full_name": rc.full_name,
                "current_title": rc.current_title,
                "current_company": rc.current_company,
                "composite_score": rc.composite_score,
                "semantic_fit": rc.score_breakdown.semantic_fit,
                "skills_match": rc.score_breakdown.skills_match,
                "trajectory": rc.score_breakdown.trajectory,
                "behavioral": rc.score_breakdown.behavioral,
                "career_momentum": rc.behavioral_breakdown.career_momentum,
                "learning_velocity": rc.behavioral_breakdown.learning_velocity,
                "role_consistency": rc.behavioral_breakdown.role_consistency,
                "job_stability": rc.behavioral_breakdown.job_stability,
                "promotion_frequency": rc.behavioral_breakdown.promotion_frequency,
                "upskilling_pattern": rc.behavioral_breakdown.upskilling_pattern,
                "traits_match_score": rc.traits_match_score,
                "confidence": rc.confidence,
                "explanation": rc.explanation,
                "strengths": " | ".join(rc.strengths),
                "gaps": " | ".join(rc.gaps),
                "behavioral_highlights": " | ".join(rc.behavioral_highlights),
            }
        )

    output.seek(0)
    filename = f"talentlens_shortlist_{session_id[:8]}_{job_id[:8]}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
