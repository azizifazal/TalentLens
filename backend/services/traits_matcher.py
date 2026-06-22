from __future__ import annotations

import json
from typing import Any

import structlog

from backend.models.candidate import (
    Candidate,
    TraitBreakdown,
    TraitMatchLevel,
    TraitsMatchResult,
)
from backend.models.session import JDRequirements
from backend.services.bedrock import BedrockClient

logger = structlog.get_logger(__name__)

_TRAITS_SYSTEM = """You are a behavioral assessment expert.
Match job description success traits against candidate behavioral evidence.
Be precise and evidence-grounded.
Return ONLY valid JSON. Do not add markdown or commentary."""

_BATCH_TRAITS_TEMPLATE = """Match the JD success traits against each candidate's behavioral evidence.

JD Success Traits: {traits}
JD Behavioral Expectations: {expectations}

For each candidate, evaluate their evidence against every trait.

Candidates:
{candidates_json}

Return a JSON array (one object per candidate) in this exact format:
[
  {{
    "candidate_id": "string",
    "traits_match_score": number (0-100),
    "traits_breakdown": [
      {{
        "trait": "string",
        "evidence": "specific quote or paraphrase from candidate history, or empty string",
        "match_level": "STRONG|PARTIAL|ABSENT|CONTRADICTED"
      }}
    ]
  }}
]"""

_SINGLE_TRAITS_TEMPLATE = """Match these JD success traits against this candidate's behavioral evidence.

JD Success Traits: {traits}
JD Behavioral Expectations: {expectations}
Candidate Behavioral Evidence: {evidence}
Candidate Work History Summary: {work_summary}

Return JSON:
{{
  "traits_match_score": number (0-100),
  "traits_breakdown": [
    {{
      "trait": "string",
      "evidence": "specific quote or paraphrase, or empty string if absent",
      "match_level": "STRONG|PARTIAL|ABSENT|CONTRADICTED"
    }}
  ]
}}"""


class TraitsMatcherService:
    def __init__(self) -> None:
        self._bedrock = BedrockClient()

    def match_batch(
        self,
        candidates: list[Candidate],
        jd_requirements: JDRequirements,
    ) -> dict[str, TraitsMatchResult]:
        if not jd_requirements.success_traits and not jd_requirements.behavioral_expectations:
            return {c.candidate_id: TraitsMatchResult(traits_match_score=50) for c in candidates}

        if not candidates:
            return {}

        candidates_data: list[dict[str, Any]] = []
        for c in candidates:
            if not c.profile:
                continue
            work_summary = "; ".join(
                f"{w.title} at {w.company} ({w.duration_months}mo)"
                for w in c.profile.work_history[:5]
            )
            candidates_data.append(
                {
                    "candidate_id": c.candidate_id,
                    "behavioral_evidence": c.profile.raw_behavioral_evidence[:6],
                    "work_summary": work_summary,
                }
            )

        if not candidates_data:
            return {c.candidate_id: TraitsMatchResult(traits_match_score=50) for c in candidates}

        prompt = _BATCH_TRAITS_TEMPLATE.format(
            traits=json.dumps(jd_requirements.success_traits),
            expectations=json.dumps(jd_requirements.behavioral_expectations),
            candidates_json=json.dumps(candidates_data, indent=2),
        )

        try:
            raw_list = self._bedrock.invoke_claude_json_list(
                user_prompt=prompt,
                system_prompt=_TRAITS_SYSTEM,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.error("batch_traits_match_failed", error=str(exc))
            return {c.candidate_id: TraitsMatchResult(traits_match_score=50) for c in candidates}

        results: dict[str, TraitsMatchResult] = {}
        for item in raw_list:
            candidate_id = item.get("candidate_id", "")
            if not candidate_id:
                continue
            score = int(item.get("traits_match_score", 50))
            breakdown: list[TraitBreakdown] = []
            for tb in item.get("traits_breakdown", []):
                try:
                    breakdown.append(
                        TraitBreakdown(
                            trait=str(tb.get("trait", "")),
                            evidence=str(tb.get("evidence", "")),
                            match_level=TraitMatchLevel(
                                tb.get("match_level", TraitMatchLevel.ABSENT)
                            ),
                        )
                    )
                except Exception:
                    continue
            results[candidate_id] = TraitsMatchResult(
                traits_match_score=max(0, min(100, score)),
                traits_breakdown=breakdown,
            )

        for c in candidates:
            if c.candidate_id not in results:
                results[c.candidate_id] = TraitsMatchResult(traits_match_score=50)

        return results

    def match_single(
        self,
        candidate: Candidate,
        jd_requirements: JDRequirements,
    ) -> TraitsMatchResult:
        if not jd_requirements.success_traits and not jd_requirements.behavioral_expectations:
            return TraitsMatchResult(traits_match_score=50)
        if not candidate.profile:
            return TraitsMatchResult(traits_match_score=50)

        work_summary = "; ".join(
            f"{w.title} at {w.company} ({w.duration_months}mo)"
            for w in candidate.profile.work_history[:5]
        )

        prompt = _SINGLE_TRAITS_TEMPLATE.format(
            traits=json.dumps(jd_requirements.success_traits),
            expectations=json.dumps(jd_requirements.behavioral_expectations),
            evidence=json.dumps(candidate.profile.raw_behavioral_evidence[:6]),
            work_summary=work_summary,
        )

        try:
            raw = self._bedrock.invoke_claude_json(
                user_prompt=prompt,
                system_prompt=_TRAITS_SYSTEM,
                max_tokens=1500,
            )
            score = int(raw.get("traits_match_score", 50))
            breakdown: list[TraitBreakdown] = []
            for tb in raw.get("traits_breakdown", []):
                try:
                    breakdown.append(
                        TraitBreakdown(
                            trait=str(tb.get("trait", "")),
                            evidence=str(tb.get("evidence", "")),
                            match_level=TraitMatchLevel(
                                tb.get("match_level", TraitMatchLevel.ABSENT)
                            ),
                        )
                    )
                except Exception:
                    continue
            return TraitsMatchResult(
                traits_match_score=max(0, min(100, score)),
                traits_breakdown=breakdown,
            )
        except Exception as exc:
            logger.error("single_traits_match_failed", error=str(exc))
            return TraitsMatchResult(traits_match_score=50)
