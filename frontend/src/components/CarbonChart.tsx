import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHROME, useIsDark } from "../colors";
import { dayToMonthLabel, MONTH_TICKS } from "../dateUtils";
import type { DailyRecord } from "../types";

export default function CarbonChart({ daily }: { daily: DailyRecord[] }) {
  const dark = useIsDark();
  const chrome = dark ? CHROME.dark : CHROME.light;
  const rows = daily.map((d) => ({ day: d.day, intensity: d.carbon_intensity_gco2_per_kwh }));

  return (
    <div className="chart-card">
      <h3>Carbon intensity over the year</h3>
      <p className="chart-desc">Grams of CO₂ per kWh of electricity delivered, averaged over each day.</p>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
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
            label={{ value: "gCO₂/kWh", angle: -90, position: "insideLeft", fill: chrome.muted, fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: chrome.surface, border: `1px solid ${chrome.grid}`, fontSize: 12 }}
            labelFormatter={(d: number) => `Day ${d + 1} (${dayToMonthLabel(d)})`}
            formatter={(value: number) => [`${value.toFixed(0)} gCO₂/kWh`, "Carbon intensity"]}
          />
          <Line type="monotone" dataKey="intensity" stroke="#256abf" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
