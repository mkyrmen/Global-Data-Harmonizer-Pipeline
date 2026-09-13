import Link from "next/link";

export default function Home() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center gap-8 overflow-hidden bg-gradient-to-b from-slate-950 to-slate-900 px-6 text-white">
      <div className="bg-glow pointer-events-none absolute inset-0" aria-hidden />
      <div className="fade-in relative max-w-2xl text-center">
        <p className="mb-4 text-sm uppercase tracking-[0.3em] text-cyan-400">
          Data Engineering Platform
        </p>
        <h1 className="mb-6 bg-gradient-to-br from-white to-slate-400 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-6xl">
          Global Data Harmonizer
        </h1>
        <p className="mx-auto max-w-xl text-lg text-slate-300">
          Ingest messy multi-source socio-economic datasets, profile them, clean
          and harmonize country, numeric, date and missing-value inconsistencies,
          resolve duplicate conflicts, and validate a single source of truth — with
          full transformation lineage and quality scores.
        </p>
      </div>
      <Link
        href="/auth"
        className="relative rounded-full bg-cyan-500 px-8 py-3 font-semibold text-slate-950 shadow-lg shadow-cyan-500/25 transition-all duration-150 hover:-translate-y-0.5 hover:bg-cyan-400 hover:shadow-cyan-400/30 active:scale-[0.97]"
      >
        Open the Workspace
      </Link>
    </main>
  );
}