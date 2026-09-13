"use client";

import { useState } from "react";

const PAGE_SIZE = 50;

interface Props {
  rows: Record<string, unknown>[];
  columns: string[];
}

export default function HarmonizedTable({ rows, columns }: Props) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const start = safePage * PAGE_SIZE;
  const slice = rows.slice(start, start + PAGE_SIZE);

  if (rows.length === 0 || columns.length === 0) {
    return <p className="text-slate-500 text-sm">No rows produced.</p>;
  }

  const firstRow = start + 1;
  const lastRow = Math.min(rows.length, start + PAGE_SIZE);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40">
      <div className="max-h-[28rem] overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="sticky top-0 z-10 bg-slate-900 text-left shadow-[0_1px_0_0_#1e293b]">
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-4 py-2.5 font-medium text-slate-300 uppercase text-xs tracking-widest"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.map((row, i) => (
              <tr
                key={`${safePage}-${i}`}
                className="border-t border-slate-800/70 transition-colors hover:bg-cyan-500/[0.04]"
              >
                {columns.map((col) => {
                  const value = row[col];
                  const isNull = value === null || value === undefined || String(value) === "";
                  return (
                    <td key={col} className="px-4 py-2 text-slate-200 tabular-nums">
                      {isNull ? (
                        <span className="text-slate-600 italic">null</span>
                      ) : (
                        String(value)
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-slate-800 px-4 py-2.5 text-xs text-slate-400">
        <span className="tabular-nums">
          Rows {firstRow}–{lastRow} of {rows.length}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={safePage === 0}
            className="rounded-md border border-slate-700 px-3 py-1.5 text-slate-300 transition-all duration-150 hover:border-cyan-500 hover:text-cyan-300 active:scale-[0.97] disabled:opacity-40"
          >
            Previous
          </button>
          <span className="tabular-nums">
            Page {safePage + 1} / {pageCount}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={safePage >= pageCount - 1}
            className="rounded-md border border-slate-700 px-3 py-1.5 text-slate-300 transition-all duration-150 hover:border-cyan-500 hover:text-cyan-300 active:scale-[0.97] disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}