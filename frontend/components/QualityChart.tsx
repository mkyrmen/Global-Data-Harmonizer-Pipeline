"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
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
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="name" stroke="#94a3b8" />
            <YAxis domain={[0, 100]} stroke="#94a3b8" />
            <Tooltip cursor={{ fill: "rgba(148,163,184,0.08)" }} />
            <Legend />
            <Bar dataKey="score" name="Quality score">
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
            <BarChart data={deductions} layout="vertical" margin={{ left: 32 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis type="category" dataKey="name" width={140} stroke="#94a3b8" tick={{ fontSize: 12 }} />
              <Tooltip cursor={{ fill: "rgba(148,163,184,0.08)" }} />
              <Bar dataKey="points" name="Points deducted" fill="#f87171" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}