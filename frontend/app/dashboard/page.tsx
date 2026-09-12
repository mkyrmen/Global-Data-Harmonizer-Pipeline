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
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-800">
        <h1 className="text-xl font-bold">Global Data Harmonizer</h1>
        <button onClick={signOut} className="text-sm text-slate-400 hover:text-white">
          Sign out
        </button>
      </header>

      <div className="max-w-5xl mx-auto px-8 py-8 flex flex-col gap-8">
        <section className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold">Workspaces</h2>
            <p className="text-slate-400 text-sm">
              Upload messy datasets, review and toggle sources, then run the harmonization pipeline.
            </p>
          </div>
          <button
            onClick={bootstrapDemo}
            disabled={boosting}
            className="rounded-md border border-cyan-500 text-cyan-300 hover:bg-cyan-500/10 px-4 py-2 text-sm disabled:opacity-50"
          >
            {boosting ? "Loading demo…" : "Load demo workspace"}
          </button>
        </section>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <form onSubmit={createWorkspace} className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New workspace name"
            className="flex-1 rounded-md bg-slate-900 border border-slate-700 px-4 py-2.5 text-sm focus:outline-none focus:border-cyan-500"
          />
          <button
            type="submit"
            disabled={creating}
            className="rounded-md bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold px-4 py-2 text-sm disabled:opacity-50"
          >
            Create
          </button>
        </form>

        {loading ? (
          <p className="text-slate-500">Loading…</p>
        ) : workspaces.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-700 p-10 text-center text-slate-500">
            No workspaces yet. Upload datasets in a workspace, or load the demo.
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {workspaces.map((ws) => (
              <li key={ws.id}>
                <Link
                  href={`/workspace/${ws.id}`}
                  className="block rounded-lg border border-slate-800 hover:border-cyan-600 bg-slate-900 px-5 py-4 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold">{ws.name}</h3>
                      {ws.description && <p className="text-sm text-slate-400">{ws.description}</p>}
                    </div>
                    <span className="text-xs px-2 py-1 rounded-full bg-slate-800 text-slate-300">
                      {ws.sources.length} source{ws.sources.length === 1 ? "" : "s"}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}