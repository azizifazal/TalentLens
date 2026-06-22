import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/useAuthStore";
import { useSessionStore } from "@/store/useSessionStore";
import type { SessionStatus } from "@/types/session";

const STATUS_LABELS: Record<SessionStatus, string> = {
  CREATED: "Draft",
  JD_ANALYZED: "Role Defined",
  INGESTING: "Uploading Candidates",
  RANKED: "Ranked",
};

const STATUS_COLORS: Record<SessionStatus, string> = {
  CREATED: "bg-surface-raised text-text-secondary",
  JD_ANALYZED: "bg-accent/15 text-accent",
  INGESTING: "bg-accent-warm/15 text-accent-warm",
  RANKED: "bg-success/15 text-success",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { userEmail, logout } = useAuthStore();
  const { sessions, fetchSessions, startNewSession, isLoading, error } = useSessionStore();
  const [showNewModal, setShowNewModal] = useState(false);
  const [jobTitle, setJobTitle] = useState("");

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  async function handleCreateSession(e: FormEvent) {
    e.preventDefault();
    if (!jobTitle.trim()) return;
    const sessionId = await startNewSession(jobTitle.trim());
    setShowNewModal(false);
    setJobTitle("");
    navigate(`/session/${sessionId}`);
  }

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 border-r border-white/5 p-6 flex flex-col">
        <div className="flex items-center gap-2 mb-10">
          <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
            <div className="w-4 h-4 rounded-full bg-accent" />
          </div>
          <span className="font-display font-bold text-text-primary">TalentLens</span>
        </div>

        <nav className="space-y-1 flex-1">
          <a className="block px-3 py-2 rounded-lg bg-surface-raised text-text-primary text-sm font-medium">
            Sessions
          </a>
        </nav>

        <div className="border-t border-white/5 pt-4">
          <p className="text-xs text-text-secondary truncate mb-2">{userEmail}</p>
          <button
            onClick={handleLogout}
            className="text-xs text-text-secondary hover:text-text-primary"
          >
            Logout
          </button>
        </div>
      </aside>

      <main className="flex-1 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-display font-bold text-2xl text-text-primary">
              Recruitment Sessions
            </h1>
            <p className="text-text-secondary text-sm mt-1">
              Manage your AI-powered candidate shortlists
            </p>
          </div>
          <button onClick={() => setShowNewModal(true)} className="btn-primary">
            + New Session
          </button>
        </div>

        {error && (
          <div className="card p-4 border border-red-500/30 text-red-400 text-sm mb-6">
            {error}
          </div>
        )}

        {isLoading && sessions.length === 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card p-5 h-32 animate-pulse" />
            ))}
          </div>
        )}

        {!isLoading && sessions.length === 0 && (
          <div className="card p-12 text-center">
            <p className="text-text-secondary mb-4">
              Start by defining a role. TalentLens will help you find the candidates
              you'd otherwise miss.
            </p>
            <button onClick={() => setShowNewModal(true)} className="btn-primary">
              Create Your First Session
            </button>
          </div>
        )}

        {sessions.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sessions.map((session) => (
              <button
                key={session.session_id}
                onClick={() => navigate(`/session/${session.session_id}`)}
                className="card p-5 text-left hover:bg-surface-raised transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-display font-semibold text-text-primary truncate pr-2">
                    {session.job_title}
                  </h3>
                  <span
                    className={`tag-chip text-[10px] shrink-0 ${
                      STATUS_COLORS[session.status]
                    }`}
                  >
                    {STATUS_LABELS[session.status]}
                  </span>
                </div>
                <p className="text-sm text-text-secondary">
                  {session.candidate_count} candidate
                  {session.candidate_count !== 1 ? "s" : ""}
                </p>
                <p className="text-xs text-muted mt-2">
                  Created {new Date(session.created_at).toLocaleDateString()}
                </p>
              </button>
            ))}
          </div>
        )}
      </main>

      {showNewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="card w-full max-w-md p-6">
            <h2 className="font-display font-semibold text-lg text-text-primary mb-4">
              New Recruitment Session
            </h2>
            <form onSubmit={handleCreateSession}>
              <label className="block text-xs text-text-secondary mb-1.5">
                Job Title
              </label>
              <input
                type="text"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                placeholder="e.g. Senior Backend Engineer"
                className="input-field w-full mb-4"
                autoFocus
                required
                minLength={2}
              />
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" disabled={isLoading} className="btn-primary">
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
