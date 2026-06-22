export type SkillDepth = "AWARE" | "PRACTICED" | "EXPERT";

export type RoleLevel =
  | "JUNIOR"
  | "MID"
  | "SENIOR"
  | "LEAD"
  | "PRINCIPAL"
  | "MANAGER"
  | "DIRECTOR";

export type ParseStatus =
  | "QUEUED"
  | "PARSING"
  | "COMPUTING_SIGNALS"
  | "READY"
  | "ERROR";

export interface Skill {
  name: string;
  category: string;
  last_used_year: number | null;
  depth: SkillDepth;
}

export interface WorkHistory {
  title: string;
  company: string;
  start_date: string;
  end_date: string | null;
  duration_months: number;
  level_inferred: RoleLevel;
  description_summary: string;
  responsibilities: string[];
}

export interface Education {
  degree: string;
  field: string;
  institution: string;
  graduation_year: number | null;
}

export interface Certification {
  name: string;
  issuer: string;
  year: number;
}

export interface CandidateProfile {
  full_name: string;
  current_title: string;
  current_company: string;
  location: string;
  years_experience: number;
  skills: Skill[];
  work_history: WorkHistory[];
  education: Education[];
  certifications: Certification[];
  raw_behavioral_evidence: string[];
}

export interface BehavioralSignals {
  career_momentum: number;
  learning_velocity: number;
  role_consistency: number;
  job_stability: number;
  promotion_frequency: number;
  upskilling_pattern: number;
  behavioral_composite: number;
}

export interface CareerSignals {
  career_trajectory: number;
  avg_tenure_months: number;
  level_progression_rate: number;
  career_gap_months: number;
}

export type TraitMatchLevel = "STRONG" | "PARTIAL" | "ABSENT" | "CONTRADICTED";

export interface TraitBreakdown {
  trait: string;
  evidence: string;
  match_level: TraitMatchLevel;
}

export interface TraitsMatchResult {
  traits_match_score: number;
  traits_breakdown: TraitBreakdown[];
}

export interface CandidateSignals {
  behavioral: BehavioralSignals;
  career: CareerSignals;
  skills_currency_score: number;
  traits_match: TraitsMatchResult | null;
}

export interface Candidate {
  candidate_id: string;
  session_id: string;
  file_name: string;
  s3_key: string;
  parse_status: ParseStatus;
  parse_error: string | null;
  embedding_id: string | null;
  profile: CandidateProfile | null;
  signals: CandidateSignals | null;
  created_at: string;
  expires_at: number;
}

export interface CandidateListItem {
  candidate_id: string;
  file_name: string;
  parse_status: ParseStatus;
  full_name: string;
  current_title: string;
  current_company: string;
  parse_error: string | null;
}

export interface UploadUrlResponse {
  candidate_id: string;
  upload_url: string;
  s3_key: string;
}
