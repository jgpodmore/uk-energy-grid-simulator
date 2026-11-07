import type { LatitudePresetInfo } from "../types";

interface Props {
  value: number;
  presets: Record<string, LatitudePresetInfo>;
  solarMultiplier: number | null;
  heatingMultiplier: number | null;
  acMultiplier: number | null;
  onChange: (value: number) => void;
}

const ACTUAL_KEY = "actual";

export default function LatitudeToggle({ value, presets, solarMultiplier, heatingMultiplier, acMultiplier, onChange }: Props) {
  const activeKey = Object.entries(presets).find(([, p]) => Math.abs(p.value - value) < 0.01)?.[0] ?? null;
  const isActual = activeKey === ACTUAL_KEY || activeKey === null;

  return (
    <div className="slider-row">
      <div className="slider-row-label">
        <span className="name">Latitude</span>
      </div>
      <div className="preset-bar" style={{ marginBottom: 4 }}>
        {Object.entries(presets).map(([key, preset]) => (
          <button
            key={key}
            className={`preset-btn${activeKey === key ? " active" : ""}`}
            title={preset.sublabel}
            onClick={() => onChange(preset.value)}
          >
            {key === ACTUAL_KEY ? "↺ " : ""}
            {preset.label}
          </button>
        ))}
      </div>
      <div className="slider-note">
        {presets[activeKey ?? ""]?.sublabel ?? `${value}°N`}
        {" - also scales heating and air-conditioning demand (sunnier/lower latitude = milder winters, hotter summers)"}
        {!isActual && solarMultiplier != null && (
          <>
            <br />
            solar ×{solarMultiplier.toFixed(2)}
            {heatingMultiplier != null && `, heating ×${heatingMultiplier.toFixed(2)}`}
            {acMultiplier != null && `, AC ×${acMultiplier.toFixed(2)}`}
            {" from latitude alone (weather unchanged)"}
          </>
        )}
      </div>
    </div>
  );
}
