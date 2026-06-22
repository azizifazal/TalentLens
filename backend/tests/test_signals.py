from __future__ import annotations

from backend.models.candidate import RoleLevel, WorkHistory
from backend.services.signals import (
    compute_all_signals,
    compute_behavioral_composite,
    compute_career_momentum,
    compute_career_trajectory,
    compute_job_stability,
    compute_learning_velocity,
    compute_promotion_frequency,
    compute_role_consistency,
    compute_skills_currency_score,
    compute_upskilling_pattern,
)
from backend.models.candidate import BehavioralSignals


class TestCareerMomentum:
    def test_empty_history_returns_neutral(self):
        assert compute_career_momentum([]) == 50

    def test_single_role_returns_neutral(self, sample_work_history):
        assert compute_career_momentum([sample_work_history[0]]) == 50

    def test_progressing_career_scores_high(self, sample_work_history):
        score = compute_career_momentum(sample_work_history, current_year=2026)
        assert score > 50

    def test_stagnant_career_scores_lower_than_progressing(self):
        stagnant = [
            WorkHistory(
                title="Engineer", company="X", start_date="2018-01", end_date="2020-01",
                duration_months=24, level_inferred=RoleLevel.MID,
            ),
            WorkHistory(
                title="Engineer", company="Y", start_date="2020-02", end_date="2026-01",
                duration_months=70, level_inferred=RoleLevel.MID,
            ),
        ]
        progressing = [
            WorkHistory(
                title="Engineer", company="X", start_date="2018-01", end_date="2020-01",
                duration_months=24, level_inferred=RoleLevel.JUNIOR,
            ),
            WorkHistory(
                title="Director", company="Y", start_date="2020-02", end_date="2026-01",
                duration_months=70, level_inferred=RoleLevel.DIRECTOR,
            ),
        ]
        stagnant_score = compute_career_momentum(stagnant, current_year=2026)
        progressing_score = compute_career_momentum(progressing, current_year=2026)
        assert progressing_score > stagnant_score

    def test_score_within_bounds(self, sample_work_history):
        score = compute_career_momentum(sample_work_history, current_year=2026)
        assert 0 <= score <= 100


class TestLearningVelocity:
    def test_no_skills_returns_low_score(self, sample_work_history):
        score = compute_learning_velocity([], [], sample_work_history, current_year=2026)
        assert score == 0

    def test_diverse_recent_skills_score_high(self, sample_skills, sample_certifications, sample_work_history):
        score = compute_learning_velocity(
            sample_skills, sample_certifications, sample_work_history, current_year=2026
        )
        assert score > 0
        assert score <= 100

    def test_score_within_bounds(self, sample_skills, sample_certifications, sample_work_history):
        score = compute_learning_velocity(
            sample_skills, sample_certifications, sample_work_history, current_year=2026
        )
        assert 0 <= score <= 100


class TestRoleConsistency:
    def test_insufficient_history_returns_neutral(self):
        assert compute_role_consistency([]) == 70

    def test_consistent_titles_score_higher(self):
        consistent = [
            WorkHistory(title="Software Engineer", company="A", start_date="2018-01",
                       end_date="2020-01", duration_months=24, level_inferred=RoleLevel.MID),
            WorkHistory(title="Software Architect", company="B", start_date="2020-02",
                       end_date="2026-01", duration_months=70, level_inferred=RoleLevel.SENIOR),
        ]
        inconsistent = [
            WorkHistory(title="Software Engineer", company="A", start_date="2018-01",
                       end_date="2020-01", duration_months=24, level_inferred=RoleLevel.MID),
            WorkHistory(title="Sales Manager", company="B", start_date="2020-02",
                       end_date="2026-01", duration_months=70, level_inferred=RoleLevel.SENIOR),
        ]
        consistent_score = compute_role_consistency(consistent)
        inconsistent_score = compute_role_consistency(inconsistent)
        assert consistent_score >= inconsistent_score

    def test_score_within_bounds(self, sample_work_history):
        score = compute_role_consistency(sample_work_history)
        assert 0 <= score <= 100


class TestJobStability:
    def test_empty_history_returns_zero(self):
        assert compute_job_stability([]) == 0

    def test_long_tenures_score_higher_than_short(self):
        long_tenure = [
            WorkHistory(title="Engineer", company="A", start_date="2018-01",
                       end_date="2022-01", duration_months=48, level_inferred=RoleLevel.MID),
        ]
        short_tenure = [
            WorkHistory(title="Engineer", company="A", start_date="2018-01",
                       end_date="2018-04", duration_months=3, level_inferred=RoleLevel.MID),
        ]
        assert compute_job_stability(long_tenure) > compute_job_stability(short_tenure)

    def test_score_within_bounds(self, sample_work_history):
        score = compute_job_stability(sample_work_history)
        assert 0 <= score <= 100


class TestPromotionFrequency:
    def test_no_multi_role_company_returns_neutral(self):
        single_roles = [
            WorkHistory(title="Engineer", company="A", start_date="2018-01",
                       end_date="2020-01", duration_months=24, level_inferred=RoleLevel.MID),
            WorkHistory(title="Senior Engineer", company="B", start_date="2020-02",
                       end_date="2022-01", duration_months=24, level_inferred=RoleLevel.SENIOR),
        ]
        assert compute_promotion_frequency(single_roles) == 40

    def test_internal_promotion_scores_higher(self, sample_work_history):
        score = compute_promotion_frequency(sample_work_history)
        assert score > 40

    def test_score_within_bounds(self, sample_work_history):
        score = compute_promotion_frequency(sample_work_history)
        assert 0 <= score <= 100


class TestUpskillingPattern:
    def test_no_certs_or_skills_returns_low(self, sample_work_history):
        score = compute_upskilling_pattern([], [], sample_work_history, current_year=2026)
        assert score == 0

    def test_certs_and_cross_domain_skills_score_higher(
        self, sample_certifications, sample_skills, sample_work_history
    ):
        score = compute_upskilling_pattern(
            sample_certifications, sample_skills, sample_work_history, current_year=2026
        )
        assert score > 0

    def test_score_within_bounds(self, sample_certifications, sample_skills, sample_work_history):
        score = compute_upskilling_pattern(
            sample_certifications, sample_skills, sample_work_history, current_year=2026
        )
        assert 0 <= score <= 100


class TestBehavioralComposite:
    def test_weighted_average_calculation(self):
        signals = BehavioralSignals(
            career_momentum=80,
            learning_velocity=70,
            role_consistency=60,
            job_stability=90,
            promotion_frequency=50,
            upskilling_pattern=40,
        )
        expected = int(80 * 0.20 + 70 * 0.20 + 60 * 0.15 + 90 * 0.20 + 50 * 0.15 + 40 * 0.10)
        assert compute_behavioral_composite(signals) == expected

    def test_all_zero_signals_return_zero(self):
        signals = BehavioralSignals(
            career_momentum=0, learning_velocity=0, role_consistency=0,
            job_stability=0, promotion_frequency=0, upskilling_pattern=0,
        )
        assert compute_behavioral_composite(signals) == 0

    def test_all_max_signals_return_max(self):
        signals = BehavioralSignals(
            career_momentum=100, learning_velocity=100, role_consistency=100,
            job_stability=100, promotion_frequency=100, upskilling_pattern=100,
        )
        assert compute_behavioral_composite(signals) == 100


class TestCareerTrajectoryBiasFree:
    def test_no_company_name_parameter_exists(self):
        """Critical bias-prevention test: function signature must not accept company data."""
        import inspect
        sig = inspect.signature(compute_career_trajectory)
        params = list(sig.parameters.keys())
        assert "company" not in params
        assert "company_name" not in params
        assert "prestige" not in params

    def test_identical_career_different_company_names_score_equal(self):
        """Bias check: same career shape at a famous vs unknown company must score identically."""
        famous_company_history = [
            WorkHistory(title="Engineer", company="Google", start_date="2018-01",
                       end_date="2020-01", duration_months=24, level_inferred=RoleLevel.JUNIOR),
            WorkHistory(title="Senior Engineer", company="Google", start_date="2020-02",
                       end_date="2024-01", duration_months=47, level_inferred=RoleLevel.SENIOR),
        ]
        unknown_company_history = [
            WorkHistory(title="Engineer", company="Regional Logistics LLC", start_date="2018-01",
                       end_date="2020-01", duration_months=24, level_inferred=RoleLevel.JUNIOR),
            WorkHistory(title="Senior Engineer", company="Regional Logistics LLC", start_date="2020-02",
                       end_date="2024-01", duration_months=47, level_inferred=RoleLevel.SENIOR),
        ]
        famous_score = compute_career_trajectory(famous_company_history)
        unknown_score = compute_career_trajectory(unknown_company_history)
        assert famous_score == unknown_score

    def test_empty_history_returns_zero(self):
        assert compute_career_trajectory([]) == 0

    def test_score_within_bounds(self, sample_work_history):
        score = compute_career_trajectory(sample_work_history)
        assert 0 <= score <= 100


class TestSkillsCurrencyScore:
    def test_no_required_skills_returns_neutral(self, sample_skills):
        assert compute_skills_currency_score(sample_skills, [], current_year=2026) == 50

    def test_no_skills_returns_zero(self):
        assert compute_skills_currency_score([], ["Python"], current_year=2026) == 0

    def test_matching_skills_score_higher_than_no_match(self, sample_skills):
        matching = compute_skills_currency_score(sample_skills, ["Python", "AWS"], current_year=2026)
        non_matching = compute_skills_currency_score(sample_skills, ["COBOL", "Fortran"], current_year=2026)
        assert matching > non_matching

    def test_score_within_bounds(self, sample_skills):
        score = compute_skills_currency_score(sample_skills, ["Python"], current_year=2026)
        assert 0 <= score <= 100


class TestComputeAllSignals:
    def test_returns_complete_signals_object(self, sample_profile):
        signals = compute_all_signals(sample_profile, required_skills=["Python", "AWS"])
        assert signals.behavioral.career_momentum >= 0
        assert signals.behavioral.behavioral_composite >= 0
        assert signals.career.career_trajectory >= 0
        assert signals.skills_currency_score >= 0

    def test_all_scores_within_bounds(self, sample_profile):
        signals = compute_all_signals(sample_profile, required_skills=["Python"])
        assert 0 <= signals.behavioral.career_momentum <= 100
        assert 0 <= signals.behavioral.learning_velocity <= 100
        assert 0 <= signals.behavioral.role_consistency <= 100
        assert 0 <= signals.behavioral.job_stability <= 100
        assert 0 <= signals.behavioral.promotion_frequency <= 100
        assert 0 <= signals.behavioral.upskilling_pattern <= 100
        assert 0 <= signals.behavioral.behavioral_composite <= 100
        assert 0 <= signals.career.career_trajectory <= 100
        assert 0 <= signals.skills_currency_score <= 100
