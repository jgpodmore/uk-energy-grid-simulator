import type { DefaultsResponse, DemandConfig, GenerationConfig, PresetsResponse, SimulationResponse } from "./types";

const BASE = "/api";

export async function fetchDefaults(): Promise<DefaultsResponse> {
  const res = await fetch(`${BASE}/defaults`);
  if (!res.ok) throw new Error("Failed to load defaults");
  return res.json();
}

export async function fetchPresets(): Promise<PresetsResponse> {
  const res = await fetch(`${BASE}/presets`);
  if (!res.ok) throw new Error("Failed to load presets");
  return res.json();
}

export async function simulate(generation: GenerationConfig, demand: DemandConfig): Promise<SimulationResponse> {
  const res = await fetch(`${BASE}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ generation, demand }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Simulation failed: ${text}`);
  }
  return res.json();
}
