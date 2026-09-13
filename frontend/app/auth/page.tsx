"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabase, setToken } from "@/lib/supabase";
import { api } from "@/lib/api";

type Mode = "login" | "register";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data, error: authError } =
        mode === "login"
          ? await getSupabase().auth.signInWithPassword({ email, password })
          : await getSupabase().auth.signUp({ email, password });
      if (authError) throw authError;
      const session = data.session;
      if (!session) {
        setError("Account created. Confirm your email, then sign in.");
        return;
      }
      setToken(session.access_token);
      try {
        await api.get("/api/auth/me");
      } catch {
        /* profile may take a moment; non-fatal */
      }
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-b from-slate-950 to-slate-900 px-6 text-white">
      <div className="bg-glow pointer-events-none absolute inset-0" aria-hidden />

      <div className="fade-in relative w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-2xl shadow-slate-950/50 backdrop-blur-md">
        <h1 className="mb-1 text-center text-2xl font-bold tracking-tight">
          Global Data Harmonizer
        </h1>
        <p className="mb-8 text-center text-sm text-slate-400">
          {mode === "login" ? "Sign in to your workspace" : "Create an account"}
        </p>

        <div className="mb-6 flex rounded-lg bg-slate-950/60 p-1">
          {(["login", "register"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                setError(null);
              }}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-all duration-150 ${
                mode === m
                  ? "bg-cyan-500 text-slate-950 shadow-sm shadow-cyan-500/30"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {m === "login" ? "Sign in" : "Register"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="flex flex-col gap-4">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className="rounded-lg border border-slate-700 bg-slate-950/60 px-4 py-2.5 text-sm placeholder-slate-500 transition-colors duration-150 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/25"
          />
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (min 6 characters)"
            className="rounded-lg border border-slate-700 bg-slate-950/60 px-4 py-2.5 text-sm placeholder-slate-500 transition-colors duration-150 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/25"
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-cyan-500 py-2.5 font-semibold text-slate-950 transition-all duration-150 hover:bg-cyan-400 active:scale-[0.98] disabled:opacity-50"
          >
            {loading
              ? "Working…"
              : mode === "login"
                ? "Sign in"
                : "Register"}
          </button>
        </form>
      </div>
    </main>
  );
}