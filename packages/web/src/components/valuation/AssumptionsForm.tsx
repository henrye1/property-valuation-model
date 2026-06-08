/**
 * AssumptionsForm — the Assumptions section of the Valuation Editor.
 *
 * Covers: valuation_date, monthly_operating_expenses, vacancy_allowance_pct,
 * cap_rate, and rounding.
 *
 * Defined at module top-level to prevent remounting on parent re-renders.
 * Inline WarningChips are shown for cap_rate, vacancy_allowance_pct, and
 * monthly_operating_expenses fields when the live /calculate result returns
 * matching warnings.
 */
import type { UseFormRegister, FieldErrors, Control } from 'react-hook-form'
import { Controller } from 'react-hook-form'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { FormField } from '@/components/forms/FormField'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Warning } from '@/schemas/valuation'
import { WarningChip } from './WarningChip'
import type { ValuationFormValues } from './valuation-form-types'

interface AssumptionsFormProps {
  register: UseFormRegister<ValuationFormValues>
  control: Control<ValuationFormValues>
  errors: FieldErrors<ValuationFormValues>
  /** All warnings from the live result — we filter to the relevant field paths */
  warnings: Warning[]
}

function fieldWarnings(warnings: Warning[], fieldPath: string): Warning[] {
  return warnings.filter((w) => w.field_path === fieldPath)
}

const ROUNDING_LABELS: Record<string, string> = {
  nearest_10000: 'Nearest R10 000',
  nearest_1000: 'Nearest R1 000',
  none: 'None',
}

export function AssumptionsForm({ register, control, errors, warnings }: AssumptionsFormProps) {
  const capRateWarnings = fieldWarnings(warnings, 'cap_rate')
  const vacancyWarnings = fieldWarnings(warnings, 'vacancy_allowance_pct')
  const opexWarnings = fieldWarnings(warnings, 'monthly_operating_expenses')

  return (
    <Card>
      <CardHeader>
        <CardTitle>Assumptions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Valuation date */}
        <FormField
          label="Valuation date"
          htmlFor="valuation_date"
          error={errors.valuation_date?.message}
          required
        >
          <Input
            id="valuation_date"
            type="date"
            {...register('valuation_date')}
            aria-invalid={!!errors.valuation_date}
          />
        </FormField>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Monthly operating expenses */}
          <FormField
            label="Monthly operating expenses (R)"
            htmlFor="monthly_operating_expenses"
            error={errors.monthly_operating_expenses?.message}
            required
          >
            <div>
              <Input
                id="monthly_operating_expenses"
                inputMode="decimal"
                placeholder="e.g. 50000"
                {...register('monthly_operating_expenses')}
                aria-invalid={!!errors.monthly_operating_expenses}
              />
              {opexWarnings.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {opexWarnings.map((w, i) => <WarningChip key={i} warning={w} />)}
                </div>
              )}
            </div>
          </FormField>

          {/* Vacancy allowance */}
          <FormField
            label="Vacancy allowance (as decimal, e.g. 0.05)"
            htmlFor="vacancy_allowance_pct"
            error={errors.vacancy_allowance_pct?.message}
            required
          >
            <div>
              <Input
                id="vacancy_allowance_pct"
                inputMode="decimal"
                placeholder="e.g. 0.05"
                {...register('vacancy_allowance_pct')}
                aria-invalid={!!errors.vacancy_allowance_pct}
              />
              {vacancyWarnings.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {vacancyWarnings.map((w, i) => <WarningChip key={i} warning={w} />)}
                </div>
              )}
            </div>
          </FormField>

          {/* Cap rate */}
          <FormField
            label="Capitalisation rate (as decimal, e.g. 0.115)"
            htmlFor="cap_rate"
            error={errors.cap_rate?.message}
            required
          >
            <div>
              <Input
                id="cap_rate"
                inputMode="decimal"
                placeholder="e.g. 0.115"
                {...register('cap_rate')}
                aria-invalid={!!errors.cap_rate}
              />
              {capRateWarnings.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {capRateWarnings.map((w, i) => <WarningChip key={i} warning={w} />)}
                </div>
              )}
            </div>
          </FormField>

          {/* Rounding — base-ui Select, controlled via Controller */}
          <FormField
            label="Rounding"
            htmlFor="rounding"
            error={errors.rounding?.message}
          >
            <Controller
              name="rounding"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="rounding" className="w-full">
                    <SelectValue placeholder="Select rounding" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ROUNDING_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>
        </div>
      </CardContent>
    </Card>
  )
}
