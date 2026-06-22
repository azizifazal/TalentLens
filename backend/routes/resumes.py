from __future__ import annotations

import json
import uuid
from typing import Any

import boto3
import structlog
from fastapi import APIRouter, Depends

from backend.core.auth import CurrentUser, verify_token
from backend.core.config import get_settings
from backend.core.exceptions import ValidationError
from backend.models.candidate import (
    CandidateListItem,
    ConfirmUploadRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from backend.repositories.candidates import CandidateRepository
from backend.repositories.sessions import SessionRepository

router = APIRouter(prefix="/sessions/{session_id}/resumes", tags=["resumes"])
logger = structlog.get_logger(__name__)

_ALLOWED_EXTENSIONS = {".pdf", ".docx"}
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


@router.get("", response_model=list[CandidateListItem])
async def list_candidates(
    session_id: str,
    current_user: CurrentUser = Depends(verify_token),
) -> list[CandidateListItem]:
    session_repo = SessionRepository()
    session_repo.get(session_id, current_user["user_id"])
    candidate_repo = CandidateRepository()
    return candidate_repo.list_by_session(session_id)


@router.post("/upload-url", response_model=UploadUrlResponse, status_code=201)
async def get_upload_url(
    session_id: str,
    body: UploadUrlRequest,
    current_user: CurrentUser = Depends(verify_token),
) -> UploadUrlResponse:
    settings = get_settings()

    session_repo = SessionRepository()
    session = session_repo.get(session_id, current_user["user_id"])

    if session.candidate_count >= settings.max_candidates_per_session:
        raise ValidationError(
            f"Session has reached the maximum of {settings.max_candidates_per_session} candidates"
        )

    ext = ""
    lower_name = body.file_name.lower()
    for allowed in _ALLOWED_EXTENSIONS:
        if lower_name.endswith(allowed):
            ext = allowed
            break
    if not ext:
        raise ValidationError("Only PDF and Word (.docx) files are supported")

    if body.file_size_bytes > _MAX_FILE_SIZE_BYTES:
        raise ValidationError("File size exceeds 10MB limit")

    candidate_id = str(uuid.uuid4())
    s3_key = f"uploads/{session_id}/{candidate_id}/original{ext}"

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": s3_key,
            "ContentType": "application/octet-stream",
        },
        ExpiresIn=900,
    )

    candidate_repo = CandidateRepository()
    candidate_repo.create(
        session_id=session_id,
        candidate_id=candidate_id,
        file_name=body.file_name,
        s3_key=s3_key,
    )

    session_repo.increment_candidate_count(session_id)
    logger.info("upload_url_generated", candidate_id=candidate_id, session_id=session_id)
    return UploadUrlResponse(
        candidate_id=candidate_id,
        upload_url=upload_url,
        s3_key=s3_key,
    )


@router.post("/confirm", status_code=202)
async def confirm_upload(
    session_id: str,
    body: ConfirmUploadRequest,
    current_user: CurrentUser = Depends(verify_token),
) -> dict[str, Any]:
    settings = get_settings()
    session_repo = SessionRepository()
    session_repo.get(session_id, current_user["user_id"])

    candidate_repo = CandidateRepository()
    candidate = candidate_repo.get(session_id, body.candidate_id)

    sqs = boto3.client("sqs", region_name=settings.aws_region)
    message = {
        "session_id": session_id,
        "candidate_id": body.candidate_id,
        "s3_key": candidate.s3_key,
        "file_name": candidate.file_name,
    }
    sqs.send_message(
        QueueUrl=settings.sqs_parse_queue_url,
        MessageBody=json.dumps(message),
        MessageGroupId=session_id,
        MessageDeduplicationId=body.candidate_id,
    )
    logger.info("parse_job_queued", candidate_id=body.candidate_id, session_id=session_id)
    return {
        "candidate_id": body.candidate_id,
        "status": "queued",
        "message": "Resume queued for processing",
    }
