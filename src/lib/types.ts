export interface Vessel {
  mmsi: string;
  imo: string;
  name: string;
  ship_type: "crude" | "product";
  lat: number;
  lon: number;
  speed: number;
  course: number;
  draught: number;
  length: number;
  beam: number;
  destination: string;
  destination_parsed: string | null;
  vessel_class: string;
  dwt: number;
  load_factor: number;
  cargo_tonnes: number;
  cargo_litres: number;
  is_ballast: boolean;
  draught_missing: boolean;
  last_update: string;
}

export interface Snapshot {
  timestamp: string;
  vessels: Vessel[];
}

export interface Arrival {
  imo: string;
  name: string;
  port: string;
  timestamp: string;
  ship_type: "crude" | "product";
  vessel_class: string;
  cargo_tonnes: number;
  cargo_litres: number;
  draught_missing: boolean;
}

export interface MonthEstimate {
  arrived_crude_litres: number;
  arrived_product_litres: number;
  arrived_crude_tonnes: number;
  arrived_product_tonnes: number;
  en_route_crude_litres: number;
  en_route_product_litres: number;
  arrival_count: number;
  last_updated: string;
}

export interface MonthlyEstimates {
  months: Record<string, MonthEstimate>;
}

export interface ImportRecord {
  month: string;
  crude_oil_ml: number;
  lpg_ml: number;
  gasoline_ml: number;
  jet_fuel_ml: number;
  diesel_ml: number;
  fuel_oil_ml: number;
  total_ml: number;
}

export interface ConsumptionRecord {
  month: string;
  crude_days: number;
  gasoline_days: number;
  jet_fuel_days: number;
  diesel_days: number;
  total_days: number;
}

export interface ImportsData {
  imports_by_month: ImportRecord[];
  consumption_cover: ConsumptionRecord[];
}

export interface DashboardData {
  snapshot: Snapshot;
  arrivals: Arrival[];
  monthlyEstimates: MonthlyEstimates;
  imports: ImportsData;
}
