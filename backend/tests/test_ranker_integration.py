from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.models.candidate import (
    Candidate,
    CandidateProfile,
    CandidateSignals,
    BehavioralSignals,
    CareerSignals,
    ParseStatus,
    TraitsMatchResult,
)
from backend.models.ranking import RankingResult, RankingStatus, RankingWeights
from backend.models.session import JDRequirements, Session, SessionStatus


def _make_candidate(candidate_id: str, name: str, semantic_friendly: bool = True) -> Candidate:
    profile = CandidateProfile(
        full_name=name,
        current_title="Senior Engineer",
        current_company="TestCo",
        years_experience=6.0,
        skills=[],
        work_history=[],
        raw_behavioral_evidence=["Led a major initiative"],
    )
    signals = CandidateSignals(
        behavioral=BehavioralSignals(
            career_momentum=80, learning_velocity=75, role_consistency=70,
            job_stability=85, promotion_frequency=60, upskilling_pattern=65,
            behavioral_composite=75 if semantic_friendly else 30,
        ),
        career=CareerSignals(career_trajectory=80 if semantic_friendly else 25, avg_tenure_months=24),
        skills_currency_score=85 if semantic_friendly else 20,
        traits_match=TraitsMatchResult(traits_match_score=70),
    )
    return Candidate(
        candidate_id=candidate_id,
        session_id="session-1",
        file_name=f"{name}.pdf",
        s3_key=f"uploads/session-1/{candidate_id}/original.pdf",
        parse_status=ParseStatus.READY,
        profile=profile,
        signals=signals,
    )


@pytest.fixture
def mock_session() -> Session:
    return Session(
        session_id="session-1",
        user_id="user-1",
        job_title="Senior Backend Engineer",
        status=SessionStatus.INGESTING,
        candidate_count=2,
        jd_embedding_id="jd_session-1",
        jd_requirements=JDRequirements(
            required_skills=["Python", "AWS"],
            success_traits=["self-starter"],
        ),
    )


class TestRankerCompositeScoring:
    @patch("backend.services.ranker.TraitsMatcherService")
    @patch("backend.services.ranker.CandidateRepository")
    @patch("backend.services.ranker.VectorRepository")
    @patch("backend.services.ranker.BedrockClient")
    def test_higher_signal_candidate_ranks_first(
        self, mock_bedrock_cls, mock_vector_cls, mock_candidate_repo_cls, mock_traits_cls, mock_session
    ):
        strong_candidate = _make_candidate("cand-strong", "Strong Candidate", semantic_friendly=True)
        weak_candidate = _make_candidate("cand-weak", "Weak Candidate", semantic_friendly=False)

        mock_vector = MagicMock()
        mock_vector.get_jd_embedding.return_value = [0.1] * 1024
        mock_vector.knn_search.return_value = [
            {"candidate_id": "cand-strong", "cosine_score": 0.9},
            {"candidate_id": "cand-weak", "cosine_score": 0.5},
        ]
        mock_vector_cls.return_value = mock_vector

        mock_candidate_repo = MagicMock()
        mock_candidate_repo.get.side_effect = lambda sid, cid: (
            strong_candidate if cid == "cand-strong" else weak_candidate
        )
        mock_candidate_repo_cls.return_value = mock_candidate_repo

        mock_traits = MagicMock()
        mock_traits.match_batch.return_value = {
            "cand-strong": TraitsMatchResult(traits_match_score=80),
            "cand-weak": TraitsMatchResult(traits_match_score=40),
        }
        mock_traits_cls.return_value = mock_traits

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_claude_json.return_value = {
            "explanation": "Strong fit based on evidence.",
            "strengths": ["Relevant experience"],
            "gaps": [],
            "behavioral_highlights": ["High momentum"],
            "confidence": "HIGH",
        }
        mock_bedrock_cls.return_value = mock_bedrock

        from backend.services.ranker import RankerService

        ranker = RankerService()
        ranking_result = RankingResult(
            ranking_job_id="job-1",
            session_id="session-1",
            status=RankingStatus.PROCESSING,
            weights=RankingWeights(),
            top_n=10,
        )

        result = ranker.run_ranking(mock_session, ranking_result)

        assert result.status == RankingStatus.COMPLETE
        assert len(result.ranked_candidates) == 2
        assert result.ranked_candidates[0].candidate_id == "cand-strong"
        assert result.ranked_candidates[0].rank == 1
        assert result.ranked_candidates[0].composite_score > result.ranked_candidates[1].composite_score

    @patch("backend.services.ranker.TraitsMatcherService")
    @patch("backend.services.ranker.CandidateRepository")
    @patch("backend.services.ranker.VectorRepository")
    @patch("backend.services.ranker.BedrockClient")
    def test_empty_knn_results_marks_ranking_failed(
        self, mock_bedrock_cls, mock_vector_cls, mock_candidate_repo_cls, mock_traits_cls, mock_session
    ):
        mock_vector = MagicMock()
        mock_vector.get_jd_embedding.return_value = [0.1] * 1024
        mock_vector.knn_search.return_value = []
        mock_vector_cls.return_value = mock_vector

        from backend.services.ranker import RankerService

        ranker = RankerService()
        ranking_result = RankingResult(
            ranking_job_id="job-2",
            session_id="session-1",
            status=RankingStatus.PROCESSING,
            weights=RankingWeights(),
            top_n=10,
        )

        result = ranker.run_ranking(mock_session, ranking_result)
        assert result.status == RankingStatus.FAILED
        assert result.error_message is not None

    @patch("backend.services.ranker.TraitsMatcherService")
    @patch("backend.services.ranker.CandidateRepository")
    @patch("backend.services.ranker.VectorRepository")
    @patch("backend.services.ranker.BedrockClient")
    def test_confidence_levels_assigned_correctly(
        self, mock_bedrock_cls, mock_vector_cls, mock_candidate_repo_cls, mock_traits_cls, mock_session
    ):
        from backend.services.ranker import RankerService

        ranker = RankerService()
        assert ranker._determine_confidence(85) == "HIGH"
        assert ranker._determine_confidence(55) == "MEDIUM"
        assert ranker._determine_confidence(20) == "LOW"
