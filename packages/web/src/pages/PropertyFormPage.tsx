import { useEffect } from 'react'
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { FormField } from '@/components/forms/FormField'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter } from '@/components/ui/card'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select'
import { useProperty } from '@/hooks/useProperties'
import { useEntities } from '@/hooks/useEntities'
import { useCreateProperty, useUpdateProperty } from '@/hooks/usePropertyMutations'
import { PropertyTypeSchema } from '@/schemas/property'
import type { PropertyType } from '@/schemas/property'

const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  office: 'Office',
  retail: 'Retail',
  industrial: 'Industrial',
  mixed: 'Mixed',
  residential: 'Residential',
  other: 'Other',
}

const PROPERTY_TYPES = PropertyTypeSchema.options

const schema = z.object({
  entity_id: z.string().min(1, 'Entity is required'),
  name: z.string().min(1, 'Name is required'),
  address: z.string().optional().or(z.literal('')),
  property_type: PropertyTypeSchema,
  notes: z.string().optional().or(z.literal('')),
})

type FormValues = z.infer<typeof schema>

function emptyToNull(val: string | undefined): string | null {
  return val === '' || val === undefined ? null : val
}

export default function PropertyFormPage() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const createMutation = useCreateProperty()
  const updateMutation = useUpdateProperty()

  const { isPending, error, data: property } = useProperty(id ?? '')
  const { data: entities } = useEntities()

  const preselectedEntityId = searchParams.get('entity_id') ?? ''

  const {
    register,
    handleSubmit,
    reset,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      entity_id: preselectedEntityId,
      name: '',
      address: '',
      property_type: 'office',
      notes: '',
    },
  })

  useEffect(() => {
    if (property) {
      reset({
        entity_id: property.entity_id,
        name: property.name,
        address: property.address ?? '',
        property_type: property.property_type,
        notes: property.notes ?? '',
      })
    }
  }, [property, reset])

  async function onSubmit(values: FormValues) {
    const payload = {
      entity_id: values.entity_id,
      name: values.name,
      property_type: values.property_type,
      address: emptyToNull(values.address),
      notes: emptyToNull(values.notes),
    }

    try {
      if (isEdit && id) {
        await updateMutation.mutateAsync({ id, ...payload })
        void navigate(`/properties/${id}`)
      } else {
        const created = await createMutation.mutateAsync(payload)
        void navigate(`/properties/${created.id}`)
      }
    } catch (err: unknown) {
      // Best-effort: map 422 field errors from API envelope { error: { details: { field: msg } } }
      const anyErr = err as { error?: { details?: Record<string, string> } }
      const details = anyErr?.error?.details
      if (details && typeof details === 'object') {
        for (const [field, message] of Object.entries(details)) {
          if (
            field === 'entity_id' ||
            field === 'name' ||
            field === 'address' ||
            field === 'property_type' ||
            field === 'notes'
          ) {
            setError(field, { message: String(message) })
          }
        }
      }
      // mutation hook already toasted the message; nothing more to do
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={isEdit ? 'Edit property' : 'New property'}
        action={
          <Button variant="outline" size="sm" render={<Link to={isEdit ? `/properties/${id}` : '/properties'} />}>
            Cancel
          </Button>
        }
      />

      {isEdit ? (
        <DataState isPending={isPending} error={error}>
          {property && <PropertyForm />}
        </DataState>
      ) : (
        <PropertyForm />
      )}
    </div>
  )

  function PropertyForm() {
    return (
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <Card>
          <CardContent className="space-y-4 pt-4">
            {/* Entity select */}
            <FormField label="Entity" htmlFor="prop-entity" error={errors.entity_id?.message} required>
              <Controller
                name="entity_id"
                control={control}
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={(val) => field.onChange(val)}
                  >
                    <SelectTrigger id="prop-entity" className="w-full" aria-invalid={!!errors.entity_id}>
                      <SelectValue placeholder="Select entity…" />
                    </SelectTrigger>
                    <SelectContent>
                      {(entities ?? []).map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FormField>

            {/* Name */}
            <FormField label="Name" htmlFor="prop-name" error={errors.name?.message} required>
              <Input
                id="prop-name"
                {...register('name')}
                aria-invalid={!!errors.name}
                placeholder="Property name"
              />
            </FormField>

            {/* Property type select */}
            <FormField label="Property type" htmlFor="prop-type" error={errors.property_type?.message} required>
              <Controller
                name="property_type"
                control={control}
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={(val) => field.onChange(val as PropertyType)}
                  >
                    <SelectTrigger id="prop-type" className="w-full" aria-invalid={!!errors.property_type}>
                      <SelectValue placeholder="Select type…" />
                    </SelectTrigger>
                    <SelectContent>
                      {PROPERTY_TYPES.map((pt) => (
                        <SelectItem key={pt} value={pt}>
                          {PROPERTY_TYPE_LABELS[pt]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FormField>

            {/* Address */}
            <FormField label="Address" htmlFor="prop-address" error={errors.address?.message}>
              <Input
                id="prop-address"
                {...register('address')}
                aria-invalid={!!errors.address}
                placeholder="Street address"
              />
            </FormField>

            {/* Notes */}
            <FormField label="Notes" htmlFor="prop-notes" error={errors.notes?.message}>
              <textarea
                id="prop-notes"
                {...register('notes')}
                aria-invalid={!!errors.notes}
                placeholder="Optional notes"
                rows={3}
                className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:bg-input/30"
              />
            </FormField>
          </CardContent>

          <CardFooter className="gap-2">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : isEdit ? 'Save changes' : 'Create property'}
            </Button>
            <Button
              variant="outline"
              render={<Link to={isEdit ? `/properties/${id}` : '/properties'} />}
            >
              Cancel
            </Button>
          </CardFooter>
        </Card>
      </form>
    )
  }
}
