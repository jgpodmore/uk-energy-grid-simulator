import { useState } from "react";
import { SUPPLY_LABELS, SUPPLY_ORDER, toSupplyKey } from "../colors";
import type { Headline } from "../types";

function buildShareText(headline: Headline): string {
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
    "UK Energy Grid Simulator - my mix for the year:",
    `Cost: £${headline.cost_per_mwh.toFixed(1)}/MWh (£${(headline.total_cost_gbp / 1_000_000_000).toFixed(2)}bn/yr total)`,
    `Emissions: ${(headline.total_emissions_tonnes / 1_000_000).toFixed(1)} MtCO2 (${headline.avg_carbon_intensity_gco2_per_kwh.toFixed(0)} gCO2/kWh average)`,
    `Curtailment payments: £${(headline.total_curtailment_payment_gbp / 1_000_000).toFixed(1)}m/yr`,
    `Produced: ${(headline.total_delivered_mwh / 1_000_000).toFixed(1)} TWh/yr, Consumed: ${(headline.total_demand_mwh / 1_000_000).toFixed(1)} TWh/yr`,
    demandMetLine,
    `Generation mix: ${mixLine}`,
  ].join("\n");
}

type ShareState = "idle" | "copied" | "error";

export default function ShareResultsButton({ headline }: { headline: Headline }) {
  const [state, setState] = useState<ShareState>("idle");

  const handleClick = async () => {
    const text = buildShareText(headline);
    const url = window.location.href;

    if (navigator.share) {
      try {
        await navigator.share({ title: "UK Energy Grid Simulator results", text, url });
        return;
      } catch (e) {
        // AbortError just means the user dismissed the native share sheet -
        // not a failure worth falling back from.
        if (e instanceof DOMException && e.name === "AbortError") return;
      }
    }

    try {
      await navigator.clipboard.writeText(`${text}\n\n${url}`);
      setState("copied");
    } catch {
      setState("error");
    } finally {
      setTimeout(() => setState("idle"), 2500);
    }
  };

  const label = state === "copied" ? "Copied to clipboard!" : state === "error" ? "Couldn't copy - try again" : "Share results";

  return (
    <button type="button" className="share-btn" onClick={handleClick}>
      {label}
    </button>
  );
}
