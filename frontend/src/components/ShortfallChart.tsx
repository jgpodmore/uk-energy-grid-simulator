import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHROME, STATUS, useIsDark } from "../colors";
import { dayToMonthLabel, MONTH_TICKS } from "../dateUtils";
import type { DailyRecord } from "../types";

export default function ShortfallChart({ daily }: { daily: DailyRecord[] }) {
  const dark = useIsDark();
  const chrome = dark ? CHROME.dark : CHROME.light;
  const rows = daily.map((d) => ({
    day: d.day,
    shortfall: d.unmet_demand_mwh / 1000,
  }));
  const anyShortfall = rows.some((r) => r.shortfall > 0);
  const worstDay = rows.reduce((best, r) => (r.shortfall > best.shortfall ? r : best), rows[0] ?? { day: 0, shortfall: 0 });

  return (
    <div className="chart-card">
      <h3>Days demand isn't met</h3>
      <p className="chart-desc">
        Days where available generation, storage and imports fall short of demand, and by how much (GWh/day).
      </p>
      {anyShortfall ? (
        <div className="banner critical" style={{ marginBottom: 12 }}>
          <strong>⚠ Shortfall.</strong>
          <span>
            Worst day: {worstDay.shortfall.toFixed(1)} GWh unmet on day {worstDay.day + 1} ({dayToMonthLabel(worstDay.day)}).
          </span>
        </div>
      ) : (
        <p className="chart-desc">This mix meets demand on every day of the year - no bars to show.</p>
      )}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={chrome.grid} vertical={false} />
          <XAxis
            dataKey="day"
            ticks={MONTH_TICKS}
            tickFormatter={(d: number) => dayToMonthLabel(d)}
            stroke={chrome.baseline}
            tick={{ fill: chrome.muted, fontSize: 11 }}
          />
          <YAxis
            stroke={chrome.baseline}
            tick={{ fill: chrome.muted, fontSize: 11 }}
            label={{ value: "GWh/day", angle: -90, position: "insideLeft", fill: chrome.muted, fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: chrome.surface, border: `1px solid ${chrome.grid}`, fontSize: 12 }}
            labelFormatter={(d: number) => `Day ${d + 1} (${dayToMonthLabel(d)})`}
            formatter={(value: number) => [`${value.toFixed(1)} GWh`, "Unmet demand"]}
          />
          <Bar dataKey="shortfall" fill={STATUS.critical} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
