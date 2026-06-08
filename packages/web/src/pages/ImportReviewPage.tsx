import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { ImportItemTable } from '@/components/import/ImportItemTable'
import { ImportItemPanel } from '@/components/import/ImportItemPanel'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useImportBatch, useCommitBatch, useCancelBatch } from '@/hooks/useImports'
import { formatDate } from '@/lib/format'
import type { CommitSummary, ImportItem } from '@/schemas/imports'

// ─── commit summary dialog ────────────────────────────────────────────────────

interface CommitSummaryDialogProps {
  summary: CommitSummary
  onClose: () => void
}

function CommitSummaryDialog({ summary, onClose }: CommitSummaryDialogProps) {
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>Commit complete</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-2xl font-semibold">{summary.summary.committed}</p>
              <p className="text-xs text-muted-foreground">Committed</p>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-2xl font-semibold">{summary.summary.skipped}</p>
              <p className="text-xs text-muted-foreground">Skipped</p>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-2xl font-semibold text-destructive">{summary.summary.failed}</p>
              <p className="text-xs text-muted-foreground">Failed</p>
            </div>
          </div>

          {summary.failures.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Failures
              </p>
              <ul className="space-y-0.5">
                {summary.failures.map((f) => (
                  <li key={f.item_id} className="text-xs text-destructive">
                    <span className="font-medium">{f.filename}</span>: {f.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  )
}

// ─── page ─────────────────────────────────────────────────────────────────────

export default function ImportReviewPage() {
  const { id } = useParams<{ id: string }>()
  const batchId = id ?? ''

  const { isPending, error, data: batch } = useImportBatch(batchId)
  const commitMutation = useCommitBatch(batchId)
  const cancelMutation = useCancelBatch(batchId)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [commitSummary, setCommitSummary] = useState<CommitSummary | null>(null)

  const selectedItem: ImportItem | undefined = batch?.items.find(
    (item) => item.id === selectedId,
  )

  const hasPendingItems =
    batch?.items.some((item) => item.resolution === 'pending') ?? true

  const canCommit =
    batch?.status === 'review' && !hasPendingItems && !commitMutation.isPending

  const canCancel =
    batch?.status === 'parsing' || batch?.status === 'review'

  async function handleCommit() {
    const result = await commitMutation.mutateAsync()
    setCommitSummary(result)
    if (result.summary.failed === 0) {
      toast.success(
        `Committed ${result.summary.committed} item${result.summary.committed === 1 ? '' : 's'}.`,
      )
    }
  }

  async function handleCancel() {
    if (!window.confirm('Cancel this import batch? This cannot be undone.')) return
    await cancelMutation.mutateAsync()
    toast.success('Import batch cancelled.')
  }

  const pageActions = (
    <div className="flex items-center gap-2">
      {canCancel && (
        <Button
          variant="outline"
          size="sm"
          disabled={cancelMutation.isPending}
          onClick={() => void handleCancel()}
        >
          {cancelMutation.isPending ? 'Cancelling…' : 'Cancel batch'}
        </Button>
      )}
      <Button
        size="sm"
        disabled={!canCommit}
        onClick={() => void handleCommit()}
        title={
          batch?.status !== 'review'
            ? 'Batch must be in review status'
            : hasPendingItems
              ? 'Resolve all pending items first'
              : undefined
        }
      >
        {commitMutation.isPending ? 'Committing…' : 'Commit batch'}
      </Button>
      <Button variant="outline" size="sm" render={<Link to="/imports" />}>
        Back
      </Button>
    </div>
  )

  return (
    <div className="space-y-6">
      <DataState isPending={isPending} error={error}>
        {batch && (
          <>
            <PageHeader
              title={`Import ${formatDate(batch.uploaded_at)}`}
              action={pageActions}
            />

            {batch.status === 'parsing' && (
              <div className="rounded-lg border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
                Parsing… (auto-refreshing)
              </div>
            )}

            {batch.status === 'cancelled' && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                This batch has been cancelled.
              </div>
            )}

            {batch.status === 'committed' && (
              <div className="rounded-lg border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
                This batch has been committed.
              </div>
            )}

            <ImportItemTable
              items={batch.items}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />

            {selectedItem && (
              <ImportItemPanel
                key={selectedItem.id}
                item={selectedItem}
                batchId={batchId}
                onClose={() => setSelectedId(null)}
              />
            )}

            {commitSummary && (
              <CommitSummaryDialog
                summary={commitSummary}
                onClose={() => setCommitSummary(null)}
              />
            )}
          </>
        )}
      </DataState>
    </div>
  )
}
