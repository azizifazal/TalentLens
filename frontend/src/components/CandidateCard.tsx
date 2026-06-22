import ScoreBar from "@/components/ScoreBar";
import ScoreRing from "@/components/ScoreRing";
import type { RankedCandidate } from "@/types/ranking";

interface CandidateCardProps {
  candidate: RankedCandidate;
  onClick: () => void;
}

const CONFIDENCE_STYLES: Record<string, string> = {
  HIGH: "text-success",
  MEDIUM: "text-accent-warm",
  LOW: "text-muted",
};

export default function CandidateCard({ candidate, onClick }: CandidateCardProps) {
  return (
    <button
      onClick={onClick}
      className="card w-full text-left p-5 hover:bg-surface-raised hover:shadow-lg transition-all duration-200 group"
    >
      <div className="flex gap-4">
        <div className="flex flex-col items-center gap-1 shrink-0">
          <span className="font-mono text-xs text-muted">#{candidate.rank}</span>
          <ScoreRing score={candidate.composite_score} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="font-display font-semibold text-text-primary truncate">
                {candidate.full_name || "Unnamed Candidate"}
              </h3>
              <p className="text-sm text-text-secondary truncate">
                {candidate.current_title}
                {candidate.current_company && ` @ ${candidate.current_company}`}
              </p>
            </div>
            <span
              className={`text-xs font-mono font-semibold shrink-0 ${
                CONFIDENCE_STYLES[candidate.confidence] || "text-muted"
              }`}
            >
              {candidate.confidence}
            </span>
          </div>

          <div className="mt-3 space-y-1.5">
            <ScoreBar
              label="Semantic"
              value={candidate.score_breakdown.semantic_fit}
              color="#6C63FF"
            />
            <ScoreBar
              label="Skills"
              value={candidate.score_breakdown.skills_match}
              color="#FF9F43"
            />
            <ScoreBar
              label="Trajectory"
              value={candidate.score_breakdown.trajectory}
              color="#2ECC71"
            />
            <ScoreBar
              label="Behavioral"
              value={candidate.score_breakdown.behavioral}
              color="#38BDF8"
            />
          </div>

          {candidate.explanation && (
            <p className="mt-3 text-sm text-text-secondary leading-relaxed line-clamp-3">
              {candidate.explanation}
            </p>
          )}

          {(candidate.strengths.length > 0 || candidate.gaps.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {candidate.strengths.slice(0, 3).map((s, i) => (
                <span
                  key={`strength-${i}`}
                  className="tag-chip bg-success/10 text-success text-[11px]"
                >
                  ✓ {s}
                </span>
              ))}
              {candidate.gaps.slice(0, 2).map((g, i) => (
                <span
                  key={`gap-${i}`}
                  className="tag-chip bg-accent-warm/10 text-accent-warm text-[11px]"
                >
                  △ {g}
                </span>
              ))}
            </div>
          )}

          {candidate.behavioral_highlights.length > 0 && (
            <div className="mt-2 flex items-center gap-1.5 text-[11px] text-behavioral">
              <span>⚡</span>
              <span className="truncate">
                {candidate.behavioral_highlights.join(" · ")}
              </span>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
