import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/useAuthStore";

type Mode = "login" | "register" | "confirm";

export default function Login() {
  const navigate = useNavigate();
  const { login, register, confirmRegistration, error, isLoading, clearError } =
    useAuthStore();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    clearError();
    try {
      if (mode === "login") {
        await login(email, password);
        navigate("/dashboard");
      } else if (mode === "register") {
        await register(email, password);
        setMode("confirm");
      } else {
        await confirmRegistration(email, code);
        setMode("login");
      }
    } catch {
      // Error state is already set in the store.
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {Array.from({ length: 40 }).map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 rounded-full bg-accent/20"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animation: `fade-in ${2 + Math.random() * 3}s ease-in-out infinite alternate`,
            }}
          />
        ))}
      </div>

      <div className="card w-full max-w-md p-8 relative z-10">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-4">
            <div className="w-6 h-6 rounded-full bg-accent" />
          </div>
          <h1 className="font-display font-bold text-2xl text-text-primary">
            TalentLens AI
          </h1>
          <p className="text-text-secondary text-sm mt-2">
            AI that finds the hire you'd otherwise miss.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-text-secondary mb-1.5" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field w-full"
              placeholder="recruiter@company.com"
              disabled={mode === "confirm"}
            />
          </div>

          {mode !== "confirm" && (
            <div>
              <label className="block text-xs text-text-secondary mb-1.5" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field w-full"
                placeholder="••••••••"
                minLength={8}
              />
            </div>
          )}

          {mode === "confirm" && (
            <div>
              <label className="block text-xs text-text-secondary mb-1.5" htmlFor="code">
                Verification Code
              </label>
              <input
                id="code"
                type="text"
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="input-field w-full"
                placeholder="123456"
              />
            </div>
          )}

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button type="submit" disabled={isLoading} className="btn-primary w-full">
            {isLoading
              ? "Please wait..."
              : mode === "login"
              ? "Sign In"
              : mode === "register"
              ? "Create Account"
              : "Confirm Account"}
          </button>
        </form>

        <div className="text-center mt-6 text-sm text-text-secondary">
          {mode === "login" && (
            <button onClick={() => setMode("register")} className="hover:text-accent">
              Don't have an account? Sign up
            </button>
          )}
          {mode === "register" && (
            <button onClick={() => setMode("login")} className="hover:text-accent">
              Already have an account? Sign in
            </button>
          )}
          {mode === "confirm" && (
            <button onClick={() => setMode("login")} className="hover:text-accent">
              Back to sign in
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
