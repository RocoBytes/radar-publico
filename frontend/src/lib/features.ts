/**
 * Feature flags para el frontend.
 *
 * Cada flag lee una variable de entorno NEXT_PUBLIC_FEATURE_*.
 * Para activar una feature, configurá la variable en .env.local:
 *   NEXT_PUBLIC_FEATURE_PIPELINE_CHECKLIST=true
 *
 * Los flags son evaluados en build time (Next.js reemplaza las vars
 * NEXT_PUBLIC_* en el bundle). Para cambios en runtime se requiere rebuild.
 */
export const features = {
  /** Checklist documental por pipeline_item (Feature A — operatividad-pipeline) */
  pipelineChecklist:
    process.env.NEXT_PUBLIC_FEATURE_PIPELINE_CHECKLIST === "true",

  /** Alertas de cambio de estado externo desde ChileCompra (Feature B) */
  licitacionStateAlerts:
    process.env.NEXT_PUBLIC_FEATURE_LICITACION_STATE_ALERTS === "true",
} as const;
