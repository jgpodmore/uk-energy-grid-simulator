import type { GenerationConfig, Headline, SliderMeta } from "../types";
import SliderRow from "./SliderRow";

interface Props {
  generation: GenerationConfig;
  meta: Record<string, SliderMeta>;
  headline: Headline | null;
  onChange: (field: keyof GenerationConfig, value: number) => void;
}

function Field({
  field,
  label,
  generation,
  meta,
  onChange,
}: {
  field: keyof GenerationConfig;
  label: string;
  generation: GenerationConfig;
  meta: Record<string, SliderMeta>;
  onChange: (field: keyof GenerationConfig, value: number) => void;
}) {
  return (
    <SliderRow
      label={label}
      value={generation[field]}
      meta={meta[field]}
      onChange={(v) => onChange(field, v)}
    />
  );
}

export default function GenerationPanel({ generation, meta, headline, onChange }: Props) {
  return (
    <>
      <div className="panel-group">
        <h2>Solar</h2>
        <Field field="solar_field_gw" label="Field (utility-scale) capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="solar_field_price" label="Field cost" generation={generation} meta={meta} onChange={onChange} />
        <Field field="solar_roof_gw" label="Rooftop capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="solar_roof_price" label="Rooftop cost" generation={generation} meta={meta} onChange={onChange} />
      </div>

      <div className="panel-group">
        <h2>Nuclear</h2>
        <Field field="nuclear_gw" label="Capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="nuclear_price" label="Cost" generation={generation} meta={meta} onChange={onChange} />
      </div>

      <div className="panel-group">
        <h2>Wind</h2>
        <Field field="wind_onshore_gw" label="Onshore capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="wind_onshore_price" label="Onshore cost" generation={generation} meta={meta} onChange={onChange} />
        <Field field="wind_offshore_gw" label="Offshore capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="wind_offshore_price" label="Offshore cost (before grid)" generation={generation} meta={meta} onChange={onChange} />
        {headline && (
          <div className="slider-note">
            + £{headline.offshore_wind_distribution_cost_per_mwh}/MWh grid distribution cost (rises with offshore
            capacity) = £{(headline.offshore_wind_base_price_per_mwh + headline.offshore_wind_distribution_cost_per_mwh).toFixed(1)}/MWh total
          </div>
        )}
      </div>

      <div className="panel-group">
        <h2>Gas &amp; biomass</h2>
        <Field field="gas_gw" label="Gas capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="gas_price" label="Gas commodity price" generation={generation} meta={meta} onChange={onChange} />
        {headline && (
          <div className="slider-note">-&gt; £{headline.gas_electricity_price_per_mwh}/MWh electricity (50% plant efficiency + £8/MWh O&amp;M)</div>
        )}
        <Field field="biomass_gw" label="Biomass capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="biomass_price" label="Biomass cost" generation={generation} meta={meta} onChange={onChange} />
      </div>

      <div className="panel-group">
        <h2>Interconnectors</h2>
        <Field field="interconnector_france_gw" label="France capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="interconnector_france_price" label="France price" generation={generation} meta={meta} onChange={onChange} />
        <Field field="interconnector_norway_gw" label="Norway capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="interconnector_norway_price" label="Norway price" generation={generation} meta={meta} onChange={onChange} />
        <Field field="interconnector_belgium_gw" label="Belgium capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="interconnector_belgium_price" label="Belgium price" generation={generation} meta={meta} onChange={onChange} />
        <Field field="interconnector_netherlands_gw" label="Netherlands capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="interconnector_netherlands_price" label="Netherlands price" generation={generation} meta={meta} onChange={onChange} />
      </div>

      <div className="panel-group">
        <h2>Emerging &amp; other</h2>
        <Field field="geothermal_gw" label="Enhanced geothermal capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="geothermal_price" label="Enhanced geothermal cost" generation={generation} meta={meta} onChange={onChange} />
        <Field field="tidal_gw" label="Tidal power capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="tidal_price" label="Tidal power cost" generation={generation} meta={meta} onChange={onChange} />
        <Field field="morocco_link_gw" label="Morocco solar link capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="morocco_link_price" label="Morocco solar link cost" generation={generation} meta={meta} onChange={onChange} />
      </div>

      <div className="panel-group">
        <h2>Storage</h2>
        <Field field="battery_gw" label="Battery power capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="battery_price" label="Battery throughput cost" generation={generation} meta={meta} onChange={onChange} />
        <Field field="other_storage_gw" label="Pumped hydro / multiday power capacity" generation={generation} meta={meta} onChange={onChange} />
        <Field field="other_storage_price" label="Pumped hydro / multiday throughput cost" generation={generation} meta={meta} onChange={onChange} />
      </div>
    </>
  );
}
