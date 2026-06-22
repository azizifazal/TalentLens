from __future__ import annotations

import os

import pytest

os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_testpool")
os.environ.setdefault("COGNITO_CLIENT_ID", "test-client-id")
os.environ.setdefault("S3_BUCKET_NAME", "talentlens-resumes-test")
os.environ.setdefault("OPENSEARCH_ENDPOINT", "https://test.us-east-1.aoss.amazonaws.com")
os.environ.setdefault("SQS_PARSE_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/resume-parse-queue")
os.environ.setdefault("SQS_RANK_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/rank-job-queue")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")


from backend.models.candidate import (
    CandidateProfile,
    Certification,
    RoleLevel,
    Skill,
    SkillDepth,
    WorkHistory,
)


@pytest.fixture
def sample_work_history() -> list[WorkHistory]:
    return [
        WorkHistory(
            title="Software Engineer",
            company="Acme Corp",
            start_date="2018-01",
            end_date="2020-06",
            duration_months=29,
            level_inferred=RoleLevel.JUNIOR,
            description_summary="Built backend services",
            responsibilities=["API development", "Database design"],
        ),
        WorkHistory(
            title="Senior Software Engineer",
            company="Acme Corp",
            start_date="2020-07",
            end_date="2022-12",
            duration_months=29,
            level_inferred=RoleLevel.SENIOR,
            description_summary="Led backend team",
            responsibilities=["Team leadership", "System design"],
        ),
        WorkHistory(
            title="Staff Software Engineer",
            company="BetaTech",
            start_date="2023-01",
            end_date=None,
            duration_months=30,
            level_inferred=RoleLevel.LEAD,
            description_summary="Architecting platform",
            responsibilities=["Architecture", "Mentorship"],
        ),
    ]


@pytest.fixture
def sample_skills() -> list[Skill]:
    return [
        Skill(name="Python", category="Backend", last_used_year=2026, depth=SkillDepth.EXPERT),
        Skill(name="AWS", category="DevOps", last_used_year=2025, depth=SkillDepth.EXPERT),
        Skill(name="React", category="Frontend", last_used_year=2023, depth=SkillDepth.PRACTICED),
        Skill(name="Kubernetes", category="DevOps", last_used_year=2026, depth=SkillDepth.PRACTICED),
        Skill(name="Machine Learning", category="ML", last_used_year=2025, depth=SkillDepth.AWARE),
    ]


@pytest.fixture
def sample_certifications() -> list[Certification]:
    return [
        Certification(name="AWS Solutions Architect", issuer="AWS", year=2024),
        Certification(name="CKA", issuer="CNCF", year=2025),
    ]


@pytest.fixture
def sample_profile(sample_work_history, sample_skills, sample_certifications) -> CandidateProfile:
    return CandidateProfile(
        full_name="Jordan Martinez",
        current_title="Staff Software Engineer",
        current_company="BetaTech",
        location="Austin, TX",
        years_experience=8.0,
        skills=sample_skills,
        work_history=sample_work_history,
        education=[],
        certifications=sample_certifications,
        raw_behavioral_evidence=[
            "Promoted from Software Engineer to Senior in 30 months",
            "Led migration of monolith to microservices architecture",
            "Completed AWS Solutions Architect certification while working full-time",
        ],
    )
