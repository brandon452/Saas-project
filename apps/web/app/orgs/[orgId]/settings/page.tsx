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
  const [purchaseOrderNextNumber, setPurchaseOrderNextNumber] = useState("1")
  const [branchTransferApprovalRequired, setBranchTransferApprovalRequired] = useState(true)
  const [stockTakeApprovalRequired, setStockTakeApprovalRequired] = useState(true)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")

  const settings = settingsQuery.data ?? null
  const canManage =
    role === "OWNER" || role === "ADMIN" || user?.parent_role === "PARENT_ADMIN"
  const trimmedName = name.trim()
  const trimmedCurrency = defaultCurrency.trim().toUpperCase()
  const trimmedTimezone = defaultTimezone.trim()
  const trimmedPurchaseOrderPrefix = purchaseOrderPrefix.trim().toUpperCase()
  const parsedPurchaseOrderNextNumber = Number.parseInt(purchaseOrderNextNumber, 10)
  const hasChanges =
    !!settings &&
    (trimmedName !== settings.name ||
      trimmedCurrency !== settings.default_currency ||
      trimmedTimezone !== settings.default_timezone ||
      allowNegativeStock !== settings.allow_negative_stock ||
      trimmedPurchaseOrderPrefix !== settings.purchase_order_prefix ||
      parsedPurchaseOrderNextNumber !== settings.purchase_order_next_number ||
      branchTransferApprovalRequired !== settings.branch_transfer_approval_required ||
      stockTakeApprovalRequired !== settings.stock_take_approval_required)
  const canSubmit =
    hasChanges &&
    !!trimmedName &&
    /^[A-Z]{3}$/.test(trimmedCurrency) &&
    !!trimmedTimezone &&
    !!trimmedPurchaseOrderPrefix &&
    Number.isInteger(parsedPurchaseOrderNextNumber) &&
    parsedPurchaseOrderNextNumber > 0
  const isBusy = settingsQuery.isFetching || updateSettings.isPending
  const createdAt = useMemo(
    () => formatCreatedAt(settings?.created_at ?? ""),
    [settings?.created_at],
  )

  useEffect(() => {
    if (settings) {
      setName(settings.name)
      setDefaultCurrency(settings.default_currency)
      setDefaultTimezone(settings.default_timezone)
      setAllowNegativeStock(settings.allow_negative_stock)
      setPurchaseOrderPrefix(settings.purchase_order_prefix)
      setPurchaseOrderNextNumber(String(settings.purchase_order_next_number))
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
        purchase_order_next_number: parsedPurchaseOrderNextNumber,
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
                    type="number"
                    min={1}
                    value={purchaseOrderNextNumber}
                    onChange={(event) => {
                      setPurchaseOrderNextNumber(event.target.value)
                      setError("")
                      setSuccess("")
                    }}
                    disabled={isBusy}
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
                    setPurchaseOrderNextNumber(String(settings.purchase_order_next_number))
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
