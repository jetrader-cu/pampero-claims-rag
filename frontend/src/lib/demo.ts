/** Claves fijas que crea `make seed` (scripts/seed.py). Solo valen en local. */
export interface DemoPreset {
  apiKey: string;
  tenantName: string;
  hint: string;
}

export const DEMO_PRESETS: DemoPreset[] = [
  {
    apiKey: "pampero_key_demo_norte",
    tenantName: "Pampero Norte Seguros",
    hint: "ajustador-norte@pampero.local",
  },
  {
    apiKey: "pampero_key_demo_sur",
    tenantName: "Pampero Sur Seguros",
    hint: "ajustador-sur@pampero.local",
  },
];
