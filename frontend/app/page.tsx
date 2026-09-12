import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-8 px-6 bg-gradient-to-b from-slate-950 to-slate-900 text-white">
      <div className="text-center max-w-2xl">
        <p className="text-sm tracking-widest uppercase text-cyan-400 mb-4">Data Engineering Platform</p>
        <h1 className="text-4xl sm:text-6xl font-bold tracking-tight mb-6">
          Global Data Harmonizer
        </h1>
        <p className="text-lg text-slate-300">
          Ingest messy multi-source socio-economic datasets, profile them, clean
          and harmonize country, numeric, date and missing-value inconsistencies,
          resolve duplicate conflicts, and validate a single source of truth — with
          full transformation lineage and quality scores.
        </p>
      </div>
      <Link
        href="/auth"
        className="rounded-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold px-8 py-3 transition-colors"
      >
        Open the Workspace
      </Link>
    </main>
  );
}