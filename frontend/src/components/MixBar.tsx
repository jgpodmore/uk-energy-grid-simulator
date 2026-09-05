import { pick, SUPPLY_COLORS, SUPPLY_LABELS, SUPPLY_ORDER, toSupplyKey, useIsDark } from "../colors";
import type { Headline } from "../types";

export default function MixBar({ headline }: { headline: Headline }) {
  const dark = useIsDark();
  const shares: Record<string, number> = {};
  for (const [source, pct] of Object.entries(headline.generation_share_pct)) {
    const key = toSupplyKey(source);
    shares[key] = (shares[key] ?? 0) + pct;
  }

  return (
    <div className="chart-card">
      <h3>Annual generation share</h3>
      <p className="chart-desc">Share of delivered electricity by source, across the full year.</p>
      <div className="mix-bar">
        {SUPPLY_ORDER.filter((k) => (shares[k] ?? 0) > 0.01).map((key) => (
          <div
            key={key}
            style={{
              width: `${shares[key] ?? 0}%`,
              background: pick(SUPPLY_COLORS[key], dark),
            }}
            title={`${SUPPLY_LABELS[key]}: ${(shares[key] ?? 0).toFixed(1)}%`}
          />
        ))}
      </div>
      <div className="mix-legend">
        {SUPPLY_ORDER.filter((k) => (shares[k] ?? 0) > 0.01).map((key) => (
          <div className="mix-legend-item" key={key}>
            <span className="mix-legend-swatch" style={{ background: pick(SUPPLY_COLORS[key], dark) }} />
            <span>
              {SUPPLY_LABELS[key]} — {(shares[key] ?? 0).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
