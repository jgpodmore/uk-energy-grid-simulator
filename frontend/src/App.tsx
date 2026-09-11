import { useCallback, useEffect, useRef, useState } from "react";
import { fetchDefaults, fetchPresets, simulate } from "./api";
import CarbonChart from "./components/CarbonChart";
import CurtailmentChart from "./components/CurtailmentChart";
import DemandChart from "./components/DemandChart";
import DemandPanel from "./components/DemandPanel";
import GenerationPanel from "./components/GenerationPanel";
import HeadlineStats from "./components/HeadlineStats";
import MixBar from "./components/MixBar";
import PresetBar from "./components/PresetBar";
import ShortfallChart from "./components/ShortfallChart";
import SupplyChart from "./components/SupplyChart";
import type { DefaultsResponse, DemandConfig, GenerationConfig, PresetsResponse, SimulationResponse } from "./types";

export default function App() {
  const [defaults, setDefaults] = useState<DefaultsResponse | null>(null);
  const [presets, setPresets] = useState<PresetsResponse | null>(null);
  const [generation, setGeneration] = useState<GenerationConfig | null>(null);
  const [demand, setDemand] = useState<DemandConfig | null>(null);
  const [activePreset, setActivePreset] = useState<string | null>("current_mix");
  const [result, setResult] = useState<SimulationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [d, p] = await Promise.all([fetchDefaults(), fetchPresets()]);
        setDefaults(d);
        setPresets(p);
        setGeneration(d.generation);
        setDemand(d.demand);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load configuration");
      }
    })();
  }, []);

  const runSimulation = useCallback((gen: GenerationConfig, dem: DemandConfig) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await simulate(gen, dem);
        setResult(res);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Simulation failed");
      } finally {
        setLoading(false);
      }
    }, 200);
  }, []);

  useEffect(() => {
    if (generation && demand) runSimulation(generation, demand);
  }, [generation, demand, runSimulation]);

  const updateGeneration = (field: keyof GenerationConfig, value: number) => {
    setActivePreset(null);
    setGeneration((prev) => (prev ? { ...prev, [field]: value } : prev));
  };

  const updateDemand = (field: keyof DemandConfig, value: number) => {
    setDemand((prev) => (prev ? { ...prev, [field]: value } : prev));
  };

  const selectPreset = (key: string) => {
    if (!presets) return;
    setActivePreset(key);
    setGeneration(presets[key].generation);
  };

  if (!defaults || !generation || !demand) {
    return (
      <div className="main">
        <p>{error ?? "Loading UK grid simulator…"}</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>UK Energy Grid Simulator</h1>
        <p className="subtitle">
          Adjust how much generation comes from each source, and how much each costs, to see whether the mix would
          meet demand across a full year - and what it would cost.
        </p>
        <GenerationPanel generation={generation} meta={defaults.generation_meta} headline={result?.headline ?? null} onChange={updateGeneration} />
        <DemandPanel demand={demand} meta={defaults.demand_meta} onChange={updateDemand} />
      </aside>

      <main className="main">
        <PresetBar presets={presets} activePreset={activePreset} onSelect={selectPreset} />
        {loading && <div className="loading-veil">Simulating…</div>}
        {error && (
          <div className="banner critical">
            <strong>Error:</strong>
            <span>{error}</span>
          </div>
        )}
        {result && (
          <>
            <HeadlineStats headline={result.headline} />
            <MixBar headline={result.headline} />
            <DemandChart daily={result.daily} />
            <SupplyChart daily={result.daily} />
            <ShortfallChart daily={result.daily} />
            <CarbonChart daily={result.daily} />
            <CurtailmentChart daily={result.daily} />
          </>
        )}
      </main>
    </div>
  );
}
