import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function ScoreTrendChart({ data = [] }) {
  return (
    <div className="chart-card">
      <h2>Score Trend</h2>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data}>
          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <Tooltip contentStyle={{ background: "#111827", border: "1px solid #334155" }} />
          <Area
            type="monotone"
            dataKey="score"
            stroke="#22c55e"
            fill="#22c55e"
            fillOpacity={0.18}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
