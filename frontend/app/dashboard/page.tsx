"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { setToken } from "@/lib/supabase";
import { api, ApiError } from "@/lib/api";
import type { Workspace } from "@/lib/types";

export default function Dashboard() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [boosting, setBoosting] = useState(false);

  async function load() {
    try {
      const ws = await api.get<Workspace[]>("/api/workspaces");
      setWorkspaces(ws);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push("/auth");
      else setError(String((err as Error).message));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createWorkspace(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const ws = await api.post<Workspace>("/api/workspaces", { name: name || "Untitled workspace" });
      setWorkspaces((prev) => [...prev, ws]);
      setName("");
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setCreating(false);
    }
  }

  async function bootstrapDemo() {
    setBoosting(true);
    setError(null);
    try {
      const ws = await api.post<Workspace>("/api/auth/demo");
      setWorkspaces((prev) => (prev.some((w) => w.id === ws.id) ? prev : [...prev, ws]));
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBoosting(false);
    }
  }

  function signOut() {
    setToken(null);
    router.push("/auth");
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="bg-glow pointer-events-none fixed inset-0" aria-hidden />

      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-8 py-4">
          <h1 className="text-xl font-bold tracking-tight">Global Data Harmonizer</h1>
          <button
            onClick={signOut}
            className="rounded-md px-3 py-1.5 text-sm text-slate-400 transition-all duration-150 hover:bg-slate-900 hover:text-white active:scale-[0.97]"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="fade-in mx-auto max-w-5xl px-8 py-8">
        <section className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Workspaces</h2>
            <p className="mt-1 text-sm text-slate-400">
              Upload messy datasets, review and toggle sources, then run the harmonization pipeline.
            </p>
          </div>
          <button
            onClick={bootstrapDemo}
            disabled={boosting}
            className="rounded-md border border-cyan-500/70 px-4 py-2 text-sm font-medium text-cyan-300 transition-all duration-150 hover:bg-cyan-500/10 active:scale-[0.97] disabled:opacity-50"
          >
            {boosting ? "Loading demo…" : "Load demo workspace"}
          </button>
        </section>

        {error && (
          <p className="mt-4 rounded-lg border border-red-800 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
            {error}
          </p>
        )}

        <form onSubmit={createWorkspace} className="mt-6 flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New workspace name"
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm placeholder-slate-500 transition-colors duration-150 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/25"
          />
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition-all duration-150 hover:bg-cyan-400 active:scale-[0.97] disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create"}
          </button>
        </form>

        <div className="mt-8">
          {loading ? (
            <div className="flex flex-col gap-3">
              {[0, 1].map((i) => (
                <div
                  key={i}
                  className="h-20 animate-pulse rounded-xl border border-slate-800 bg-slate-900/60"
                />
              ))}
            </div>
          ) : workspaces.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700 p-10 text-center text-slate-500">
              No workspaces yet. Upload datasets in a workspace, or load the demo.
            </div>
          ) : (
            <ul className="flex flex-col gap-3">
              {workspaces.map((ws) => (
                <li key={ws.id} className="fade-in">
                  <Link
                    href={`/workspace/${ws.id}`}
                    className="group block rounded-xl border border-slate-800 bg-slate-900 px-5 py-4 shadow-[0_0_0_1px_rgba(148,163,184,0.05)] transition-all duration-150 hover:-translate-y-0.5 hover:border-cyan-600 hover:shadow-lg hover:shadow-slate-950/40"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-semibold transition-colors duration-150 group-hover:text-cyan-300">
                          {ws.name}
                        </h3>
                        {ws.description && (
                          <p className="mt-0.5 text-sm text-slate-400">{ws.description}</p>
                        )}
                      </div>
                      <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs tabular-nums text-slate-300">
                        {ws.sources.length} source{ws.sources.length === 1 ? "" : "s"}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  );
}