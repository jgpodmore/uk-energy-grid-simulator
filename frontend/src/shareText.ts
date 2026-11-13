import { SUPPLY_LABELS, SUPPLY_ORDER, toSupplyKey } from "./colors";
import { DEMAND_FIELD_ORDER, DEMAND_LABELS, GENERATION_FIELD_ORDER, GENERATION_LABELS } from "./sliderLabels";
import type { DemandConfig, GenerationConfig, Headline, SliderMeta } from "./types";

function buildHeadlineLines(headline: Headline): string[] {
  const demandMetLine = headline.reliability_ok
    ? "Demand met: fully met across the year"
    : `Demand met: shortfall of ${(headline.total_unmet_demand_mwh / 1000).toFixed(1)} GWh across ${headline.days_with_shortfall} day${headline.days_with_shortfall === 1 ? "" : "s"}`;

  const shares: Record<string, number> = {};
  for (const [source, pct] of Object.entries(headline.generation_share_pct)) {
    const key = toSupplyKey(source);
    shares[key] = (shares[key] ?? 0) + pct;
  }
  const mixLine = SUPPLY_ORDER.filter((key) => (shares[key] ?? 0) > 0.01)
    .map((key) => `${SUPPLY_LABELS[key]} ${(shares[key] ?? 0).toFixed(1)}%`)
    .join(", ");

  return [
    `Cost: £${headline.cost_per_mwh.toFixed(1)}/MWh (£${(headline.total_cost_gbp / 1_000_000_000).toFixed(2)}bn/yr total)`,
    `Emissions: ${(headline.total_emissions_tonnes / 1_000_000).toFixed(1)} MtCO2 (${headline.avg_carbon_intensity_gco2_per_kwh.toFixed(0)} gCO2/kWh average)`,
    `Curtailment payments: £${(headline.total_curtailment_payment_gbp / 1_000_000).toFixed(1)}m/yr`,
    `Produced: ${(headline.total_delivered_mwh / 1_000_000).toFixed(1)} TWh/yr, Consumed: ${(headline.total_demand_mwh / 1_000_000).toFixed(1)} TWh/yr`,
    demandMetLine,
    `Generation mix: ${mixLine}`,
  ];
}

function formatSliderValue(value: number, meta: SliderMeta | undefined): string {
  // Match the slider's own step precision (e.g. 0.5 GW steps show one
  // decimal place) rather than always showing whole numbers.
  const decimals = meta && !Number.isInteger(meta.step) ? 1 : 0;
  const unit = meta?.unit ?? "";
  return `${value.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;
}

function buildInputLines(
  fieldOrder: string[],
  labels: Record<string, string>,
  values: Record<string, number>,
  meta: Record<string, SliderMeta>,
): string[] {
  return fieldOrder.map((field) => `${labels[field]}: ${formatSliderValue(values[field], meta[field])}`);
}

export function buildHeadlineShareText(headline: Headline): string {
  return ["UK Energy Grid Simulator - my mix for the year:", ...buildHeadlineLines(headline)].join("\n");
}

export function buildFullShareText(
  headline: Headline,
  generation: GenerationConfig,
  demand: DemandConfig,
  generationMeta: Record<string, SliderMeta>,
  demandMeta: Record<string, SliderMeta>,
): string {
  return [
    "UK Energy Grid Simulator - my full scenario for the year:",
    ...buildHeadlineLines(headline),
    "",
    "Generation inputs:",
    ...buildInputLines(GENERATION_FIELD_ORDER, GENERATION_LABELS, generation as unknown as Record<string, number>, generationMeta),
    "",
    "Demand inputs:",
    ...buildInputLines(DEMAND_FIELD_ORDER, DEMAND_LABELS, demand as unknown as Record<string, number>, demandMeta),
  ].join("\n");
}
