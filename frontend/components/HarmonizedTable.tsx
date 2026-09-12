"use client";

interface Props {
  rows: Record<string, unknown>[];
  columns: string[];
}

export default function HarmonizedTable({ rows, columns }: Props) {
  if (rows.length === 0 || columns.length === 0) {
    return <p className="text-slate-500 text-sm">No rows produced.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-900 text-left">
            {columns.map((col) => (
              <th key={col} className="px-4 py-2.5 font-medium text-slate-300 uppercase text-xs tracking-wide">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-slate-800 hover:bg-slate-900/60">
              {columns.map((col) => (
                <td key={col} className="px-4 py-2 text-slate-200 tabular-nums">
                  {String(row[col] ?? "") === "" || row[col] === null
                    ? <span className="text-slate-600">null</span>
                    : String(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}