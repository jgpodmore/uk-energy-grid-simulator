import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHROME, useIsDark } from "../colors";
import { dayToMonthLabel, MONTH_TICKS } from "../dateUtils";
import type { DailyRecord } from "../types";

export default function CurtailmentChart({ daily }: { daily: DailyRecord[] }) {
  const dark = useIsDark();
  const chrome = dark ? CHROME.dark : CHROME.light;
  const rows = daily.map((d) => ({
    day: d.day,
    payment: d.curtailment_payment_gbp / 1000,
    mwh: d.curtailment_total_mwh,
  }));
  const anyCurtailment = rows.some((r) => r.payment > 0);

  return (
    <div className="chart-card">
      <h3>Curtailment payments</h3>
      <p className="chart-desc">
        When supply exceeds demand and storage is full, surplus generation is curtailed and paid for anyway - shown
        here as £k/day.
      </p>
      {!anyCurtailment && <p className="chart-desc">No curtailment occurs with this mix.</p>}
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
            label={{ value: "£k/day", angle: -90, position: "insideLeft", fill: chrome.muted, fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: chrome.surface, border: `1px solid ${chrome.grid}`, fontSize: 12 }}
            labelFormatter={(d: number) => `Day ${d + 1} (${dayToMonthLabel(d)})`}
            formatter={(value: number, name: string) =>
              name === "payment" ? [`£${value.toFixed(0)}k`, "Curtailment payment"] : [`${value.toFixed(0)} MWh`, "Curtailed"]
            }
          />
          <Bar dataKey="payment" fill="#256abf" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
