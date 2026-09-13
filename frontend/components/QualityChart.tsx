"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { QualityInfo } from "@/lib/types";

interface Props {
  before: QualityInfo | null;
  after: QualityInfo | null;
}

export default function QualityChart({ before, after }: Props) {
  if (!before || !after) return null;

  const data = [
    { name: "Before", score: Math.round(before.score), fill: "#64748b" },
    { name: "After", score: Math.round(after.score), fill: "#22d3ee" },
  ];

  const deductions = Object.entries(after.deductions).map(([key, value]) => ({
    name: key.replace(/_/g, " "),
    points: value,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="name" stroke="#94a3b8" tickLine={false} axisLine={false} />
            <YAxis domain={[0, 100]} stroke="#94a3b8" tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: "rgba(148,163,184,0.08)" }}
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: "0.5rem",
                fontSize: "0.8rem",
              }}
            />
            <Bar dataKey="score" name="Quality score" maxBarSize={72} radius={[6, 6, 0, 0]}>
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {deductions.length > 0 && (
        <div className="h-48">
          <h4 className="text-sm font-medium text-slate-300 mb-2">Score deductions (after)</h4>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={deductions} layout="vertical" margin={{ left: 4, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
              <XAxis type="number" stroke="#94a3b8" tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="name" width={140} stroke="#94a3b8" tick={{ fontSize: 12 }} />
              <Tooltip
                cursor={{ fill: "rgba(148,163,184,0.08)" }}
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  borderRadius: "0.5rem",
                  fontSize: "0.8rem",
                }}
              />
              <Bar dataKey="points" name="Points deducted" fill="#f87171" maxBarSize={16} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}