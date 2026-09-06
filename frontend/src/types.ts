export interface GenerationConfig {
  solar_field_gw: number;
  solar_field_price: number;
  solar_roof_gw: number;
  solar_roof_price: number;
  nuclear_gw: number;
  nuclear_price: number;
  wind_onshore_gw: number;
  wind_onshore_price: number;
  wind_offshore_gw: number;
  wind_offshore_price: number;
  gas_gw: number;
  gas_price: number;
  biomass_gw: number;
  biomass_price: number;
  interconnector_france_gw: number;
  interconnector_france_price: number;
  interconnector_norway_gw: number;
  interconnector_norway_price: number;
  interconnector_belgium_gw: number;
  interconnector_belgium_price: number;
  interconnector_netherlands_gw: number;
  interconnector_netherlands_price: number;
  geothermal_gw: number;
  geothermal_price: number;
  tidal_gw: number;
  tidal_price: number;
  morocco_link_gw: number;
  morocco_link_price: number;
  battery_gw: number;
  battery_price: number;
  other_storage_gw: number;
  other_storage_price: number;
}

export interface DemandConfig {
  heat_pump_pct: number;
  ev_pct: number;
  industry_pct: number;
  ac_pct: number;
}

export interface SliderMeta {
  min: number;
  max: number;
  step: number;
  unit: string;
  note?: string;
  cap_note?: string;
}

export interface DefaultsResponse {
  generation: GenerationConfig;
  demand: DemandConfig;
  generation_meta: Record<string, SliderMeta>;
  demand_meta: Record<string, SliderMeta>;
}

export interface PresetInfo {
  label: string;
  description: string;
  generation: GenerationConfig;
}

export type PresetsResponse = Record<string, PresetInfo>;

export interface DailyRecord {
  day: number;
  demand_mwh: number;
  supply_mwh: Record<string, number>;
  storage_charge_mwh: Record<string, number>;
  total_grid_load_mwh: number;
  battery_soc_pct: number;
  other_soc_pct: number;
  curtailment_mwh: Record<string, number>;
  curtailment_total_mwh: number;
  curtailment_payment_gbp: number;
  unmet_demand_mwh: number;
  carbon_intensity_gco2_per_kwh: number;
  cost_gbp: number;
}

export interface Headline {
  total_demand_mwh: number;
  total_delivered_mwh: number;
  total_cost_gbp: number;
  cost_per_mwh: number;
  generation_share_pct: Record<string, number>;
  total_emissions_tonnes: number;
  avg_carbon_intensity_gco2_per_kwh: number;
  total_curtailment_mwh: number;
  total_curtailment_payment_gbp: number;
  total_unmet_demand_mwh: number;
  reliability_ok: boolean;
  offshore_wind_distribution_cost_per_mwh: number;
  offshore_wind_base_price_per_mwh: number;
  gas_electricity_price_per_mwh: number;
  equivalents: {
    nuclear_reactors: number;
    onshore_turbines: number;
    offshore_turbines: number;
    gas_plants: number;
    solar_panels_millions: number;
    tidal_turbines: number;
    geothermal_plants: number;
    morocco_links: number;
  };
}

export interface SimulationResponse {
  daily: DailyRecord[];
  headline: Headline;
}
