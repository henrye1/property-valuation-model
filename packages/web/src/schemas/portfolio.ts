import { z } from 'zod'
import { PropertyTypeSchema } from './property'

// Mirrors api/schemas/portfolio.py
// Reference guessed by_type/by_entity — real field names are value_by_type/value_by_entity
// Decimal fields (value) serialised as strings on the wire

export const ValueByTypeSchema = z.object({
  type: PropertyTypeSchema,
  value: z.string(),
  count: z.number().int(),
})
export type ValueByType = z.infer<typeof ValueByTypeSchema>

export const ValueByEntitySchema = z.object({
  entity_id: z.string(),
  name: z.string(),
  value: z.string(),
  count: z.number().int(),
})
export type ValueByEntity = z.infer<typeof ValueByEntitySchema>

export const TopPropertySchema = z.object({
  property_id: z.string(),
  name: z.string(),
  value: z.string(),
})
export type TopProperty = z.infer<typeof TopPropertySchema>

export const PortfolioSummarySchema = z.object({
  total_market_value: z.string(),
  property_count: z.number().int(),
  entity_count: z.number().int(),
  last_snapshot_date: z.string().nullable(),
  value_by_type: z.array(ValueByTypeSchema),
  value_by_entity: z.array(ValueByEntitySchema),
  top_properties: z.array(TopPropertySchema),
})
export type PortfolioSummary = z.infer<typeof PortfolioSummarySchema>

export const TimeseriesPointSchema = z.object({
  bucket_date: z.string(),
  total_market_value: z.string(),
  property_count: z.number().int(),
})
export type TimeseriesPoint = z.infer<typeof TimeseriesPointSchema>

export const PortfolioTimeseriesSchema = z.object({
  bucket: z.string(),
  points: z.array(TimeseriesPointSchema),
})
export type PortfolioTimeseries = z.infer<typeof PortfolioTimeseriesSchema>
