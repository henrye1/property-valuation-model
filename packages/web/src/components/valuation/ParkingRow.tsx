/**
 * ParkingRow — a single row in the parking useFieldArray.
 *
 * Defined at module top-level (NOT as a nested closure) to prevent remounting
 * on parent re-renders and consequent focus loss.
 *
 * bay_type is a Select (controlled via Controller).
 * bays is an integer number input (the only numeric field in the form).
 * rate_per_bay_pm is a string text input.
 */
import type { UseFormRegister, FieldErrors, Control } from 'react-hook-form'
import { Controller } from 'react-hook-form'
import { Trash2 } from 'lucide-react'
import { FormField } from '@/components/forms/FormField'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ValuationFormValues } from './valuation-form-types'

interface ParkingRowProps {
  index: number
  register: UseFormRegister<ValuationFormValues>
  control: Control<ValuationFormValues>
  errors: FieldErrors<ValuationFormValues>
  remove: (index: number) => void
}

const BAY_TYPE_LABELS: Record<string, string> = {
  open: 'Open',
  covered: 'Covered',
  shade: 'Shade',
  basement: 'Basement',
  other: 'Other',
}

export function ParkingRow({ index, register, control, errors, remove }: ParkingRowProps) {
  const prefix = `parking.${index}` as const
  const parkingErrors = errors.parking?.[index]

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-muted-foreground">Parking {index + 1}</span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => remove(index)}
          aria-label={`Remove parking row ${index + 1}`}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {/* bay_type — base-ui Select, controlled via Controller */}
        <FormField
          label="Bay type"
          htmlFor={`${prefix}-bay_type`}
          error={parkingErrors?.bay_type?.message}
          required
        >
          <Controller
            name={`${prefix}.bay_type`}
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id={`${prefix}-bay_type`} className="w-full">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(BAY_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>

        {/* bays — integer number input */}
        <FormField
          label="Number of bays"
          htmlFor={`${prefix}-bays`}
          error={parkingErrors?.bays?.message}
          required
        >
          <Input
            id={`${prefix}-bays`}
            type="number"
            inputMode="numeric"
            min={0}
            step={1}
            placeholder="e.g. 10"
            {...register(`${prefix}.bays`, { valueAsNumber: true })}
            aria-invalid={!!parkingErrors?.bays}
          />
        </FormField>

        {/* rate_per_bay_pm — decimal string */}
        <FormField
          label="Rate (R/bay/pm)"
          htmlFor={`${prefix}-rate_per_bay_pm`}
          error={parkingErrors?.rate_per_bay_pm?.message}
          required
        >
          <Input
            id={`${prefix}-rate_per_bay_pm`}
            inputMode="decimal"
            placeholder="e.g. 800"
            {...register(`${prefix}.rate_per_bay_pm`)}
            aria-invalid={!!parkingErrors?.rate_per_bay_pm}
          />
        </FormField>
      </div>
    </div>
  )
}
