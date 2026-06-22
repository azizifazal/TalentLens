export type SessionStatus = "CREATED" | "JD_ANALYZED" | "INGESTING" | "RANKED";

export interface JDRequirements {
  required_skills: string[];
  preferred_skills: string[];
  experience_min: number;
  experience_max: number;
  role_level: string;
  industry_context: string;
  education: string[];
  success_traits: string[];
  behavioral_expectations: string[];
  red_flags: string[];
}

export interface SessionSummary {
  session_id: string;
  job_title: string;
  status: SessionStatus;
  candidate_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateSessionResponse {
  session_id: string;
  job_title: string;
  status: SessionStatus;
  created_at: string;
}

export interface AnalyzeJDResponse {
  session_id: string;
  jd_requirements: JDRequirements;
  status: SessionStatus;
}
