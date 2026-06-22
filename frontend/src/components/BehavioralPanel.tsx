import type { BehavioralSignals } from "@/types/candidate";

interface BehavioralPanelProps {
  signals: BehavioralSignals;
  evidence: string[];
}

interface SignalCard {
  key: keyof BehavioralSignals;
  label: string;
  evidenceHint: string;
}

const SIGNAL_CARDS: SignalCard[] = [
  { key: "career_momentum", label: "Career Momentum", evidenceHint: "Level progression & recent advancement" },
  { key: "learning_velocity", label: "Learning Velocity", evidenceHint: "New skill domains & certification pace" },
  { key: "role_consistency", label: "Role Consistency", evidenceHint: "Coherent career narrative across roles" },
  { key: "job_stability", label: "Job Stability", evidenceHint: "Tenure patterns & delivery consistency" },
  { key: "promotion_frequency", label: "Promotion Frequency", evidenceHint: "Internal advancement within companies" },
  { key: "upskilling_pattern", label: "Upskilling Pattern", evidenceHint: "Self-directed growth & certifications" },
];

function scoreColor(score: number): string {
  if (score >= 70) return "#2ECC71";
  if (score >= 40) return "#38BDF8";
  return "#FF9F43";
}

export default function BehavioralPanel({ signals, evidence }: BehavioralPanelProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-display font-semibold text-text-primary">
          Behavioral Signal Dashboard
        </h3>
        <span className="tag-chip bg-behavioral/15 text-behavioral text-xs font-mono">
          Composite: {signals.behavioral_composite}/100
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {SIGNAL_CARDS.map((card, idx) => {
          const value = signals[card.key] as number;
          return (
            <div
              key={card.key}
              className="bg-surface-raised rounded-lg p-3 animate-fade-in"
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              <p className="text-xs text-text-secondary mb-1">{card.label}</p>
              <p className="font-mono font-semibold text-text-primary mb-2">
                {value} <span className="text-text-secondary text-xs">/100</span>
              </p>
              <div className="h-1.5 bg-bg rounded-full overflow-hidden mb-2">
                <div
                  className="h-full rounded-full transition-all duration-700 ease-out"
                  style={{
                    width: `${value}%`,
                    backgroundColor: scoreColor(value),
                    transitionDelay: `${idx * 50}ms`,
                  }}
                />
              </div>
              <p className="text-[10px] text-muted leading-tight">{card.evidenceHint}</p>
            </div>
          );
        })}
      </div>

      {evidence.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
            Supporting Evidence
          </h4>
          <ul className="space-y-1.5">
            {evidence.slice(0, 6).map((e, i) => (
              <li key={i} className="text-xs text-text-secondary flex gap-2">
                <span className="text-behavioral shrink-0">▸</span>
                <span>{e}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
