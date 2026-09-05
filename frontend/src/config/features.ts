/** Features that require infrastructure or workflows not enabled in this deployment. */
export const features = {
  globalSearch: false,
  productCreation: true,
  locationCreation: false,
  employeeCreation: false,
  invoiceCreation: false,
  directPrinting: false,
  stockAuditMutation: false,
  barcodeLabelPdf: false,
} as const;

export type Feature = keyof typeof features;
