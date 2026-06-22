from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/var/task")

import structlog

from backend.core.logging_config import configure_logging
from backend.models.candidate import ParseStatus
from backend.repositories.candidates import CandidateRepository
from backend.repositories.sessions import SessionRepository
from backend.repositories.vectors import VectorRepository
from backend.services.bedrock import BedrockClient
from backend.services.parser import ParserService
from backend.services.signals import compute_all_signals

configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = structlog.get_logger(__name__)


def handler(event: dict, context: object) -> dict:
    records = event.get("Records", [])
    failed_message_ids: list[str] = []

    for record in records:
        message_id = record.get("messageId", "")
        try:
            body = json.loads(record["body"])
            _process_parse_job(body)
        except Exception as exc:
            logger.error(
                "parse_job_failed",
                message_id=message_id,
                error=str(exc),
                exc_info=True,
            )
            failed_message_ids.append(message_id)

    if failed_message_ids:
        return {"batchItemFailures": [{"itemIdentifier": mid} for mid in failed_message_ids]}
    return {}


def _process_parse_job(body: dict) -> None:
    session_id: str = body["session_id"]
    candidate_id: str = body["candidate_id"]
    s3_key: str = body["s3_key"]

    log = logger.bind(session_id=session_id, candidate_id=candidate_id)
    log.info("parse_job_started")

    candidate_repo = CandidateRepository()
    candidate_repo.update_status(session_id, candidate_id, ParseStatus.PARSING)

    try:
        parser = ParserService()
        log.info("extracting_text")
        resume_text = parser.download_and_extract_text(s3_key)

        candidate_repo.update_status(session_id, candidate_id, ParseStatus.PARSING)

        log.info("parsing_with_ai")
        profile = parser.parse_resume_with_ai(resume_text)

        candidate_repo.update_status(session_id, candidate_id, ParseStatus.COMPUTING_SIGNALS)

        session_repo = SessionRepository()
        session = session_repo.get(session_id)
        required_skills: list[str] = []
        if session.jd_requirements:
            required_skills = session.jd_requirements.required_skills

        log.info("computing_signals")
        signals = compute_all_signals(profile, required_skills)

        log.info("generating_embedding")
        bedrock = BedrockClient()
        profile_text = _build_profile_text(profile)
        embedding = bedrock.get_embedding(profile_text)

        vector_repo = VectorRepository()
        embedding_id = vector_repo.index_candidate(
            session_id=session_id,
            candidate_id=candidate_id,
            profile_text=profile_text,
            embedding=embedding,
            expires_at=session.expires_at,
        )

        candidate_repo.update_parsed(
            session_id=session_id,
            candidate_id=candidate_id,
            profile=profile,
            signals=signals,
            embedding_id=embedding_id,
        )

        log.info("parse_job_complete")

    except Exception as exc:
        log.error("parse_job_error", error=str(exc))
        candidate_repo.update_status(
            session_id, candidate_id, ParseStatus.ERROR, error=str(exc)[:500]
        )
        raise


def _build_profile_text(profile) -> str:
    parts: list[str] = []
    if profile.full_name:
        parts.append(f"Name: {profile.full_name}")
    if profile.current_title:
        parts.append(f"Current Role: {profile.current_title}")
    if profile.skills:
        skill_names = ", ".join(s.name for s in profile.skills[:20])
        parts.append(f"Skills: {skill_names}")
    for w in profile.work_history[:5]:
        parts.append(
            f"Worked as {w.title} at {w.company} for {w.duration_months} months. "
            f"{w.description_summary}"
        )
    for e in profile.education[:2]:
        parts.append(f"Education: {e.degree} in {e.field} from {e.institution}")
    if profile.certifications:
        cert_names = ", ".join(c.name for c in profile.certifications[:5])
        parts.append(f"Certifications: {cert_names}")
    if profile.raw_behavioral_evidence:
        parts.append("Evidence: " + ". ".join(profile.raw_behavioral_evidence[:4]))
    return "\n".join(parts)
