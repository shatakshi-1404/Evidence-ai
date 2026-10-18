import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Passage } from "../lib/types";

type Props = { sources: Passage[]; cited: Set<number> };

export function SimilarityChart({ sources, cited }: Props) {
  const data = sources
    .filter((source) => source.similarity !== null)
    .map((source) => ({
      name: `[${source.marker ?? 0}]`,
      marker: source.marker ?? 0,
      similarity: Math.round((source.similarity ?? 0) * 100),
    }));

  if (data.length < 2) return null;

  return (
    <div>
      <p className="text-xs text-navy-soft">Similarity to your question (cited passages in teal)</p>
      <div className="mt-2 h-28 w-full" role="img" aria-label="Bar chart of similarity for each retrieved passage">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              formatter={(value) => [`${value}%`, "Similarity"]}
              cursor={{ fill: "rgba(15, 27, 45, 0.05)" }}
            />
            <Bar dataKey="similarity" radius={[4, 4, 0, 0]}>
              {data.map((entry) => (
                <Cell key={entry.name} fill={cited.has(entry.marker) ? "#0F766E" : "#CBD5D0"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
