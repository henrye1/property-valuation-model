import { z } from 'zod'

// Mirrors valuation_engine/src/valuation_engine/models.py
// All money/rate fields are Decimal in Python, serialised as strings across the API.

export const BayTypeSchema = z.enum(['open', 'covered', 'shade', 'basement', 'other'])
export type BayType = z.infer<typeof BayTypeSchema>

export const RoundingSchema = z.enum(['nearest_10000', 'nearest_1000', 'none'])
export type Rounding = z.infer<typeof RoundingSchema>

// TenantLine: description required; tenant_name nullable; decimals as strings; dates as ISO strings
export const TenantLineSchema = z.object({
  description: z.string(),
  tenant_name: z.string().nullable().optional(),
  rentable_area_m2: z.string(),
  rent_per_m2_pm: z.string(),
  annual_escalation_pct: z.string(),
  next_escalation_date: z.string().nullable().optional(),
  lease_period_text: z.string().nullable().optional(),
  lease_expiry_date: z.string().nullable().optional(),
})
export type TenantLine = z.infer<typeof TenantLineSchema>

export const ParkingLineSchema = z.object({
  bay_type: BayTypeSchema,
  bays: z.number().int(),
  rate_per_bay_pm: z.string(),
})
export type ParkingLine = z.infer<typeof ParkingLineSchema>

export const ValuationInputSchema = z.object({
  valuation_date: z.string(),
  tenants: z.array(TenantLineSchema).min(1),
  parking: z.array(ParkingLineSchema).default([]),
  monthly_operating_expenses: z.string(),
  vacancy_allowance_pct: z.string(),
  cap_rate: z.string(),
  rounding: RoundingSchema.default('nearest_10000'),
})
export type ValuationInput = z.infer<typeof ValuationInputSchema>

// ResolvedTenant: all decimal fields as strings
export const ResolvedTenantSchema = z.object({
  description: z.string(),
  rentable_area_m2: z.string(),
  effective_rent_per_m2_pm: z.string(),
  monthly_rent: z.string(),
  escalation_cycles_applied: z.number().int(),
})
export type ResolvedTenant = z.infer<typeof ResolvedTenantSchema>

// Real engine model: ValuationWarning (not Warning) — exported as WarningSchema for API consumers
export const WarningSchema = z.object({
  code: z.string(),
  message: z.string(),
  field_path: z.string().nullable().optional(),
})
export type Warning = z.infer<typeof WarningSchema>

export const ValuationResultSchema = z.object({
  engine_version: z.string(),
  valuation_date: z.string(),
  tenants_resolved: z.array(ResolvedTenantSchema),
  gross_monthly_rent_tenants: z.string(),
  gross_monthly_rent_parking: z.string(),
  gross_monthly_income: z.string(),
  gross_annual_income: z.string(),
  annual_operating_expenses: z.string(),
  opex_per_m2_pm: z.string(),
  opex_pct_of_gai: z.string(),
  vacancy_allowance_amount: z.string(),
  annual_net_income: z.string(),
  capitalised_value: z.string(),
  market_value: z.string(),
  warnings: z.array(WarningSchema),
})
export type ValuationResult = z.infer<typeof ValuationResultSchema>
