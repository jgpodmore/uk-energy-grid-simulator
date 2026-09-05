// Categorical palette (validated, fixed order - see dataviz skill reference).
// Each entity keeps the same slot everywhere in the app.
export type SupplyKey =
  | "solar"
  | "nuclear"
  | "wind_onshore"
  | "wind_offshore"
  | "gas"
  | "biomass"
  | "interconnectors"
  | "storage";

interface ColorPair {
  light: string;
  dark: string;
}

export const SUPPLY_COLORS: Record<SupplyKey, ColorPair> = {
  solar: { light: "#2a78d6", dark: "#3987e5" },
  nuclear: { light: "#eb6834", dark: "#d95926" },
  wind_onshore: { light: "#1baf7a", dark: "#199e70" },
  wind_offshore: { light: "#eda100", dark: "#c98500" },
  gas: { light: "#e87ba4", dark: "#d55181" },
  biomass: { light: "#008300", dark: "#008300" },
  interconnectors: { light: "#4a3aa7", dark: "#9085e9" },
  storage: { light: "#e34948", dark: "#e66767" },
};

export const SUPPLY_LABELS: Record<SupplyKey, string> = {
  solar: "Solar",
  nuclear: "Nuclear",
  wind_onshore: "Wind (onshore)",
  wind_offshore: "Wind (offshore)",
  gas: "Gas",
  biomass: "Biomass",
  interconnectors: "Interconnectors",
  storage: "Storage discharge",
};

export const SUPPLY_ORDER: SupplyKey[] = [
  "solar",
  "nuclear",
  "wind_onshore",
  "wind_offshore",
  "gas",
  "biomass",
  "interconnectors",
  "storage",
];

export const SEQUENTIAL_BLUE = { light: "#256abf", dark: "#3987e5" };

export const CHROME = {
  light: {
    surface: "#fcfcfb",
    page: "#f9f9f7",
    textPrimary: "#0b0b0b",
    textSecondary: "#52514e",
    muted: "#898781",
    grid: "#e1e0d9",
    baseline: "#c3c2b7",
  },
  dark: {
    surface: "#1a1a19",
    page: "#0d0d0d",
    textPrimary: "#ffffff",
    textSecondary: "#c3c2b7",
    muted: "#898781",
    grid: "#2c2c2a",
    baseline: "#383835",
  },
};

export const STATUS = {
  good: "#0ca30c",
  warning: "#fab219",
  serious: "#ec835a",
  critical: "#d03b3b",
};

export function useIsDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function pick(pair: ColorPair, dark: boolean): string {
  return dark ? pair.dark : pair.light;
}

// Maps the backend's fine-grained source keys onto the 8 chart categories.
export function toSupplyKey(sourceKey: string): SupplyKey {
  if (sourceKey.startsWith("solar")) return "solar";
  if (sourceKey === "nuclear") return "nuclear";
  if (sourceKey === "wind_onshore") return "wind_onshore";
  if (sourceKey === "wind_offshore") return "wind_offshore";
  if (sourceKey === "gas") return "gas";
  if (sourceKey === "biomass") return "biomass";
  if (sourceKey.startsWith("interconnector")) return "interconnectors";
  if (sourceKey === "battery" || sourceKey === "other_storage") return "storage";
  return "gas";
}
