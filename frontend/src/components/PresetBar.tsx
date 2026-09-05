import type { PresetsResponse } from "../types";

interface Props {
  presets: PresetsResponse | null;
  activePreset: string | null;
  onSelect: (key: string) => void;
}

export default function PresetBar({ presets, activePreset, onSelect }: Props) {
  if (!presets) return null;
  const active = activePreset ? presets[activePreset] : null;
  return (
    <div>
      <div className="preset-bar">
        {Object.entries(presets).map(([key, preset]) => (
          <button
            key={key}
            className={`preset-btn${activePreset === key ? " active" : ""}`}
            onClick={() => onSelect(key)}
            title={preset.description}
          >
            {preset.label}
          </button>
        ))}
      </div>
      {active && <p className="preset-desc">{active.description}</p>}
    </div>
  );
}
