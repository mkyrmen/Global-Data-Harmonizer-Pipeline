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
    <main className="min-h-screen flex items-center justify-center bg-slate-950 text-white px-6">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-center mb-2">Global Data Harmonizer</h1>
        <p className="text-center text-slate-400 text-sm mb-8">
          {mode === "login" ? "Sign in to your workspace" : "Create an account"}
        </p>

        <div className="flex rounded-lg bg-slate-900 p-1 mb-6">
          {(["login", "register"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === m ? "bg-cyan-500 text-slate-950" : "text-slate-400 hover:text-white"
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
            className="rounded-md bg-slate-900 border border-slate-700 px-4 py-2.5 text-sm focus:outline-none focus:border-cyan-500"
          />
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (min 6 characters)"
            className="rounded-md bg-slate-900 border border-slate-700 px-4 py-2.5 text-sm focus:outline-none focus:border-cyan-500"
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold py-2.5 disabled:opacity-50 transition-colors"
          >
            {loading ? "Working…" : mode === "login" ? "Sign in" : "Register"}
          </button>
        </form>
      </div>
    </main>
  );
}