from __future__ import annotations

from datetime import datetime

import structlog

from backend.models.candidate import (
    BehavioralSignals,
    CandidateProfile,
    CandidateSignals,
    CareerSignals,
    Certification,
    RoleLevel,
    Skill,
    WorkHistory,
)

logger = structlog.get_logger(__name__)

_LEVEL_MAP: dict[str, int] = {
    RoleLevel.JUNIOR: 1,
    RoleLevel.MID: 2,
    RoleLevel.SENIOR: 3,
    RoleLevel.LEAD: 4,
    RoleLevel.PRINCIPAL: 5,
    RoleLevel.MANAGER: 4,
    RoleLevel.DIRECTOR: 6,
}


def _current_year() -> int:
    return datetime.now().year


def _safe_clamp(value: int | float) -> int:
    return max(0, min(100, int(value)))


def compute_career_momentum(
    work_history: list[WorkHistory], current_year: int | None = None
) -> int:
    if not current_year:
        current_year = _current_year()
    if len(work_history) < 2:
        return 50

    levels = [_LEVEL_MAP.get(w.level_inferred.value, 2) for w in work_history]
    total_months = sum(w.duration_months for w in work_history if w.duration_months > 0)
    total_years = max(1.0, total_months / 12)

    level_gain = levels[-1] - levels[0]
    gain_rate = (level_gain / total_years) * 5
    trajectory_score = _safe_clamp(gain_rate * 20)

    recent_roles: list[WorkHistory] = []
    for w in work_history:
        try:
            start_year = int(w.start_date[:4])
            if current_year - start_year <= 2:
                recent_roles.append(w)
        except (ValueError, IndexError):
            continue

    if recent_roles:
        recent_levels = [_LEVEL_MAP.get(w.level_inferred.value, 2) for w in recent_roles]
        prev_levels = [
            _LEVEL_MAP.get(w.level_inferred.value, 2) for w in work_history if w not in recent_roles
        ]
        recent_max = max(recent_levels)
        prev_max = max(prev_levels) if prev_levels else 0
        recency_bonus = 35 if recent_max > prev_max else 15
    else:
        recency_bonus = 10

    if len(levels) >= 2:
        sorted_levels = sorted(levels)
        median_level = sorted_levels[len(sorted_levels) // 2]
        direction_score = 25 if levels[-1] >= median_level else 5
    else:
        direction_score = 15

    return _safe_clamp(trajectory_score + recency_bonus + direction_score)


def compute_learning_velocity(
    skills: list[Skill],
    certifications: list[Certification],
    work_history: list[WorkHistory],
    current_year: int | None = None,
) -> int:
    if not current_year:
        current_year = _current_year()

    total_months = sum(w.duration_months for w in work_history if w.duration_months > 0)
    career_years = max(1.0, total_months / 12)

    categories = {s.category.lower() for s in skills if s.category}
    domain_score = _safe_clamp(len(categories) * 5)

    recent_skills = [s for s in skills if s.last_used_year and current_year - s.last_used_year <= 2]
    recent_score = _safe_clamp(len(recent_skills) * 6)

    cert_rate = len(certifications) / career_years
    cert_score = _safe_clamp(cert_rate * 25)

    expert_count = sum(1 for s in skills if s.depth.value == "EXPERT")
    breadth_score = _safe_clamp(expert_count * 5)

    return _safe_clamp(
        min(30, domain_score) + min(30, recent_score) + min(25, cert_score) + min(15, breadth_score)
    )


def compute_role_consistency(work_history: list[WorkHistory]) -> int:
    if len(work_history) < 2:
        return 70

    titles = [w.title.lower() for w in work_history]
    first_words = [t.split()[0] if t.split() else "" for t in titles]
    unique_first = set(first_words)
    consistency_ratio = 1.0 - (len(unique_first) / max(1, len(first_words)))
    domain_score = _safe_clamp(consistency_ratio * 60)

    level_values = [_LEVEL_MAP.get(w.level_inferred.value, 2) for w in work_history]
    volatile_jumps = 0
    for i in range(1, len(level_values)):
        if abs(level_values[i] - level_values[i - 1]) > 2:
            volatile_jumps += 1
    volatility_penalty = volatile_jumps * 10

    carryover_score = 40

    return _safe_clamp(domain_score + carryover_score - volatility_penalty)


def compute_job_stability(work_history: list[WorkHistory]) -> int:
    if not work_history:
        return 0

    tenures = [w.duration_months for w in work_history if w.duration_months > 0]
    if not tenures:
        return 30

    avg_tenure = sum(tenures) / len(tenures)
    tenure_score = _safe_clamp((avg_tenure - 6) / 18 * 40)

    stable_count = sum(1 for t in tenures if t >= 18)
    stability_pct = stable_count / len(tenures)
    pct_score = _safe_clamp(stability_pct * 30)

    gap_months = 0
    sorted_history = sorted(work_history, key=lambda w: w.start_date)
    for i in range(1, len(sorted_history)):
        prev = sorted_history[i - 1]
        curr = sorted_history[i]
        if prev.end_date:
            try:
                prev_end_parts = prev.end_date.split("-")
                curr_start_parts = curr.start_date.split("-")
                prev_end = int(prev_end_parts[0]) * 12 + int(prev_end_parts[1])
                curr_start = int(curr_start_parts[0]) * 12 + int(curr_start_parts[1])
                gap = curr_start - prev_end
                if gap > 1:
                    gap_months += gap - 1
            except (ValueError, IndexError):
                continue
    gap_penalty = _safe_clamp(gap_months / 6 * 5)

    if len(tenures) >= 4:
        mid = len(tenures) // 2
        early_avg = sum(tenures[:mid]) / mid
        late_avg = sum(tenures[mid:]) / (len(tenures) - mid)
        trend_score = 30 if late_avg >= early_avg else 10
    else:
        trend_score = 15

    return _safe_clamp(tenure_score + pct_score + trend_score - gap_penalty)


def compute_promotion_frequency(work_history: list[WorkHistory]) -> int:
    if len(work_history) < 2:
        return 40

    company_groups: dict[str, list[WorkHistory]] = {}
    for w in work_history:
        key = w.company.lower().strip()
        company_groups.setdefault(key, []).append(w)

    total_promotions = 0
    total_company_years = 0.0

    for roles in company_groups.values():
        if len(roles) < 2:
            continue
        sorted_roles = sorted(roles, key=lambda r: r.start_date)
        role_levels = [_LEVEL_MAP.get(r.level_inferred.value, 2) for r in sorted_roles]
        promotions = sum(
            1 for i in range(1, len(role_levels)) if role_levels[i] > role_levels[i - 1]
        )
        total_promotions += promotions
        company_months = sum(r.duration_months for r in roles if r.duration_months > 0)
        total_company_years += company_months / 12

    if total_company_years < 0.5:
        return 40

    if total_promotions == 0:
        return 25

    # Benchmark: one promotion every 3 years of tenure at a single company
    # is considered strong progression and approaches the top of the range.
    promo_rate = total_promotions / total_company_years
    score = 40 + min(60.0, promo_rate * 3 * 60)
    return _safe_clamp(score)


def compute_upskilling_pattern(
    certifications: list[Certification],
    skills: list[Skill],
    work_history: list[WorkHistory],
    current_year: int | None = None,
) -> int:
    if not current_year:
        current_year = _current_year()

    recent_certs = [c for c in certifications if current_year - c.year <= 3]
    cert_score = _safe_clamp(len(certifications) * 8 + len(recent_certs) * 5)

    work_title_words = set()
    for w in work_history:
        work_title_words.update(w.title.lower().split())
    cross_domain_skills = [
        s
        for s in skills
        if s.category and not any(word in s.category.lower() for word in work_title_words)
    ]
    cross_score = _safe_clamp(len(cross_domain_skills) * 7)

    recent_added = [
        s
        for s in skills
        if s.last_used_year
        and current_year - s.last_used_year <= 2
        and s.depth.value in ("PRACTICED", "EXPERT")
    ]
    recency_score = _safe_clamp(len(recent_added) * 5)

    return _safe_clamp(min(40, cert_score) + min(35, cross_score) + min(25, recency_score))


def compute_behavioral_composite(signals: BehavioralSignals) -> int:
    return _safe_clamp(
        signals.career_momentum * 0.20
        + signals.learning_velocity * 0.20
        + signals.role_consistency * 0.15
        + signals.job_stability * 0.20
        + signals.promotion_frequency * 0.15
        + signals.upskilling_pattern * 0.10
    )


def compute_career_trajectory(work_history: list[WorkHistory]) -> int:
    """Bias-free trajectory: company name is never used."""
    if not work_history:
        return 0

    levels = [_LEVEL_MAP.get(w.level_inferred.value, 2) for w in work_history]
    tenures = [w.duration_months for w in work_history if w.duration_months > 0]
    avg_tenure = sum(tenures) / len(tenures) if tenures else 0

    tenure_score = _safe_clamp((avg_tenure - 6) / 18 * 35)
    level_delta = levels[-1] - levels[0] if len(levels) >= 2 else 0
    progression_score = _safe_clamp(level_delta / 3 * 40)

    max_level = max(levels)
    recent_has_max = any(
        _LEVEL_MAP.get(w.level_inferred.value, 0) >= max_level for w in work_history[-2:]
    )
    recency_score = 25 if recent_has_max else 10

    gap_months = 0
    sorted_wh = sorted(work_history, key=lambda w: w.start_date)
    for i in range(1, len(sorted_wh)):
        prev = sorted_wh[i - 1]
        curr = sorted_wh[i]
        if prev.end_date:
            try:
                pe = prev.end_date.split("-")
                cs = curr.start_date.split("-")
                prev_months = int(pe[0]) * 12 + int(pe[1])
                curr_months = int(cs[0]) * 12 + int(cs[1])
                gap = curr_months - prev_months
                if gap > 1:
                    gap_months += gap - 1
            except (ValueError, IndexError):
                continue
    gap_penalty = _safe_clamp(gap_months / 6 * 5)

    return _safe_clamp(tenure_score + progression_score + recency_score - gap_penalty)


def compute_skills_currency_score(
    skills: list[Skill],
    required_skills: list[str],
    current_year: int | None = None,
) -> int:
    if not current_year:
        current_year = _current_year()
    if not required_skills:
        return 50
    if not skills:
        return 0

    try:
        from rapidfuzz import fuzz
    except ImportError:

        def fuzz_ratio(a: str, b: str) -> float:  # type: ignore
            return 80.0 if a.lower() in b.lower() or b.lower() in a.lower() else 0.0

        class fuzz:  # type: ignore
            @staticmethod
            def partial_ratio(a: str, b: str) -> float:
                return fuzz_ratio(a, b)

    match_scores: list[float] = []
    for req in required_skills:
        best_match_score = 0.0
        for skill in skills:
            similarity = fuzz.partial_ratio(req.lower(), skill.name.lower())
            if similarity >= 75:
                years_ago = current_year - (skill.last_used_year or current_year - 5)
                recency = max(0.0, 60.0 - years_ago * 15)
                depth_map = {"AWARE": 10, "PRACTICED": 25, "EXPERT": 40}
                depth = depth_map.get(skill.depth.value, 10)
                candidate_score = recency + depth
                best_match_score = max(best_match_score, candidate_score)
        match_scores.append(best_match_score)

    if not match_scores:
        return 0
    raw_avg = sum(match_scores) / len(match_scores)
    return _safe_clamp(raw_avg / 100 * 100)


def compute_all_signals(
    profile: CandidateProfile,
    required_skills: list[str] | None = None,
) -> CandidateSignals:
    year = _current_year()
    wh = profile.work_history
    skills = profile.skills
    certs = profile.certifications

    momentum = compute_career_momentum(wh, year)
    velocity = compute_learning_velocity(skills, certs, wh, year)
    consistency = compute_role_consistency(wh)
    stability = compute_job_stability(wh)
    promotion = compute_promotion_frequency(wh)
    upskilling = compute_upskilling_pattern(certs, skills, wh, year)

    behavioral = BehavioralSignals(
        career_momentum=momentum,
        learning_velocity=velocity,
        role_consistency=consistency,
        job_stability=stability,
        promotion_frequency=promotion,
        upskilling_pattern=upskilling,
    )
    behavioral.behavioral_composite = compute_behavioral_composite(behavioral)

    trajectory = compute_career_trajectory(wh)
    avg_tenure = (
        sum(w.duration_months for w in wh if w.duration_months > 0) / len(wh) if wh else 0.0
    )

    total_months = sum(w.duration_months for w in wh if w.duration_months > 0)
    levels = [_LEVEL_MAP.get(w.level_inferred.value, 2) for w in wh]
    career_years = max(1.0, total_months / 12)
    level_prog_rate = (levels[-1] - levels[0]) / career_years if len(levels) >= 2 else 0.0

    career_signals = CareerSignals(
        career_trajectory=trajectory,
        avg_tenure_months=round(avg_tenure, 1),
        level_progression_rate=round(level_prog_rate, 2),
        career_gap_months=0,
    )

    skills_score = compute_skills_currency_score(skills, required_skills or [], year)

    return CandidateSignals(
        behavioral=behavioral,
        career=career_signals,
        skills_currency_score=skills_score,
        traits_match=None,
    )
