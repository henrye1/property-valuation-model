import { useEffect } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { FormField } from '@/components/forms/FormField'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter } from '@/components/ui/card'
import { useEntity } from '@/hooks/useEntities'
import { useCreateEntity, useUpdateEntity } from '@/hooks/useEntityMutations'

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  registration_number: z.string().optional().or(z.literal('')),
  notes: z.string().optional().or(z.literal('')),
})

type FormValues = z.infer<typeof schema>

function emptyToNull(val: string | undefined): string | null {
  return val === '' || val === undefined ? null : val
}

export default function EntityFormPage() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()

  const createMutation = useCreateEntity()
  const updateMutation = useUpdateEntity()

  const { isPending, error, data: entity } = useEntity(id ?? '')

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', registration_number: '', notes: '' },
  })

  useEffect(() => {
    if (entity) {
      reset({
        name: entity.name,
        registration_number: entity.registration_number ?? '',
        notes: entity.notes ?? '',
      })
    }
  }, [entity, reset])

  async function onSubmit(values: FormValues) {
    const payload = {
      name: values.name,
      registration_number: emptyToNull(values.registration_number),
      notes: emptyToNull(values.notes),
    }

    try {
      if (isEdit && id) {
        await updateMutation.mutateAsync({ id, ...payload })
        void navigate(`/entities/${id}`)
      } else {
        const created = await createMutation.mutateAsync(payload)
        void navigate(`/entities/${created.id}`)
      }
    } catch (err: unknown) {
      // Best-effort: map 422 field errors from API envelope { error: { details: { field: msg } } }
      const anyErr = err as { error?: { details?: Record<string, string> } }
      const details = anyErr?.error?.details
      if (details && typeof details === 'object') {
        for (const [field, message] of Object.entries(details)) {
          if (field === 'name' || field === 'registration_number' || field === 'notes') {
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
        title={isEdit ? 'Edit entity' : 'New entity'}
        action={
          <Button variant="outline" size="sm" render={<Link to={isEdit ? `/entities/${id}` : '/entities'} />}>
            Cancel
          </Button>
        }
      />

      {isEdit ? (
        <DataState isPending={isPending} error={error}>
          {entity && <EntityForm />}
        </DataState>
      ) : (
        <EntityForm />
      )}
    </div>
  )

  function EntityForm() {
    return (
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <Card>
          <CardContent className="space-y-4 pt-4">
            <FormField label="Name" htmlFor="entity-name" error={errors.name?.message} required>
              <Input
                id="entity-name"
                {...register('name')}
                aria-invalid={!!errors.name}
                placeholder="Entity name"
              />
            </FormField>

            <FormField
              label="Registration number"
              htmlFor="entity-reg"
              error={errors.registration_number?.message}
            >
              <Input
                id="entity-reg"
                {...register('registration_number')}
                aria-invalid={!!errors.registration_number}
                placeholder="e.g. 2021/012345/07"
              />
            </FormField>

            <FormField label="Notes" htmlFor="entity-notes" error={errors.notes?.message}>
              <textarea
                id="entity-notes"
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
              {isSubmitting ? 'Saving…' : isEdit ? 'Save changes' : 'Create entity'}
            </Button>
            <Button
              variant="outline"
              render={<Link to={isEdit ? `/entities/${id}` : '/entities'} />}
            >
              Cancel
            </Button>
          </CardFooter>
        </Card>
      </form>
    )
  }
}
