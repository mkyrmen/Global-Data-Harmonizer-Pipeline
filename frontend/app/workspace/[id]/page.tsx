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
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-slate-400 hover:text-white text-sm">
            ← Workspaces
          </Link>
          <h1 className="text-xl font-bold">{workspace?.name ?? "Loading…"}</h1>
        </div>
        <form onSubmit={runPipeline} className="flex items-center gap-2">
          <button
            type="submit"
            disabled={running || selected.length === 0}
            className="rounded-md bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold px-5 py-2 text-sm disabled:opacity-50"
          >
            {running ? "Running pipeline…" : "Run pipeline"}
          </button>
        </form>
      </header>

      {error && <p className="mx-8 mt-4 text-sm text-red-400">{error}</p>}

      <div className="max-w-6xl mx-auto px-8 py-8 flex flex-col gap-10">
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Sources — review and toggle</h2>
            <button
              onClick={() => fileInput.current?.click()}
              className="rounded-md border border-slate-700 hover:border-cyan-500 px-4 py-2 text-sm"
            >
              Upload dataset
            </button>
            <input ref={fileInput} type="file" accept=".csv,text/csv" hidden onChange={onPickFile} />
          </div>

          {sources.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-700 p-10 text-center text-slate-500">
              No sources yet. Upload a CSV to get started.
            </div>
          ) : (
            <ul className="flex flex-col gap-3">
              {sources.map((src) => (
                <li key={src.id} className="rounded-lg border border-slate-800 bg-slate-900">
                  <div className="flex items-center gap-3 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.includes(src.id)}
                      onChange={() => onToggle(src.id)}
                      className="w-4 h-4 accent-cyan-500"
                    />
                    <div className="flex-1">
                      <h3 className="font-medium">{src.name}</h3>
                      <p className="text-xs text-slate-400">
                        {src.row_count} rows · {src.column_names.join(", ") || "no columns"}
                      </p>
                    </div>
                  </div>
                  {src.preview_json.length > 0 && (
                    <div className="px-4 pb-3 overflow-x-auto">
                      <table className="text-xs text-slate-300 border border-slate-800">
                        <thead>
                          <tr>{src.column_names.map((c) => <th key={c} className="px-2 py-1 bg-slate-800">{c}</th>)}</tr>
                        </thead>
                        <tbody>
                          {src.preview_json.slice(0, 5).map((row, i) => (
                            <tr key={i}>
                              {src.column_names.map((c) => (
                                <td key={c} className="px-2 py-1 border-t border-slate-800">
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
          <section className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold">Harmonized result</h2>
            {result && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Metric label="Rows" value={`${result.input_rows} → ${result.output_rows}`} />
                <Metric label="Duplicates removed" value={String(result.duplicates_removed)} />
                <Metric label="Quality" value={`${result.quality_before?.score.toFixed(1) ?? "–"} → ${result.quality_after?.score.toFixed(1) ?? "–"}`} />
                <Metric
                  label="Validation"
                  value={result.validation ? `${result.validation.failed === 0 ? "PASS" : "FAIL"} (${result.validation.passed}/${result.validation.passed + result.validation.failed})` : "–"}
                />
              </div>
            )}

            {result && (
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                <QualityChart before={result.quality_before} after={result.quality_after} />
              </div>
            )}

            {dataset && (
              <div className="flex flex-col gap-6">
                <div className="flex gap-3 flex-wrap">
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
              <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 p-4">
                <h3 className="font-semibold text-amber-300 text-sm mb-2">Cross-source conflicts detected</h3>
                <ul className="text-sm text-amber-200 space-y-1">
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
    <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3">
      <p className="text-xs text-slate-400 uppercase tracking-wide">{label}</p>
      <p className="mt-1 font-semibold tabular-nums">{value}</p>
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
      className="rounded-md border border-slate-700 hover:border-cyan-500 px-4 py-2 text-sm"
    >
      {label}
    </a>
  );
}