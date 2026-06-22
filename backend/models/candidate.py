from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SkillDepth(str, Enum):
    AWARE = "AWARE"
    PRACTICED = "PRACTICED"
    EXPERT = "EXPERT"


class RoleLevel(str, Enum):
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    PRINCIPAL = "PRINCIPAL"
    MANAGER = "MANAGER"
    DIRECTOR = "DIRECTOR"


class ParseStatus(str, Enum):
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    COMPUTING_SIGNALS = "COMPUTING_SIGNALS"
    READY = "READY"
    ERROR = "ERROR"


class Skill(BaseModel):
    name: str
    category: str = ""
    last_used_year: Optional[int] = None
    depth: SkillDepth = SkillDepth.PRACTICED


class WorkHistory(BaseModel):
    title: str
    company: str
    start_date: str = Field(..., description="YYYY-MM format")
    end_date: Optional[str] = Field(None, description="YYYY-MM or null if current")
    duration_months: int = 0
    level_inferred: RoleLevel = RoleLevel.MID
    description_summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)


class Education(BaseModel):
    degree: str
    field: str
    institution: str
    graduation_year: Optional[int] = None


class Certification(BaseModel):
    name: str
    issuer: str
    year: int


class CandidateProfile(BaseModel):
    full_name: str = ""
    current_title: str = ""
    current_company: str = ""
    location: str = ""
    years_experience: float = 0.0
    skills: list[Skill] = Field(default_factory=list)
    work_history: list[WorkHistory] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    raw_behavioral_evidence: list[str] = Field(default_factory=list)


class BehavioralSignals(BaseModel):
    career_momentum: int = Field(default=0, ge=0, le=100)
    learning_velocity: int = Field(default=0, ge=0, le=100)
    role_consistency: int = Field(default=0, ge=0, le=100)
    job_stability: int = Field(default=0, ge=0, le=100)
    promotion_frequency: int = Field(default=0, ge=0, le=100)
    upskilling_pattern: int = Field(default=0, ge=0, le=100)
    behavioral_composite: int = Field(default=0, ge=0, le=100)


class CareerSignals(BaseModel):
    career_trajectory: int = Field(default=0, ge=0, le=100)
    avg_tenure_months: float = 0.0
    level_progression_rate: float = 0.0
    career_gap_months: int = 0


class TraitMatchLevel(str, Enum):
    STRONG = "STRONG"
    PARTIAL = "PARTIAL"
    ABSENT = "ABSENT"
    CONTRADICTED = "CONTRADICTED"


class TraitBreakdown(BaseModel):
    trait: str
    evidence: str = ""
    match_level: TraitMatchLevel = TraitMatchLevel.ABSENT


class TraitsMatchResult(BaseModel):
    traits_match_score: int = Field(default=0, ge=0, le=100)
    traits_breakdown: list[TraitBreakdown] = Field(default_factory=list)


class CandidateSignals(BaseModel):
    behavioral: BehavioralSignals = Field(default_factory=BehavioralSignals)
    career: CareerSignals = Field(default_factory=CareerSignals)
    skills_currency_score: int = Field(default=0, ge=0, le=100)
    traits_match: Optional[TraitsMatchResult] = None


class Candidate(BaseModel):
    candidate_id: str
    session_id: str
    file_name: str
    s3_key: str
    parse_status: ParseStatus = ParseStatus.QUEUED
    parse_error: Optional[str] = None
    embedding_id: Optional[str] = None
    profile: Optional[CandidateProfile] = None
    signals: Optional[CandidateSignals] = None
    created_at: str = ""
    expires_at: int = 0


class CandidateListItem(BaseModel):
    candidate_id: str
    file_name: str
    parse_status: ParseStatus
    full_name: str = ""
    current_title: str = ""
    current_company: str = ""
    parse_error: Optional[str] = None


class UploadUrlRequest(BaseModel):
    file_name: str
    file_size_bytes: int


class UploadUrlResponse(BaseModel):
    candidate_id: str
    upload_url: str
    s3_key: str


class ConfirmUploadRequest(BaseModel):
    candidate_id: str
