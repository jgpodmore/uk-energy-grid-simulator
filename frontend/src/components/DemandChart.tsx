import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHROME, useIsDark } from "../colors";
import { dayToMonthLabel, MONTH_TICKS } from "../dateUtils";
import type { DailyRecord } from "../types";

export default function DemandChart({ daily }: { daily: DailyRecord[] }) {
  const dark = useIsDark();
  const chrome = dark ? CHROME.dark : CHROME.light;

  const rows = daily.map((d) => {
    const charge = (d.storage_charge_mwh.battery ?? 0) + (d.storage_charge_mwh.other_storage ?? 0);
    return {
      day: d.day,
      demand: d.demand_mwh / 1000,
      charging: charge / 1000,
    };
  });

  return (
    <div className="chart-card">
      <h3>Demand over the year</h3>
      <p className="chart-desc">
        Electricity demand (GWh/day), plus the extra load storage draws while charging - together this is the total
        load generators must meet.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
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
            formatter={(value: number, name: string) => [
              `${value.toFixed(0)} GWh`,
              name === "demand" ? "Electricity demand" : "Storage charging load",
            ]}
          />
          <Legend
            formatter={(v: string) => (v === "demand" ? "Electricity demand" : "Storage charging load")}
            wrapperStyle={{ fontSize: 12 }}
          />
          <Area
            type="monotone"
            dataKey="demand"
            stackId="1"
            stroke="#256abf"
            fill="#256abf"
            fillOpacity={0.75}
            strokeWidth={1}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="charging"
            stackId="1"
            stroke="#898781"
            fill="#898781"
            fillOpacity={0.6}
            strokeWidth={1}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
