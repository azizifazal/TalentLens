import type { TraitsMatchResult } from "@/types/candidate";

interface TraitsMatchPanelProps {
  traitsMatch: TraitsMatchResult | null;
}

const MATCH_STYLES: Record<string, { label: string; className: string }> = {
  STRONG: { label: "Strong", className: "bg-success/15 text-success" },
  PARTIAL: { label: "Partial", className: "bg-accent-warm/15 text-accent-warm" },
  ABSENT: { label: "Absent", className: "bg-surface-raised text-muted" },
  CONTRADICTED: { label: "Contradicted", className: "bg-red-500/15 text-red-400" },
};

export default function TraitsMatchPanel({ traitsMatch }: TraitsMatchPanelProps) {
  if (!traitsMatch || traitsMatch.traits_breakdown.length === 0) {
    return (
      <div>
        <h3 className="font-display font-semibold text-text-primary mb-2">
          Success Traits Match
        </h3>
        <p className="text-sm text-muted italic">
          No success traits were defined for this job description.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-display font-semibold text-text-primary">
          Success Traits Match
        </h3>
        <span className="tag-chip bg-accent/15 text-accent text-xs font-mono">
          {traitsMatch.traits_match_score}/100
        </span>
      </div>
      <div className="space-y-2">
        {traitsMatch.traits_breakdown.map((tb, i) => {
          const style = MATCH_STYLES[tb.match_level] || MATCH_STYLES.ABSENT;
          return (
            <div key={i} className="bg-surface-raised rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-text-primary">{tb.trait}</span>
                <span className={`tag-chip text-[10px] ${style.className}`}>
                  {style.label}
                </span>
              </div>
              {tb.evidence && (
                <p className="text-xs text-text-secondary leading-relaxed">{tb.evidence}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
