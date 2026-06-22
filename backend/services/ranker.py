from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from backend.models.candidate import Candidate
from backend.models.ranking import (
    BehavioralBreakdown,
    Confidence,
    RankedCandidate,
    RankingResult,
    RankingStatus,
    RankingWeights,
    ScoreBreakdown,
)
from backend.models.session import JDRequirements, Session
from backend.repositories.candidates import CandidateRepository
from backend.repositories.vectors import VectorRepository
from backend.services.bedrock import BedrockClient
from backend.services.traits_matcher import TraitsMatcherService

logger = structlog.get_logger(__name__)

_EXPLAIN_SYSTEM = """You are a senior recruiter writing concise, evidence-grounded candidate assessments.
Cite specific data points from the candidate's profile.
Never use filler like "strong candidate" without backing evidence.
Reference behavioral signals by name when relevant.
Return ONLY valid JSON. No markdown."""

_EXPLAIN_TEMPLATE = """Write a ranking justification for this candidate.

Job Requirements Summary:
Required Skills: {required_skills}
Success Traits: {success_traits}
Role Level: {role_level}

Candidate Profile:
Name: {name}
Current Role: {current_title} at {current_company}
Years Experience: {years_exp}
Top Skills: {top_skills}
Recent Work: {recent_work}
Behavioral Evidence: {behavioral_evidence}

Scores (0-100):
Composite: {composite}/100
Semantic Fit: {semantic}, Skills Match: {skills}, Trajectory: {trajectory}, Behavioral: {behavioral}
Behavioral Detail: Momentum={momentum}, Velocity={velocity}, Consistency={consistency}, Stability={stability}, Promotions={promotions}, Upskilling={upskilling}
Traits Match: {traits_match}/100

Return JSON:
{{
  "explanation": "2-3 sentence plain-English justification with specific evidence from their background",
  "strengths": ["max 3 specific strengths with supporting evidence"],
  "gaps": ["max 2 gaps framed as open questions not disqualifiers"],
  "behavioral_highlights": ["1-2 behavioral signal callouts with specific evidence"],
  "confidence": "HIGH|MEDIUM|LOW"
}}"""


class RankerService:
    def __init__(self) -> None:
        self._bedrock = BedrockClient()
        self._vector_repo = VectorRepository()
        self._candidate_repo = CandidateRepository()
        self._traits_matcher = TraitsMatcherService()

    def run_ranking(
        self,
        session: Session,
        ranking_result: RankingResult,
    ) -> RankingResult:
        jd_req = session.jd_requirements or JDRequirements()

        try:
            jd_embedding = self._vector_repo.get_jd_embedding(session.session_id)
        except Exception as exc:
            logger.error("jd_embedding_fetch_failed", session_id=session.session_id, error=str(exc))
            ranking_result.status = RankingStatus.FAILED
            ranking_result.error_message = f"Could not retrieve JD embedding: {exc}"
            return ranking_result

        knn_results = self._vector_repo.knn_search(
            session_id=session.session_id,
            jd_embedding=jd_embedding,
            k=min(50, session.candidate_count + 10),
        )
        if not knn_results:
            ranking_result.status = RankingStatus.FAILED
            ranking_result.error_message = "No candidates found in vector index"
            return ranking_result

        cosine_map: dict[str, float] = {r["candidate_id"]: r["cosine_score"] for r in knn_results}

        candidate_ids = list(cosine_map.keys())
        candidates: list[Candidate] = []
        for cid in candidate_ids:
            try:
                c = self._candidate_repo.get(session.session_id, cid)
                if c.signals and c.profile:
                    candidates.append(c)
            except Exception as exc:
                logger.warning("candidate_fetch_skipped", candidate_id=cid, error=str(exc))

        if not candidates:
            ranking_result.status = RankingStatus.FAILED
            ranking_result.error_message = "No scored candidates available"
            return ranking_result

        traits_results = self._traits_matcher.match_batch(candidates, jd_req)

        scored: list[tuple[Candidate, float, ScoreBreakdown, float]] = []
        for candidate in candidates:
            if not candidate.signals or not candidate.profile:
                continue

            cosine = cosine_map.get(candidate.candidate_id, 0.5)
            semantic_raw = min(100.0, cosine * 100)
            traits_score = float(
                traits_results.get(candidate.candidate_id, None)
                and traits_results[candidate.candidate_id].traits_match_score
                or 50
            )
            semantic_fit = semantic_raw * 0.70 + traits_score * 0.30

            skills_match = float(candidate.signals.skills_currency_score)
            trajectory = float(candidate.signals.career.career_trajectory)
            behavioral = float(candidate.signals.behavioral.behavioral_composite)

            w = ranking_result.weights
            composite = (
                semantic_fit * w.semantic
                + skills_match * w.skills
                + trajectory * w.trajectory
                + behavioral * w.behavioral
            )

            breakdown = ScoreBreakdown(
                semantic_fit=round(semantic_fit, 1),
                skills_match=round(skills_match, 1),
                trajectory=round(trajectory, 1),
                behavioral=round(behavioral, 1),
            )
            scored.append((candidate, composite, breakdown, traits_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored[: ranking_result.top_n]

        explanations = self._generate_explanations_batch(top_candidates, jd_req, traits_results)

        ranked: list[RankedCandidate] = []
        for rank_idx, (candidate, composite, breakdown, traits_score) in enumerate(
            top_candidates, start=1
        ):
            exp_data = explanations.get(candidate.candidate_id, {})
            sig = candidate.signals
            beh = sig.behavioral if sig else None

            traits_result = traits_results.get(candidate.candidate_id)

            self._candidate_repo.update_traits_match(
                session.session_id,
                candidate.candidate_id,
                int(traits_score),
                [
                    tb.model_dump()
                    for tb in (traits_result.traits_breakdown if traits_result else [])
                ],
            )

            ranked.append(
                RankedCandidate(
                    rank=rank_idx,
                    candidate_id=candidate.candidate_id,
                    full_name=candidate.profile.full_name if candidate.profile else "",
                    current_title=candidate.profile.current_title if candidate.profile else "",
                    current_company=candidate.profile.current_company if candidate.profile else "",
                    composite_score=round(composite, 1),
                    score_breakdown=breakdown,
                    behavioral_breakdown=BehavioralBreakdown(
                        career_momentum=beh.career_momentum if beh else 0,
                        learning_velocity=beh.learning_velocity if beh else 0,
                        role_consistency=beh.role_consistency if beh else 0,
                        job_stability=beh.job_stability if beh else 0,
                        promotion_frequency=beh.promotion_frequency if beh else 0,
                        upskilling_pattern=beh.upskilling_pattern if beh else 0,
                    ),
                    traits_match_score=round(traits_score, 1),
                    explanation=exp_data.get("explanation", ""),
                    strengths=exp_data.get("strengths", [])[:3],
                    gaps=exp_data.get("gaps", [])[:2],
                    behavioral_highlights=exp_data.get("behavioral_highlights", [])[:2],
                    confidence=self._determine_confidence(composite),
                )
            )

        ranking_result.ranked_candidates = ranked
        ranking_result.status = RankingStatus.COMPLETE
        ranking_result.completed_at = datetime.now(timezone.utc).isoformat()
        return ranking_result

    def _generate_explanations_batch(
        self,
        top_candidates: list[tuple[Candidate, float, ScoreBreakdown, float]],
        jd_req: JDRequirements,
        traits_results: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for candidate, composite, breakdown, traits_score in top_candidates:
            try:
                exp = self._generate_single_explanation(
                    candidate, composite, breakdown, traits_score, jd_req
                )
                results[candidate.candidate_id] = exp
            except Exception as exc:
                logger.warning(
                    "explanation_failed",
                    candidate_id=candidate.candidate_id,
                    error=str(exc),
                )
                results[candidate.candidate_id] = {
                    "explanation": f"{candidate.profile.full_name if candidate.profile else 'Candidate'} shows relevant experience for this role.",
                    "strengths": [],
                    "gaps": [],
                    "behavioral_highlights": [],
                    "confidence": "MEDIUM",
                }
        return results

    def _generate_single_explanation(
        self,
        candidate: Candidate,
        composite: float,
        breakdown: ScoreBreakdown,
        traits_score: float,
        jd_req: JDRequirements,
    ) -> dict[str, Any]:
        if not candidate.profile or not candidate.signals:
            return {
                "explanation": "Insufficient profile data.",
                "strengths": [],
                "gaps": [],
                "behavioral_highlights": [],
                "confidence": "LOW",
            }

        p = candidate.profile
        sig = candidate.signals
        beh = sig.behavioral

        top_skills = ", ".join(s.name for s in p.skills[:8])
        recent_work = "; ".join(
            f"{w.title} at {w.company} ({w.duration_months}mo)" for w in p.work_history[:3]
        )

        prompt = _EXPLAIN_TEMPLATE.format(
            required_skills=", ".join(jd_req.required_skills[:8]),
            success_traits=", ".join(jd_req.success_traits[:5]),
            role_level=jd_req.role_level,
            name=p.full_name,
            current_title=p.current_title,
            current_company=p.current_company,
            years_exp=p.years_experience,
            top_skills=top_skills,
            recent_work=recent_work,
            behavioral_evidence="; ".join(p.raw_behavioral_evidence[:4]),
            composite=round(composite, 1),
            semantic=breakdown.semantic_fit,
            skills=breakdown.skills_match,
            trajectory=breakdown.trajectory,
            behavioral=breakdown.behavioral,
            momentum=beh.career_momentum,
            velocity=beh.learning_velocity,
            consistency=beh.role_consistency,
            stability=beh.job_stability,
            promotions=beh.promotion_frequency,
            upskilling=beh.upskilling_pattern,
            traits_match=round(traits_score, 1),
        )

        return self._bedrock.invoke_claude_json(
            user_prompt=prompt,
            system_prompt=_EXPLAIN_SYSTEM,
            max_tokens=800,
        )

    @staticmethod
    def _determine_confidence(composite_score: float) -> Confidence:
        if composite_score >= 70:
            return Confidence.HIGH
        if composite_score >= 45:
            return Confidence.MEDIUM
        return Confidence.LOW

    def rerank_fast(
        self,
        session: Session,
        weights: RankingWeights,
        top_n: int,
        existing_result: RankingResult,
    ) -> RankingResult:
        """Re-rank using cached scores — no Bedrock calls for embeddings/signals."""
        jd_req = session.jd_requirements or JDRequirements()
        existing_ranked = existing_result.ranked_candidates

        if not existing_ranked:
            return self.run_ranking(session, existing_result)

        all_candidates: list[Candidate] = []
        for rc in existing_ranked:
            try:
                c = self._candidate_repo.get(session.session_id, rc.candidate_id)
                if c.signals and c.profile:
                    all_candidates.append(c)
            except Exception:
                continue

        jd_embedding = self._vector_repo.get_jd_embedding(session.session_id)
        knn_results = self._vector_repo.knn_search(
            session_id=session.session_id,
            jd_embedding=jd_embedding,
            k=50,
        )
        cosine_map: dict[str, float] = {r["candidate_id"]: r["cosine_score"] for r in knn_results}

        scored: list[tuple[Candidate, float, ScoreBreakdown, float]] = []
        for candidate in all_candidates:
            if not candidate.signals or not candidate.profile:
                continue
            cosine = cosine_map.get(candidate.candidate_id, 0.5)
            semantic_raw = min(100.0, cosine * 100)

            traits_score = 50.0
            if candidate.signals.traits_match:
                traits_score = float(candidate.signals.traits_match.traits_match_score)

            semantic_fit = semantic_raw * 0.70 + traits_score * 0.30
            skills_match = float(candidate.signals.skills_currency_score)
            trajectory = float(candidate.signals.career.career_trajectory)
            behavioral = float(candidate.signals.behavioral.behavioral_composite)

            composite = (
                semantic_fit * weights.semantic
                + skills_match * weights.skills
                + trajectory * weights.trajectory
                + behavioral * weights.behavioral
            )
            breakdown = ScoreBreakdown(
                semantic_fit=round(semantic_fit, 1),
                skills_match=round(skills_match, 1),
                trajectory=round(trajectory, 1),
                behavioral=round(behavioral, 1),
            )
            scored.append((candidate, composite, breakdown, traits_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_n]

        prev_top10 = {rc.candidate_id for rc in existing_ranked[:10]}
        new_top10 = {c.candidate_id for c, *_ in top[:10]}
        need_new_explanations = prev_top10 != new_top10

        if need_new_explanations:
            dummy_traits: dict[str, Any] = {}
            for c in all_candidates:
                if c.signals and c.signals.traits_match:
                    dummy_traits[c.candidate_id] = c.signals.traits_match
            explanations = self._generate_explanations_batch(top, jd_req, dummy_traits)
        else:
            explanations = {
                rc.candidate_id: {
                    "explanation": rc.explanation,
                    "strengths": rc.strengths,
                    "gaps": rc.gaps,
                    "behavioral_highlights": rc.behavioral_highlights,
                }
                for rc in existing_ranked
            }

        ranked: list[RankedCandidate] = []
        for rank_idx, (candidate, composite, breakdown, traits_score) in enumerate(top, start=1):
            exp_data = explanations.get(candidate.candidate_id, {})
            sig = candidate.signals
            beh = sig.behavioral if sig else None
            ranked.append(
                RankedCandidate(
                    rank=rank_idx,
                    candidate_id=candidate.candidate_id,
                    full_name=candidate.profile.full_name if candidate.profile else "",
                    current_title=candidate.profile.current_title if candidate.profile else "",
                    current_company=candidate.profile.current_company if candidate.profile else "",
                    composite_score=round(composite, 1),
                    score_breakdown=breakdown,
                    behavioral_breakdown=BehavioralBreakdown(
                        career_momentum=beh.career_momentum if beh else 0,
                        learning_velocity=beh.learning_velocity if beh else 0,
                        role_consistency=beh.role_consistency if beh else 0,
                        job_stability=beh.job_stability if beh else 0,
                        promotion_frequency=beh.promotion_frequency if beh else 0,
                        upskilling_pattern=beh.upskilling_pattern if beh else 0,
                    ),
                    traits_match_score=round(traits_score, 1),
                    explanation=exp_data.get("explanation", ""),
                    strengths=exp_data.get("strengths", [])[:3],
                    gaps=exp_data.get("gaps", [])[:2],
                    behavioral_highlights=exp_data.get("behavioral_highlights", [])[:2],
                    confidence=self._determine_confidence(composite),
                )
            )

        existing_result.ranked_candidates = ranked
        existing_result.weights = weights
        existing_result.top_n = top_n
        existing_result.status = RankingStatus.COMPLETE
        existing_result.completed_at = datetime.now(timezone.utc).isoformat()
        return existing_result
