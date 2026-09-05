import type { DemandConfig, SliderMeta } from "../types";
import SliderRow from "./SliderRow";

interface Props {
  demand: DemandConfig;
  meta: Record<string, SliderMeta>;
  onChange: (field: keyof DemandConfig, value: number) => void;
}

export default function DemandPanel({ demand, meta, onChange }: Props) {
  return (
    <div className="panel-group">
      <h2>Demand</h2>
      <SliderRow
        label="Heat pumps replacing boilers"
        value={demand.heat_pump_pct}
        meta={meta.heat_pump_pct}
        onChange={(v) => onChange("heat_pump_pct", v)}
      />
      <SliderRow
        label="Electrify cars / transport"
        value={demand.ev_pct}
        meta={meta.ev_pct}
        onChange={(v) => onChange("ev_pct", v)}
      />
      <SliderRow
        label="Electrify industry"
        value={demand.industry_pct}
        meta={meta.industry_pct}
        onChange={(v) => onChange("industry_pct", v)}
      />
      <SliderRow
        label="Air conditioning adoption"
        value={demand.ac_pct}
        meta={meta.ac_pct}
        onChange={(v) => onChange("ac_pct", v)}
      />
    </div>
  );
}
