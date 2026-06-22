from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    JD_ANALYZED = "JD_ANALYZED"
    INGESTING = "INGESTING"
    RANKED = "RANKED"


class JDRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_min: float = 0.0
    experience_max: float = 20.0
    role_level: str = ""
    industry_context: str = ""
    education: list[str] = Field(default_factory=list)
    success_traits: list[str] = Field(default_factory=list)
    behavioral_expectations: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class Session(BaseModel):
    session_id: str
    user_id: str
    job_title: str = ""
    status: SessionStatus = SessionStatus.CREATED
    created_at: str = ""
    updated_at: str = ""
    expires_at: int = 0
    candidate_count: int = 0
    jd_raw_text: str = ""
    jd_embedding_id: Optional[str] = None
    jd_requirements: Optional[JDRequirements] = None


class CreateSessionRequest(BaseModel):
    job_title: str = Field(..., min_length=2, max_length=200)


class CreateSessionResponse(BaseModel):
    session_id: str
    job_title: str
    status: SessionStatus
    created_at: str


class AnalyzeJDRequest(BaseModel):
    jd_text: str = Field(..., min_length=50, max_length=20000)


class AnalyzeJDResponse(BaseModel):
    session_id: str
    jd_requirements: JDRequirements
    status: SessionStatus


class SessionSummary(BaseModel):
    session_id: str
    job_title: str
    status: SessionStatus
    candidate_count: int
    created_at: str
    updated_at: str
