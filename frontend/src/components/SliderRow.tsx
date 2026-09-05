import type { SliderMeta } from "../types";

interface Props {
  label: string;
  value: number;
  meta: SliderMeta;
  onChange: (value: number) => void;
  formatValue?: (value: number) => string;
}

export default function SliderRow({ label, value, meta, onChange, formatValue }: Props) {
  const display = formatValue ? formatValue(value) : `${value} ${meta.unit}`;
  return (
    <div className="slider-row">
      <div className="slider-row-label">
        <span className="name">{label}</span>
        <span className="value">{display}</span>
      </div>
      <input
        type="range"
        min={meta.min}
        max={meta.max}
        step={meta.step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
      {(meta.note || meta.cap_note) && <div className="slider-note">{meta.note ?? meta.cap_note}</div>}
    </div>
  );
}
