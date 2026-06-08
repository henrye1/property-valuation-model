import { Fragment, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/lib/auth'
import { downloadFromApi } from '@/lib/download'
import { usePatchImportItem } from '@/hooks/useImports'
import { useProperties } from '@/hooks/useProperties'
import type { ImportItem } from '@/schemas/imports'

// ─── sub-components (module-level) ───────────────────────────────────────────

interface WarningListProps {
  label: string
  items: { code: string; message: string; field_path?: string | null }[]
}

function WarningList({ label, items }: WarningListProps) {
  if (items.length === 0) return null
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <ul className="space-y-0.5">
        {items.map((w, i) => (
          <li key={i} className="text-xs text-muted-foreground">
            <span className="font-medium">{w.code}</span>
            {w.field_path ? ` (${w.field_path})` : ''}: {w.message}
          </li>
        ))}
      </ul>
    </div>
  )
}

interface ParsedInputsSummaryProps {
  inputs: Record<string, unknown> | null | undefined
}

function ParsedInputsSummary({ inputs }: ParsedInputsSummaryProps) {
  if (!inputs || Object.keys(inputs).length === 0) {
    return <p className="text-xs text-muted-foreground italic">No parsed inputs.</p>
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
      {Object.entries(inputs).map(([k, v]) => (
        <Fragment key={k}>
          <dt className="font-medium text-muted-foreground truncate">
            {k}
          </dt>
          <dd className="truncate">
            {v == null ? '—' : String(v)}
          </dd>
        </Fragment>
      ))}
    </dl>
  )
}

// ─── main panel ──────────────────────────────────────────────────────────────

interface ImportItemPanelProps {
  item: ImportItem
  batchId: string
  onClose: () => void
}

export function ImportItemPanel({ item, batchId, onClose }: ImportItemPanelProps) {
  const { api } = useAuth()
  const { mutateAsync, isPending } = usePatchImportItem(batchId)
  const { data: properties } = useProperties()

  // Prefer the already-resolved property id, then the suggestion's auto-linked id,
  // then fall back to empty string (no selection).
  const initialPropertyId: string =
    item.resolved_property_id ??
    (item.suggestion?.auto_linked ? item.suggestion.property_id : '') ??
    ''
  const [resolvedPropertyId, setResolvedPropertyId] = useState<string>(initialPropertyId)
  const [resolutionNotes, setResolutionNotes] = useState<string>('')

  const canAccept = resolvedPropertyId !== ''

  async function handleAccept() {
    await mutateAsync({
      itemId: item.id,
      body: {
        resolution: 'accepted',
        resolved_property_id: resolvedPropertyId || null,
      },
    })
  }

  async function handleReject() {
    await mutateAsync({
      itemId: item.id,
      body: { resolution: 'rejected' },
    })
  }

  async function handleEditedAccept() {
    // Scope decision: full inline editing of parsed_inputs is out of scope for v1.
    // We pass the unchanged parsed_inputs as resolved_inputs, along with
    // resolution_notes. Valuers who need to change individual inputs should
    // edit the source spreadsheet and re-import. See report for details.
    await mutateAsync({
      itemId: item.id,
      body: {
        resolution: 'edited',
        resolved_property_id: resolvedPropertyId || null,
        resolved_inputs: item.parsed_inputs ?? undefined,
        resolution_notes: resolutionNotes || null,
      },
    })
  }

  function handleDownload() {
    void downloadFromApi(api, `/imports/${batchId}/items/${item.id}/source`)
  }

  const isResolved = item.resolution !== 'pending'

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="sm:max-w-lg" showCloseButton>
        <DialogHeader>
          <DialogTitle className="truncate pr-6">{item.filename}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 overflow-y-auto max-h-[60vh] pr-1">
          {/* Current resolution status */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Resolution:</span>
            <Badge variant={item.resolution === 'pending' ? 'outline' : item.resolution === 'rejected' ? 'destructive' : 'secondary'}>
              {item.resolution}
            </Badge>
            <span className="text-xs text-muted-foreground">Parse:</span>
            <Badge variant={item.parse_status === 'error' ? 'destructive' : item.parse_status === 'warning' ? 'default' : 'secondary'}>
              {item.parse_status}
            </Badge>
          </div>

          {/* Suggestion */}
          {item.suggestion && (
            <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs space-y-0.5">
              <p className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px]">
                Suggested match
              </p>
              <p>
                <span className="font-medium">{item.suggestion.property_name}</span>
                {' '}({item.suggestion.entity_name})
              </p>
              <p className="text-muted-foreground">
                Score: {item.suggestion.score}
                {item.suggestion.auto_linked ? ' · auto-linked' : ''}
              </p>
            </div>
          )}

          {/* Parsed inputs read-only */}
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Parsed inputs
            </p>
            <ParsedInputsSummary inputs={item.parsed_inputs} />
          </div>

          {/* Warnings / Errors */}
          <WarningList label="Warnings" items={item.warnings} />
          <WarningList label="Errors" items={item.errors} />

          {/* Resolution controls — hidden once committed */}
          {item.resolution !== 'committed' && (
            <div className="space-y-3 border-t border-border pt-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Resolution
              </p>

              {/* Link to existing property */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground" htmlFor="panel-property-select">
                  Link to property
                </label>
                <Select
                  value={resolvedPropertyId}
                  onValueChange={(val) => setResolvedPropertyId(val ?? '')}
                >
                  <SelectTrigger id="panel-property-select" className="w-full">
                    <SelectValue placeholder="Select property…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">— none —</SelectItem>
                    {(properties ?? []).map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Resolution notes (used for 'edited' pass-through) */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground" htmlFor="panel-notes">
                  Notes (optional — required for "Save with notes")
                </label>
                <textarea
                  id="panel-notes"
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  placeholder="Reviewer notes…"
                  rows={2}
                  className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30"
                />
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex-wrap gap-2 pt-2">
          {/* Download original */}
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={handleDownload}
            disabled={isPending}
          >
            Download original
          </Button>

          {item.resolution !== 'committed' && (
            <>
              {/* Accept — requires a linked property */}
              <Button
                variant="secondary"
                size="sm"
                type="button"
                disabled={!canAccept || isPending || isResolved}
                onClick={() => void handleAccept()}
              >
                Accept
              </Button>

              {/* Save with notes (edited pass-through) */}
              <Button
                variant="outline"
                size="sm"
                type="button"
                disabled={isPending || isResolved}
                onClick={() => void handleEditedAccept()}
              >
                Save with notes
              </Button>

              {/* Reject */}
              <Button
                variant="destructive"
                size="sm"
                type="button"
                disabled={isPending || isResolved}
                onClick={() => void handleReject()}
              >
                Reject
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
