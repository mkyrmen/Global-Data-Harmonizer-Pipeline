"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, ApiError, downloadUrl } from "@/lib/api";
import type { HarmonizedDataset, JobResult, Workspace } from "@/lib/types";
import HarmonizedTable from "@/components/HarmonizedTable";
import QualityChart from "@/components/QualityChart";

export default function WorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);
  const [dataset, setDataset] = useState<HarmonizedDataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(
    async function load() {
      try {
        const ws = await api.get<Workspace>(`/api/workspaces/${id}`);
        setWorkspace(ws);
        setSelected(ws.sources.filter((s) => s.include).map((s) => s.id));
      } catch (err) {
        setError(String((err as Error).message));
      }
    },
    [id]
  );

  useEffect(() => {
    load();
  }, [load]);

  async function persistSelection(next: string[]) {
    await api.patch(`/api/workspaces/${id}/sources`, {
      sources: workspace!.sources.map((s) => ({ source_id: s.id, include: next.includes(s.id) })),
    });
  }

  async function onToggle(sourceId: string) {
    const next = selected.includes(sourceId)
      ? selected.filter((x) => x !== sourceId)
      : [...selected, sourceId];
    setSelected(next);
    try {
      await persistSelection(next);
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("workspace_id", id);
    setError(null);
    try {
      await api.upload<unknown>("/api/datasets/upload", form);
      await load();
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function runPipeline(e: React.FormEvent) {
    e.preventDefault();
    setRunning(true);
    setError(null);
    setResult(null);
    setDataset(null);
    try {
      const job = await api.post<JobResult>("/api/jobs/run", {
        workspace_id: id,
        name: `${workspace?.name ?? "Workspace"} · harmonized`,
        source_ids: selected,
      });
      setResult(job);
      if (job.job_id) {
        const detail = await api.get<{ dataset: HarmonizedDataset | null }>(`/api/jobs/${job.job_id}`);
        setDataset(detail.dataset);
      }
    } catch (err) {
      setError(err instanceof ApiError ? `${err.message}` : String((err as Error).message));
    } finally {
      setRunning(false);
    }
  }

  const sources = workspace?.sources ?? [];

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="bg-glow pointer-events-none fixed inset-0" aria-hidden />

      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/dashboard"
              className="shrink-0 rounded-md px-2 py-1 text-sm text-slate-400 transition-all duration-150 hover:bg-slate-900 hover:text-white active:scale-[0.97]"
            >
              ← Workspaces
            </Link>
            <h1 className="truncate text-xl font-bold tracking-tight">
              {workspace?.name ?? "Loading…"}
            </h1>
          </div>
          <form onSubmit={runPipeline} className="flex shrink-0 items-center gap-2">
            <button
              type="submit"
              disabled={running || selected.length === 0}
              className="rounded-lg bg-cyan-500 px-5 py-2 text-sm font-semibold text-slate-950 transition-all duration-150 hover:bg-cyan-400 active:scale-[0.97] disabled:opacity-50"
            >
              {running ? (
                <span className="flex items-center gap-2">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-950/30 border-t-slate-950" />
                  Running…
                </span>
              ) : (
                "Run pipeline"
              )}
            </button>
          </form>
        </div>
      </header>

      {error && (
        <p className="mx-auto mt-4 max-w-6xl rounded-lg border border-red-800 bg-red-950/40 px-8 py-2.5 text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="fade-in mx-auto max-w-6xl px-8 py-8">
        <section className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold tracking-tight">Sources — review and toggle</h2>
            <button
              onClick={() => fileInput.current?.click()}
              className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-200 transition-all duration-150 hover:border-cyan-500 hover:text-cyan-300 active:scale-[0.97]"
            >
              Upload dataset
            </button>
            <input ref={fileInput} type="file" accept=".csv,text/csv" hidden onChange={onPickFile} />
          </div>

          {sources.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700 p-10 text-center text-slate-500">
              No sources yet. Upload a CSV to get started.
            </div>
          ) : (
            <ul className="flex flex-col gap-3">
              {sources.map((src) => (
                <li
                  key={src.id}
                  className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900 transition-colors duration-150 hover:border-slate-700"
                >
                  <div className="flex items-center gap-3 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.includes(src.id)}
                      onChange={() => onToggle(src.id)}
                      className="h-4 w-4 shrink-0 accent-cyan-500"
                    />
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate font-medium">{src.name}</h3>
                      <p className="mt-0.5 truncate text-xs text-slate-400">
                        <span className="tabular-nums">{src.row_count} rows</span> ·{" "}
                        {src.column_names.join(", ") || "no columns"}
                      </p>
                    </div>
                  </div>
                  {src.preview_json.length > 0 && (
                    <div className="max-h-48 overflow-auto border-t border-slate-800/70 px-4 pb-3 pt-2">
                      <table className="w-full text-xs text-slate-300">
                        <thead>
                          <tr>
                            {src.column_names.map((c) => (
                              <th key={c} className="bg-slate-800 px-2 py-1 text-left font-medium uppercase tracking-wide">
                                {c}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {src.preview_json.slice(0, 5).map((row, i) => (
                            <tr key={i} className="transition-colors hover:bg-cyan-500/[0.04]">
                              {src.column_names.map((c) => (
                                <td key={c} className="border-t border-slate-800 px-2 py-1 tabular-nums">
                                  {String((row as Record<string, unknown>)[c] ?? "")}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {(result || dataset) && (
          <section className="fade-in mt-10 flex flex-col gap-4">
            <h2 className="text-lg font-semibold tracking-tight">Harmonized result</h2>
            {result && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Metric label="Rows" value={`${result.input_rows} → ${result.output_rows}`} />
                <Metric label="Duplicates removed" value={String(result.duplicates_removed)} />
                <Metric
                  label="Quality"
                  value={`${result.quality_before?.score.toFixed(1) ?? "–"} → ${result.quality_after?.score.toFixed(1) ?? "–"}`}
                />
                <Metric
                  label="Validation"
                  value={
                    result.validation
                      ? `${result.validation.failed === 0 ? "PASS" : "FAIL"} (${result.validation.passed}/${result.validation.passed + result.validation.failed})`
                      : "–"
                  }
                />
              </div>
            )}

            {result && (
              <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
                <QualityChart before={result.quality_before} after={result.quality_after} />
              </div>
            )}

            {dataset && (
              <div className="flex flex-col gap-6">
                <div className="flex flex-wrap gap-2">
                  <DownloadLink href={downloadUrl(`/api/reports/${dataset.id}/csv`)} label="Download harmonized CSV" />
                  <DownloadLink href={downloadUrl(`/api/reports/${dataset.id}/report?name=quality`)} label="Quality report (JSON)" />
                  <DownloadLink href={downloadUrl(`/api/reports/${dataset.id}/report?name=lineage`)} label="Transformation log (JSON)" />
                </div>
                <HarmonizedTable
                  rows={dataset.data_json}
                  columns={Array.from(new Set(dataset.data_json.flatMap((r) => Object.keys(r))))}
                />
              </div>
            )}

            {result?.conflicts && result.conflicts.length > 0 && (
              <div className="rounded-xl border border-amber-700/50 bg-amber-950/30 p-4">
                <h3 className="mb-2 text-sm font-semibold text-amber-300">
                  Cross-source conflicts detected
                </h3>
                <ul className="space-y-1 text-sm text-amber-200">
                  {result.conflicts.map((c, i) => (
                    <li key={i}>
                      {c.key_value} · {c.field}: {String(c.values)} → selected {String(c.selected_value)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 shadow-[0_0_0_1px_rgba(148,163,184,0.05)]">
      <p className="text-xs uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-1.5 text-lg font-semibold tabular-nums tracking-tight">{value}</p>
    </div>
  );
}

function DownloadLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      onClick={() => {
        void fetch(href).then((r) => {
          if (!r.ok) return;
          return r.blob().then((blob) => {
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = href.split("?")[0].split("/").pop() ?? "download";
            a.click();
            URL.revokeObjectURL(a.href);
          });
        });
      }}
      className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-200 transition-all duration-150 hover:border-cyan-500 hover:text-cyan-300 active:scale-[0.97]"
    >
      {label}
    </a>
  );
}