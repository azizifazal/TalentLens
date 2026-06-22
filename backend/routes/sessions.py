from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends

from backend.core.auth import CurrentUser, verify_token
from backend.core.exceptions import ValidationError
from backend.models.session import (
    AnalyzeJDRequest,
    AnalyzeJDResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    JDRequirements,
    SessionSummary,
)
from backend.repositories.candidates import CandidateRepository
from backend.repositories.sessions import SessionRepository
from backend.repositories.vectors import VectorRepository
from backend.services.bedrock import BedrockClient

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = structlog.get_logger(__name__)

_JD_SYSTEM = """You are an expert technical recruiter and organizational psychologist.
Extract structured requirements AND behavioral success traits from job descriptions.
Return ONLY valid JSON matching the exact schema. Do not add commentary or markdown."""

_JD_PROMPT = """Analyze this job description.

Job Description:
{jd_text}

Return JSON exactly:
{{
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "experience_min": number,
  "experience_max": number,
  "role_level": "junior|mid|senior|lead|principal",
  "industry_context": "string",
  "education": ["string"],
  "success_traits": ["personality/behavioral trait, e.g. self-starter, thrives in ambiguity"],
  "behavioral_expectations": ["observable pattern, e.g. rapid skill acquisition expected"],
  "red_flags": ["string"]
}}"""


def _safe_float(val: object, default: float) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _safe_list(val: object) -> list:
    if isinstance(val, list):
        return val
    return []


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    current_user: CurrentUser = Depends(verify_token),
) -> list[SessionSummary]:
    repo = SessionRepository()
    return repo.list_by_user(current_user["user_id"])


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    current_user: CurrentUser = Depends(verify_token),
) -> CreateSessionResponse:
    session_id = str(uuid.uuid4())
    repo = SessionRepository()
    session = repo.create(
        user_id=current_user["user_id"],
        job_title=body.job_title,
        session_id=session_id,
    )
    logger.info("session_created_api", session_id=session_id)
    return CreateSessionResponse(
        session_id=session.session_id,
        job_title=session.job_title,
        status=session.status,
        created_at=session.created_at,
    )


@router.get("/{session_id}", response_model=SessionSummary)
async def get_session(
    session_id: str,
    current_user: CurrentUser = Depends(verify_token),
) -> SessionSummary:
    repo = SessionRepository()
    session = repo.get(session_id, current_user["user_id"])
    return SessionSummary(
        session_id=session.session_id,
        job_title=session.job_title,
        status=session.status,
        candidate_count=session.candidate_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post("/{session_id}/jd", response_model=AnalyzeJDResponse)
async def analyze_jd(
    session_id: str,
    body: AnalyzeJDRequest,
    current_user: CurrentUser = Depends(verify_token),
) -> AnalyzeJDResponse:
    repo = SessionRepository()
    repo.get(session_id, current_user["user_id"])

    bedrock = BedrockClient()
    raw = bedrock.invoke_claude_json(
        user_prompt=_JD_PROMPT.format(jd_text=body.jd_text[:15000]),
        system_prompt=_JD_SYSTEM,
        max_tokens=2000,
    )

    req = JDRequirements(
        required_skills=_safe_list(raw.get("required_skills"))[:20],
        preferred_skills=_safe_list(raw.get("preferred_skills"))[:15],
        experience_min=_safe_float(raw.get("experience_min"), 0.0),
        experience_max=_safe_float(raw.get("experience_max"), 20.0),
        role_level=str(raw.get("role_level") or "").lower(),
        industry_context=str(raw.get("industry_context") or ""),
        education=_safe_list(raw.get("education"))[:5],
        success_traits=_safe_list(raw.get("success_traits"))[:10],
        behavioral_expectations=_safe_list(raw.get("behavioral_expectations"))[:8],
        red_flags=_safe_list(raw.get("red_flags"))[:5],
    )

    if len(req.required_skills) < 1:
        raise ValidationError(
            "Could not extract required skills from job description. Please provide more detail."
        )

    vector_repo = VectorRepository()
    jd_embedding = bedrock.get_embedding(body.jd_text[:8000])
    session = repo.get(session_id)
    embedding_id = vector_repo.index_jd(
        session_id=session_id,
        jd_text=body.jd_text,
        embedding=jd_embedding,
        expires_at=session.expires_at,
    )

    repo.update_jd(
        session_id=session_id,
        jd_raw_text=body.jd_text,
        jd_requirements=req,
        embedding_id=embedding_id,
    )

    logger.info("jd_analyzed", session_id=session_id, skills_found=len(req.required_skills))
    return AnalyzeJDResponse(
        session_id=session_id,
        jd_requirements=req,
        status="JD_ANALYZED",
    )


@router.delete("/{session_id}", status_code=204, response_model=None)
async def delete_session(
    session_id: str,
    current_user: CurrentUser = Depends(verify_token),
) -> None:
    session_repo = SessionRepository()
    session_repo.delete(session_id, current_user["user_id"])

    candidate_repo = CandidateRepository()
    candidate_repo.delete_by_session(session_id)

    try:
        vector_repo = VectorRepository()
        vector_repo.delete_by_session(session_id)
    except Exception as exc:
        logger.warning("vector_delete_failed", session_id=session_id, error=str(exc))

    logger.info("session_deleted_api", session_id=session_id)
