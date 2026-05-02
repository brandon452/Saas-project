"use client"

import { FormEvent, useEffect, useMemo, useState } from "react"
import { Building2, FileText, Globe2, PackageCheck, RefreshCw, Save, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { getApiErrorMessage } from "@/lib/api"
import { useAuditEvents } from "@/lib/hooks/useAuditEvents"
import { useOrgSettings, useOrgSettingsMutation } from "@/lib/hooks/useOrgSettings"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"

const COMMON_TIMEZONES = [
  { value: "Asia/Kuala_Lumpur", label: "Malaysia - Kuala Lumpur (UTC+08:00)" },
  { value: "Asia/Singapore", label: "Singapore (UTC+08:00)" },
  { value: "UTC", label: "UTC (UTC+00:00)" },
  { value: "Asia/Bangkok", label: "Bangkok, Jakarta, Vietnam (UTC+07:00)" },
  { value: "Asia/Manila", label: "Manila (UTC+08:00)" },
  { value: "Asia/Hong_Kong", label: "Hong Kong (UTC+08:00)" },
  { value: "Asia/Tokyo", label: "Tokyo (UTC+09:00)" },
  { value: "Asia/Dubai", label: "Dubai (UTC+04:00)" },
  { value: "Australia/Sydney", label: "Sydney (UTC+10:00 / UTC+11:00 DST)" },
  { value: "Europe/London", label: "London (UTC+00:00 / UTC+01:00 DST)" },
  { value: "Europe/Paris", label: "Paris, Berlin, Madrid (UTC+01:00 / UTC+02:00 DST)" },
  { value: "America/New_York", label: "New York (UTC-05:00 / UTC-04:00 DST)" },
  { value: "America/Chicago", label: "Chicago (UTC-06:00 / UTC-05:00 DST)" },
  { value: "America/Denver", label: "Denver (UTC-07:00 / UTC-06:00 DST)" },
  { value: "America/Los_Angeles", label: "Los Angeles (UTC-08:00 / UTC-07:00 DST)" },
]

const COMMON_CURRENCIES = [
  { value: "MYR", label: "MYR - Malaysian Ringgit" },
  { value: "SGD", label: "SGD - Singapore Dollar" },
  { value: "USD", label: "USD - US Dollar" },
  { value: "EUR", label: "EUR - Euro" },
  { value: "GBP", label: "GBP - British Pound" },
  { value: "AUD", label: "AUD - Australian Dollar" },
  { value: "JPY", label: "JPY - Japanese Yen" },
  { value: "CNY", label: "CNY - Chinese Yuan" },
  { value: "HKD", label: "HKD - Hong Kong Dollar" },
  { value: "THB", label: "THB - Thai Baht" },
  { value: "IDR", label: "IDR - Indonesian Rupiah" },
  { value: "PHP", label: "PHP - Philippine Peso" },
]

function formatCreatedAt(value: string) {
  if (!value) return "-"

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value))
}

export default function SettingsPage() {
  const { user, isLoading: authLoading } = useAuth()
  const { orgId, role } = useOrg()
  const settingsQuery = useOrgSettings(orgId)
  const updateSettings = useOrgSettingsMutation(orgId)
  const [name, setName] = useState("")
  const [defaultCurrency, setDefaultCurrency] = useState("USD")
  const [defaultTimezone, setDefaultTimezone] = useState("UTC")
  const [allowNegativeStock, setAllowNegativeStock] = useState(false)
  const [purchaseOrderPrefix, setPurchaseOrderPrefix] = useState("PO")
  const [branchTransferApprovalRequired, setBranchTransferApprovalRequired] = useState(true)
  const [stockTakeApprovalRequired, setStockTakeApprovalRequired] = useState(true)
  const [auditEventType, setAuditEventType] = useState("")
  const [auditResourceId, setAuditResourceId] = useState("")
  const [auditQueryText, setAuditQueryText] = useState("")
  const [auditFrom, setAuditFrom] = useState("")
  const [auditTo, setAuditTo] = useState("")
  const [changedByMe, setChangedByMe] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")

  const settings = settingsQuery.data ?? null
  const canManage =
    role === "OWNER" || role === "ADMIN" || user?.parent_role === "PARENT_ADMIN"
  const trimmedName = name.trim()
  const trimmedCurrency = defaultCurrency.trim().toUpperCase()
  const trimmedTimezone = defaultTimezone.trim()
  const trimmedPurchaseOrderPrefix = purchaseOrderPrefix.trim().toUpperCase()
  const hasChanges =
    !!settings &&
    (trimmedName !== settings.name ||
      trimmedCurrency !== settings.default_currency ||
      trimmedTimezone !== settings.default_timezone ||
      allowNegativeStock !== settings.allow_negative_stock ||
      trimmedPurchaseOrderPrefix !== settings.purchase_order_prefix ||
      branchTransferApprovalRequired !== settings.branch_transfer_approval_required ||
      stockTakeApprovalRequired !== settings.stock_take_approval_required)
  const canSubmit =
    hasChanges &&
    !!trimmedName &&
    /^[A-Z]{3}$/.test(trimmedCurrency) &&
    !!trimmedTimezone &&
    !!trimmedPurchaseOrderPrefix
  const isBusy = settingsQuery.isFetching || updateSettings.isPending
  const auditQuery = useAuditEvents(orgId, {
    event_type: auditEventType || undefined,
    resource_id: auditResourceId.trim() || undefined,
    q: auditQueryText.trim() || undefined,
    from: auditFrom ? `${auditFrom}T00:00:00Z` : undefined,
    to: auditTo ? `${auditTo}T23:59:59Z` : undefined,
    changed_by_me: changedByMe,
    actor_user_id: user?.id,
  })
  const createdAt = useMemo(
    () => formatCreatedAt(settings?.created_at ?? ""),
    [settings?.created_at],
  )
  const auditExportHref = useMemo(() => {
    const params = new URLSearchParams()
    if (auditEventType) params.set("event_type", auditEventType)
    if (auditResourceId.trim()) params.set("resource_id", auditResourceId.trim())
    if (auditQueryText.trim()) params.set("q", auditQueryText.trim())
    if (auditFrom) params.set("from", `${auditFrom}T00:00:00Z`)
    if (auditTo) params.set("to", `${auditTo}T23:59:59Z`)
    if (changedByMe && user?.id) params.set("actor_user_id", user.id)
    const query = params.toString()
    return `/api/orgs/${orgId}/audit-events/export/${query ? `?${query}` : ""}`
  }, [auditEventType, auditResourceId, auditQueryText, auditFrom, auditTo, changedByMe, user?.id, orgId])

  useEffect(() => {
    if (settings) {
      setName(settings.name)
      setDefaultCurrency(settings.default_currency)
      setDefaultTimezone(settings.default_timezone)
      setAllowNegativeStock(settings.allow_negative_stock)
      setPurchaseOrderPrefix(settings.purchase_order_prefix)
      setBranchTransferApprovalRequired(settings.branch_transfer_approval_required)
      setStockTakeApprovalRequired(settings.stock_take_approval_required)
      setError("")
      setSuccess("")
    }
  }, [settings])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!settings || !canManage || !canSubmit) return

    try {
      setError("")
      setSuccess("")
      await updateSettings.mutateAsync({
        name: trimmedName,
        default_currency: trimmedCurrency,
        default_timezone: trimmedTimezone,
        allow_negative_stock: allowNegativeStock,
        purchase_order_prefix: trimmedPurchaseOrderPrefix,
        branch_transfer_approval_required: branchTransferApprovalRequired,
        stock_take_approval_required: stockTakeApprovalRequired,
      })
      setSuccess("Organization settings saved.")
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save organization settings."))
    }
  }

  if (authLoading || settingsQuery.isLoading) {
    return <SettingsPageSkeleton />
  }

  if (!canManage || getApiErrorMessage(settingsQuery.error, "").includes("permission")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to manage settings for this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (settingsQuery.isError || !settings) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load settings</CardTitle>
          <CardDescription>
            There was a problem loading this organisation settings page.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void settingsQuery.refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Organization Settings</h1>
          <p className="text-sm text-muted-foreground">
            Manage identity, operating defaults, and inventory policies for this organisation.
          </p>
        </div>
        <Badge variant={settings.is_active ? "default" : "secondary"}>
          {settings.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>
              Update organisation identity and the defaults used in reporting and documents.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-5" onSubmit={(event) => void handleSubmit(event)}>
              <div className="space-y-2">
                <Label htmlFor="org-name">Organization name</Label>
                <Input
                  id="org-name"
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value)
                    setError("")
                    setSuccess("")
                  }}
                  disabled={isBusy}
                  maxLength={255}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="org-slug">Slug</Label>
                  <Input id="org-slug" value={settings.slug} disabled readOnly />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="org-id">Organization ID</Label>
                  <Input id="org-id" value={settings.id} disabled readOnly />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="default-currency">Default currency</Label>
                  <select
                    id="default-currency"
                    value={defaultCurrency}
                    onChange={(event) => {
                      setDefaultCurrency(event.target.value.toUpperCase())
                      setError("")
                      setSuccess("")
                    }}
                    disabled={isBusy}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {COMMON_CURRENCIES.some((currency) => currency.value === defaultCurrency) ? null : (
                      <option value={defaultCurrency}>{defaultCurrency}</option>
                    )}
                    {COMMON_CURRENCIES.map((currency) => (
                      <option key={currency.value} value={currency.value}>
                        {currency.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="default-timezone">Default timezone</Label>
                  <select
                    id="default-timezone"
                    value={defaultTimezone}
                    onChange={(event) => {
                      setDefaultTimezone(event.target.value)
                      setError("")
                      setSuccess("")
                    }}
                    disabled={isBusy}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {COMMON_TIMEZONES.some((timezone) => timezone.value === defaultTimezone) ? null : (
                      <option value={defaultTimezone}>{defaultTimezone}</option>
                    )}
                    {COMMON_TIMEZONES.map((timezone) => (
                      <option key={timezone.value} value={timezone.value}>
                        {timezone.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_160px]">
                <div className="space-y-2">
                  <Label htmlFor="po-prefix">Purchase order prefix</Label>
                  <Input
                    id="po-prefix"
                    value={purchaseOrderPrefix}
                    onChange={(event) => {
                      setPurchaseOrderPrefix(event.target.value.toUpperCase())
                      setError("")
                      setSuccess("")
                    }}
                    disabled={isBusy}
                    maxLength={12}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="po-next-number">Next PO number</Label>
                  <Input
                    id="po-next-number"
                    type="text"
                    value={String(settings.purchase_order_next_number)}
                    disabled
                    readOnly
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <label className="flex items-start gap-3 rounded-md border border-border p-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={allowNegativeStock}
                    onChange={(event) => {
                      setAllowNegativeStock(event.target.checked)
                      setError("")
                      setSuccess("")
                    }}
                    disabled={isBusy}
                  />
                  <span>
                    <span className="block font-medium">Allow negative stock</span>
                    <span className="block text-muted-foreground">Permit stock-outs below zero.</span>
                  </span>
                </label>
                <label className="flex items-start gap-3 rounded-md border border-border p-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={branchTransferApprovalRequired}
                    onChange={(event) => {
                      setBranchTransferApprovalRequired(event.target.checked)
                      setError("")
                      setSuccess("")
                    }}
                    disabled={isBusy}
                  />
                  <span>
                    <span className="block font-medium">Transfer approval</span>
                    <span className="block text-muted-foreground">Require approval before dispatch.</span>
                  </span>
                </label>
                <label className="flex items-start gap-3 rounded-md border border-border p-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={stockTakeApprovalRequired}
                    onChange={(event) => {
                      setStockTakeApprovalRequired(event.target.checked)
                      setError("")
                      setSuccess("")
                    }}
                    disabled={isBusy}
                  />
                  <span>
                    <span className="block font-medium">Stock take approval</span>
                    <span className="block text-muted-foreground">Keep counts behind approval.</span>
                  </span>
                </label>
              </div>

              {error ? (
                <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              ) : null}

              {success ? (
                <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  {success}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <Button type="submit" disabled={!canSubmit || isBusy}>
                  <Save className="mr-2 h-4 w-4" />
                  {updateSettings.isPending ? "Saving..." : "Save Changes"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setName(settings.name)
                    setDefaultCurrency(settings.default_currency)
                    setDefaultTimezone(settings.default_timezone)
                    setAllowNegativeStock(settings.allow_negative_stock)
                    setPurchaseOrderPrefix(settings.purchase_order_prefix)
                    setBranchTransferApprovalRequired(settings.branch_transfer_approval_required)
                    setStockTakeApprovalRequired(settings.stock_take_approval_required)
                    setError("")
                    setSuccess("")
                  }}
                  disabled={!hasChanges || isBusy}
                >
                  Reset
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
            <CardDescription>Read-only organisation metadata.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3 rounded-md border border-border p-3">
              <Building2 className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium">Parent company</p>
                <p className="truncate text-sm text-muted-foreground">
                  {settings.parent_company_name}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-md border border-border p-3">
              <Globe2 className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium">Defaults</p>
                <p className="text-sm text-muted-foreground">
                  {settings.default_currency} - {settings.default_timezone}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-md border border-border p-3">
              <FileText className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium">Purchase orders</p>
                <p className="text-sm text-muted-foreground">
                  Next number {settings.purchase_order_prefix}-{String(settings.purchase_order_next_number).padStart(4, "0")}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-md border border-border p-3">
              <PackageCheck className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium">Inventory policy</p>
                <p className="text-sm text-muted-foreground">
                  Negative stock {settings.allow_negative_stock ? "allowed" : "blocked"}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-md border border-border p-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium">Approvals</p>
                <p className="text-sm text-muted-foreground">
                  Transfers {settings.branch_transfer_approval_required ? "required" : "skipped"} - Stock takes {settings.stock_take_approval_required ? "required" : "tracked"}
                </p>
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Created</p>
              <p className="text-sm text-muted-foreground">{createdAt}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Access</p>
              <p className="text-sm text-muted-foreground">
                {user?.parent_role === "PARENT_ADMIN"
                  ? "Parent admin"
                  : role ?? "No organization role"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Audit</CardTitle>
          <CardDescription>Recent governance changes for this organisation.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="audit-event-type">Event type</Label>
              <select
                id="audit-event-type"
                value={auditEventType}
                onChange={(event) => setAuditEventType(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
              >
                <option value="">All events</option>
                <option value="org.settings.updated">Settings updated</option>
                <option value="member.role.changed">Member role changed</option>
                <option value="member.status.changed">Member status changed</option>
                <option value="member.branch.changed">Member branch changed</option>
                <option value="po.submitted">PO submitted</option>
                <option value="po.cancelled">PO cancelled</option>
                <option value="goods_receipt.created">Goods receipt created</option>
                <option value="supplier.updated">Supplier updated</option>
                <option value="branch_transfer.received_complete">Transfer received complete</option>
                <option value="branch_transfer.received_with_variance">Transfer received with variance</option>
                <option value="stock_take.completed">Stock take completed</option>
                <option value="stock_take.completed_with_variances">Stock take completed with variances</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="audit-resource-id">Resource ID</Label>
              <Input
                id="audit-resource-id"
                value={auditResourceId}
                onChange={(event) => setAuditResourceId(event.target.value)}
                placeholder="UUID or ID"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="audit-q">Search summary</Label>
              <Input id="audit-q" value={auditQueryText} onChange={(event) => setAuditQueryText(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="audit-from">From</Label>
              <Input id="audit-from" type="date" value={auditFrom} onChange={(event) => setAuditFrom(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="audit-to">To</Label>
              <Input id="audit-to" type="date" value={auditTo} onChange={(event) => setAuditTo(event.target.value)} />
            </div>
            <label className="mt-7 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={changedByMe} onChange={(event) => setChangedByMe(event.target.checked)} />
              Changed by me
            </label>
            <div className="mt-7">
              <Button variant="outline" onClick={() => window.open(auditExportHref, "_blank", "noopener,noreferrer")}>
                Export CSV
              </Button>
            </div>
          </div>

          {auditQuery.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : auditQuery.isError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              Could not load audit events.
            </div>
          ) : (auditQuery.data?.results.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">No audit events found for the selected filters.</p>
          ) : (
            <div className="space-y-3">
              {auditQuery.data?.results.map((event) => (
                <details key={event.id} className="rounded-md border border-border p-3">
                  <summary className="cursor-pointer text-sm font-medium">
                    {new Date(event.occurred_at).toLocaleString()} - {event.summary}
                  </summary>
                  <div className="mt-2 space-y-2 text-sm text-muted-foreground">
                    <p>
                      <strong className="text-foreground">Actor:</strong>{" "}
                      {event.actor.name || event.actor.email || event.actor.type}
                    </p>
                    <p>
                      <strong className="text-foreground">Event:</strong>{" "}
                      {event.event_type === "branch_transfer.received_complete"
                        ? "branch transfer received complete"
                        : event.event_type === "branch_transfer.received_with_variance"
                          ? "branch transfer received with variance"
                          : event.event_type === "stock_take.completed"
                            ? "stock take completed"
                            : event.event_type === "stock_take.completed_with_variances"
                              ? "stock take completed with variances"
                              : event.event_type}
                    </p>
                    <p>
                      <strong className="text-foreground">Resource:</strong> {event.resource_type} ({event.resource_id})
                    </p>
                    <pre className="overflow-x-auto rounded bg-muted p-2 text-xs">
                      {JSON.stringify({ diff: event.diff_json, metadata: event.metadata_json }, null, 2)}
                    </pre>
                  </div>
                </details>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function SettingsPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-64" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  )
}
