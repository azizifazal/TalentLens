from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RankingStatus(str, Enum):
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RankingWeights(BaseModel):
    semantic: float = Field(default=0.30, ge=0.0, le=1.0)
    skills: float = Field(default=0.25, ge=0.0, le=1.0)
    trajectory: float = Field(default=0.25, ge=0.0, le=1.0)
    behavioral: float = Field(default=0.20, ge=0.0, le=1.0)

    def validate_sum(self) -> bool:
        total = round(self.semantic + self.skills + self.trajectory + self.behavioral, 4)
        return abs(total - 1.0) < 0.01


class ScoreBreakdown(BaseModel):
    semantic_fit: float = 0.0
    skills_match: float = 0.0
    trajectory: float = 0.0
    behavioral: float = 0.0


class BehavioralBreakdown(BaseModel):
    career_momentum: int = 0
    learning_velocity: int = 0
    role_consistency: int = 0
    job_stability: int = 0
    promotion_frequency: int = 0
    upskilling_pattern: int = 0


class RankedCandidate(BaseModel):
    rank: int
    candidate_id: str
    full_name: str = ""
    current_title: str = ""
    current_company: str = ""
    composite_score: float = 0.0
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    behavioral_breakdown: BehavioralBreakdown = Field(default_factory=BehavioralBreakdown)
    traits_match_score: float = 0.0
    explanation: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    behavioral_highlights: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM


class RankingResult(BaseModel):
    ranking_job_id: str
    session_id: str
    status: RankingStatus = RankingStatus.PROCESSING
    weights: RankingWeights = Field(default_factory=RankingWeights)
    top_n: int = 20
    ranked_candidates: list[RankedCandidate] = Field(default_factory=list)
    created_at: str = ""
    completed_at: Optional[str] = None
    expires_at: int = 0
    error_message: Optional[str] = None


class RankRequest(BaseModel):
    weights: RankingWeights = Field(default_factory=RankingWeights)
    top_n: int = Field(default=20, ge=5, le=50)


class RankResponse(BaseModel):
    ranking_job_id: str
    status: RankingStatus
    message: str = ""
