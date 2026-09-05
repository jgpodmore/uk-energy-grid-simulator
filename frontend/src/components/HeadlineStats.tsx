import type { Headline } from "../types";

function fmtNumber(n: number, digits = 0): string {
  return n.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export default function HeadlineStats({ headline }: { headline: Headline }) {
  const eq = headline.equivalents;
  return (
    <>
      {!headline.reliability_ok && (
        <div className="banner critical">
          <strong>⚠ Demand not met.</strong>
          <span>
            This mix falls short of demand for {fmtNumber(headline.total_unmet_demand_mwh / 1000, 1)} GWh across the
            year — add more dispatchable generation, storage, or interconnector capacity.
          </span>
        </div>
      )}
      {headline.reliability_ok && (
        <div className="banner good">
          <strong>✓ Demand met.</strong>
          <span>This mix covers demand in every 12-hour period across the year.</span>
        </div>
      )}

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label">Total system cost</div>
          <div className="value">£{fmtNumber(headline.cost_per_mwh, 1)}/MWh</div>
          <div className="sub">£{fmtNumber(headline.total_cost_gbp / 1_000_000_000, 2)}bn/yr total</div>
        </div>
        <div className="stat-card">
          <div className="label">Annual emissions</div>
          <div className="value">{fmtNumber(headline.total_emissions_tonnes / 1_000_000, 1)} MtCO₂</div>
          <div className="sub">{fmtNumber(headline.avg_carbon_intensity_gco2_per_kwh, 0)} gCO₂/kWh average</div>
        </div>
        <div className="stat-card">
          <div className="label">Curtailment payments</div>
          <div className="value">£{fmtNumber(headline.total_curtailment_payment_gbp / 1_000_000, 1)}m/yr</div>
          <div className="sub">{fmtNumber(headline.total_curtailment_mwh / 1000, 0)} GWh curtailed</div>
        </div>
        <div className="stat-card">
          <div className="label">Demand served</div>
          <div className="value">{fmtNumber(headline.total_demand_mwh / 1_000_000, 0)} TWh/yr</div>
          <div className="sub">{headline.reliability_ok ? "fully met" : "shortfall present"}</div>
        </div>
      </div>

      <div className="equivalents">
        <span>≈ {fmtNumber(eq.nuclear_reactors, 1)} × 1.2GW nuclear reactors</span>
        <span>≈ {fmtNumber(eq.onshore_turbines)} onshore turbines</span>
        <span>≈ {fmtNumber(eq.offshore_turbines)} offshore turbines</span>
        <span>≈ {fmtNumber(eq.gas_plants, 1)} × 800MW gas plants</span>
        <span>≈ {fmtNumber(eq.solar_panels_millions, 1)}m solar panels</span>
      </div>
    </>
  );
}
