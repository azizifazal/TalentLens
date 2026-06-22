export type RankingStatus = "PROCESSING" | "COMPLETE" | "FAILED";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";

export interface RankingWeights {
  semantic: number;
  skills: number;
  trajectory: number;
  behavioral: number;
}

export interface ScoreBreakdown {
  semantic_fit: number;
  skills_match: number;
  trajectory: number;
  behavioral: number;
}

export interface BehavioralBreakdown {
  career_momentum: number;
  learning_velocity: number;
  role_consistency: number;
  job_stability: number;
  promotion_frequency: number;
  upskilling_pattern: number;
}

export interface RankedCandidate {
  rank: number;
  candidate_id: string;
  full_name: string;
  current_title: string;
  current_company: string;
  composite_score: number;
  score_breakdown: ScoreBreakdown;
  behavioral_breakdown: BehavioralBreakdown;
  traits_match_score: number;
  explanation: string;
  strengths: string[];
  gaps: string[];
  behavioral_highlights: string[];
  confidence: Confidence;
}

export interface RankingResult {
  ranking_job_id: string;
  session_id: string;
  status: RankingStatus;
  weights: RankingWeights;
  top_n: number;
  ranked_candidates: RankedCandidate[];
  created_at: string;
  completed_at: string | null;
  expires_at: number;
  error_message: string | null;
}

export interface RankResponse {
  ranking_job_id: string;
  status: RankingStatus;
  message: string;
}

export const DEFAULT_WEIGHTS: RankingWeights = {
  semantic: 0.3,
  skills: 0.25,
  trajectory: 0.25,
  behavioral: 0.2,
};
