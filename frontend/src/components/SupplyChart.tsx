import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHROME, pick, SUPPLY_COLORS, SUPPLY_LABELS, SUPPLY_ORDER, toSupplyKey, useIsDark } from "../colors";
import { dayToMonthLabel, MONTH_TICKS } from "../dateUtils";
import type { DailyRecord } from "../types";

interface Row {
  day: number;
  [key: string]: number;
}

function buildRows(daily: DailyRecord[]): Row[] {
  return daily.map((d) => {
    const row: Row = { day: d.day };
    for (const key of SUPPLY_ORDER) row[key] = 0;
    for (const [source, mwh] of Object.entries(d.supply_mwh)) {
      const key = toSupplyKey(source);
      row[key] += mwh / 1000; // MWh -> GWh
    }
    return row;
  });
}

export default function SupplyChart({ daily }: { daily: DailyRecord[] }) {
  const dark = useIsDark();
  const chrome = dark ? CHROME.dark : CHROME.light;
  const rows = buildRows(daily);

  return (
    <div className="chart-card">
      <h3>Supply over the year</h3>
      <p className="chart-desc">Daily electricity delivered (GWh/day), stacked by generation type and storage discharge.</p>
      <ResponsiveContainer width="100%" height={320}>
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
            formatter={(value: number, name: string) => [`${value.toFixed(0)} GWh`, SUPPLY_LABELS[name as keyof typeof SUPPLY_LABELS]]}
          />
          <Legend
            formatter={(value: string) => SUPPLY_LABELS[value as keyof typeof SUPPLY_LABELS]}
            wrapperStyle={{ fontSize: 12 }}
          />
          {SUPPLY_ORDER.map((key) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stackId="1"
              stroke={pick(SUPPLY_COLORS[key], dark)}
              fill={pick(SUPPLY_COLORS[key], dark)}
              fillOpacity={0.85}
              strokeWidth={1}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
