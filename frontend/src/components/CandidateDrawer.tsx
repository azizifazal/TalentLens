import { useEffect, useState } from "react";
import { getCandidate } from "@/api/candidates";
import BehavioralPanel from "@/components/BehavioralPanel";
import TraitsMatchPanel from "@/components/TraitsMatchPanel";
import ScoreRing from "@/components/ScoreRing";
import type { Candidate } from "@/types/candidate";
import type { RankedCandidate } from "@/types/ranking";

interface CandidateDrawerProps {
  sessionId: string;
  rankedCandidate: RankedCandidate;
  onClose: () => void;
}

export default function CandidateDrawer({
  sessionId,
  rankedCandidate,
  onClose,
}: CandidateDrawerProps) {
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getCandidate(sessionId, rankedCandidate.candidate_id);
        if (!cancelled) setCandidate(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load candidate");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId, rankedCandidate.candidate_id]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-black/60 animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative w-full max-w-2xl bg-bg h-full overflow-y-auto animate-slide-in-right shadow-2xl border-l border-white/10">
        <div className="sticky top-0 bg-bg/95 backdrop-blur border-b border-white/5 px-6 py-4 flex items-center justify-between z-10">
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary transition-colors flex items-center gap-1.5 text-sm"
          >
            ← Back to shortlist
          </button>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-surface-raised flex items-center justify-center text-text-secondary"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="p-6">
          {isLoading && (
            <div className="space-y-4 animate-pulse">
              <div className="h-20 bg-surface rounded-card" />
              <div className="h-40 bg-surface rounded-card" />
              <div className="h-40 bg-surface rounded-card" />
            </div>
          )}

          {error && (
            <div className="card p-4 border border-red-500/30 text-red-400 text-sm">
              {error}
            </div>
          )}

          {!isLoading && !error && candidate?.profile && candidate.signals && (
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <ScoreRing score={rankedCandidate.composite_score} size={72} />
                <div>
                  <h2 className="font-display font-bold text-xl text-text-primary">
                    {candidate.profile.full_name}
                  </h2>
                  <p className="text-text-secondary">
                    {candidate.profile.current_title}
                    {candidate.profile.current_company &&
                      ` @ ${candidate.profile.current_company}`}
                  </p>
                  <p className="text-xs text-muted mt-1">
                    {candidate.profile.location} · {candidate.profile.years_experience} years experience
                  </p>
                </div>
              </div>

              {rankedCandidate.explanation && (
                <div className="card p-4">
                  <h3 className="font-display font-semibold text-text-primary mb-2">
                    AI Summary
                  </h3>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {rankedCandidate.explanation}
                  </p>
                </div>
              )}

              <div className="card p-4">
                <h3 className="font-display font-semibold text-text-primary mb-3">
                  Work History
                </h3>
                <div className="space-y-4">
                  {candidate.profile.work_history.map((w, i) => (
                    <div key={i} className="relative pl-4 border-l-2 border-surface-raised">
                      <div className="absolute -left-[5px] top-1 w-2 h-2 rounded-full bg-accent" />
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-text-primary text-sm">
                          {w.title}
                        </span>
                        <span className="tag-chip bg-surface-raised text-text-secondary text-[10px]">
                          {w.level_inferred}
                        </span>
                      </div>
                      <p className="text-xs text-text-secondary">
                        {w.company} · {w.start_date} – {w.end_date || "Present"} (
                        {w.duration_months} mo)
                      </p>
                      {w.description_summary && (
                        <p className="text-xs text-muted mt-1">{w.description_summary}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="card p-4">
                <h3 className="font-display font-semibold text-text-primary mb-3">
                  Skills
                </h3>
                <div className="flex flex-wrap gap-2">
                  {candidate.profile.skills.map((s, i) => {
                    const isFresh =
                      s.last_used_year && s.last_used_year >= new Date().getFullYear() - 2;
                    return (
                      <span
                        key={i}
                        className={`tag-chip text-xs ${
                          isFresh
                            ? "bg-accent/15 text-accent"
                            : "bg-surface-raised text-muted"
                        }`}
                      >
                        {s.name}
                      </span>
                    );
                  })}
                </div>
              </div>

              <div className="card p-4">
                <BehavioralPanel
                  signals={candidate.signals.behavioral}
                  evidence={candidate.profile.raw_behavioral_evidence}
                />
              </div>

              <div className="card p-4">
                <TraitsMatchPanel traitsMatch={candidate.signals.traits_match} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
