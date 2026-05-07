"use client"

import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { SupplierStatusBadge } from "@/components/suppliers/SupplierStatusBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { usePOItemSearch } from "@/lib/hooks/purchase-orders/usePOItemSearch"
import { useSupplier } from "@/lib/hooks/suppliers/useSupplier"
import { useSupplierContactMutations } from "@/lib/hooks/suppliers/useSupplierContactMutations"
import { useSupplierContacts } from "@/lib/hooks/suppliers/useSupplierContacts"
import { useSupplierItemMutations, useSupplierItems } from "@/lib/hooks/suppliers/useSupplierItems"
import { useSupplierMutations } from "@/lib/hooks/suppliers/useSupplierMutations"
import { useOrg } from "@/lib/hooks/useOrg"
import type { SupplierCatalogItem } from "@/lib/types/supplier-catalog"
import type { SupplierContact } from "@/lib/types/suppliers"

export default function SupplierDetailPage() {
  const router = useRouter()
  const params = useParams<{ orgId: string; id: string }>()
  const { orgId, canAccess } = useOrg()
  const supplierId = params?.id ?? ""

  const supplierQuery = useSupplier(orgId, supplierId)
  const contactsQuery = useSupplierContacts(orgId, supplierQuery.data?.id ?? null)
  const catalogQuery = useSupplierItems(orgId, supplierId)

  const { updateSupplier, deactivateSupplier, reactivateSupplier } = useSupplierMutations(orgId)
  const contactMutations = useSupplierContactMutations(orgId, supplierQuery.data?.id ?? 0)
  const catalogMutations = useSupplierItemMutations(orgId, supplierId)

  // Header / core
  const [displayName, setDisplayName] = useState("")
  const [error, setError] = useState("")
  const [confirmDeactivate, setConfirmDeactivate] = useState(false)
  const [confirmReactivate, setConfirmReactivate] = useState(false)

  // Details
  const [legalName, setLegalName] = useState("")
  const [email, setEmail] = useState("")
  const [phone, setPhone] = useState("")
  const [paymentTermsDays, setPaymentTermsDays] = useState("")
  const [leadTimeDays, setLeadTimeDays] = useState("")
  const [currency, setCurrency] = useState("")
  const [taxId, setTaxId] = useState("")
  const [notes, setNotes] = useState("")

  // Address
  const [addressLine1, setAddressLine1] = useState("")
  const [addressLine2, setAddressLine2] = useState("")
  const [city, setCity] = useState("")
  const [addressState, setAddressState] = useState("")
  const [postalCode, setPostalCode] = useState("")
  const [country, setCountry] = useState("")

  // Contacts
  const [addingContact, setAddingContact] = useState(false)
  const [newContactName, setNewContactName] = useState("")
  const [newContactRole, setNewContactRole] = useState("")
  const [newContactEmail, setNewContactEmail] = useState("")
  const [newContactPhone, setNewContactPhone] = useState("")
  const [contactError, setContactError] = useState("")
  const [editingContactId, setEditingContactId] = useState<number | null>(null)
  const [editContactName, setEditContactName] = useState("")
  const [editContactRole, setEditContactRole] = useState("")
  const [editContactEmail, setEditContactEmail] = useState("")
  const [editContactPhone, setEditContactPhone] = useState("")

  // Catalog
  const [addingCatalogItem, setAddingCatalogItem] = useState(false)
  const [catalogItemQuery, setCatalogItemQuery] = useState("")
  const [catalogItemDebouncedQuery, setCatalogItemDebouncedQuery] = useState("")
  const [selectedCatalogItem, setSelectedCatalogItem] = useState<{ id: string; name: string; sku: string } | null>(null)
  const [newItemUnitCost, setNewItemUnitCost] = useState("")
  const [newItemLeadTime, setNewItemLeadTime] = useState("")
  const [newItemPreferred, setNewItemPreferred] = useState(false)
  const [catalogError, setCatalogError] = useState("")
  const [editingCatalogItemId, setEditingCatalogItemId] = useState<number | null>(null)
  const [editItemUnitCost, setEditItemUnitCost] = useState("")
  const [editItemLeadTime, setEditItemLeadTime] = useState("")
  const [editItemPreferred, setEditItemPreferred] = useState(false)

  const supplier = supplierQuery.data

  useEffect(() => {
    if (!supplier) return
    setDisplayName(supplier.display_name)
    setLegalName(supplier.legal_name)
    setEmail(supplier.email)
    setPhone(supplier.phone)
    setPaymentTermsDays(supplier.payment_terms_days != null ? String(supplier.payment_terms_days) : "")
    setLeadTimeDays(supplier.default_lead_time_days != null ? String(supplier.default_lead_time_days) : "")
    setCurrency(supplier.currency)
    setTaxId(supplier.tax_id)
    setNotes(supplier.notes)
    setAddressLine1(supplier.address_line1)
    setAddressLine2(supplier.address_line2)
    setCity(supplier.city)
    setAddressState(supplier.state)
    setPostalCode(supplier.postal_code)
    setCountry(supplier.country)
    setError("")
  }, [supplier])

  useEffect(() => {
    const timer = window.setTimeout(() => setCatalogItemDebouncedQuery(catalogItemQuery), 300)
    return () => window.clearTimeout(timer)
  }, [catalogItemQuery])

  const { data: catalogItemSearchResults = [] } = usePOItemSearch(orgId, catalogItemDebouncedQuery)

  const canManage = canAccess(["OWNER", "ADMIN"])
  const isReadOnly = !supplier || !supplier.is_active || !canManage
  const isBusy = updateSupplier.isPending || deactivateSupplier.isPending || reactivateSupplier.isPending
  const contacts = contactsQuery.data ?? []
  const catalogItems = catalogQuery.data ?? []

  // ── handlers ──────────────────────────────────────────────────────────────

  async function handleSave() {
    if (!supplier || isReadOnly) return
    try {
      setError("")
      await updateSupplier.mutateAsync({
        id: supplier.id,
        data: {
          display_name: displayName.trim(),
          legal_name: legalName.trim(),
          email: email.trim(),
          phone: phone.trim(),
          payment_terms_days: paymentTermsDays.trim() ? Number(paymentTermsDays) : null,
          default_lead_time_days: leadTimeDays.trim() ? Number(leadTimeDays) : null,
          currency: currency.trim(),
          tax_id: taxId.trim(),
          notes: notes.trim(),
          address_line1: addressLine1.trim(),
          address_line2: addressLine2.trim(),
          city: city.trim(),
          state: addressState.trim(),
          postal_code: postalCode.trim(),
          country: country.trim(),
        },
      })
      await supplierQuery.refetch()
    } catch (err) {
      const msg = err instanceof Error ? err.message : ""
      setError(msg.includes("403") ? "Permission denied." : msg.includes("400") ? "Name is invalid or already in use." : "Could not save changes.")
    }
  }

  async function handleDeactivate() {
    if (!supplier) return
    try {
      setError("")
      await deactivateSupplier.mutateAsync(supplier.id)
      await supplierQuery.refetch()
    } catch (err) {
      const msg = err instanceof Error ? err.message : ""
      setError(msg.includes("403") ? "Permission denied." : "Could not deactivate supplier.")
    }
  }

  async function handleReactivate() {
    if (!supplier) return
    try {
      setError("")
      await reactivateSupplier.mutateAsync(supplier.id)
      await supplierQuery.refetch()
    } catch (err) {
      const msg = err instanceof Error ? err.message : ""
      setError(msg.includes("403") ? "Permission denied." : "Could not reactivate supplier.")
    }
  }

  async function handleAddContact() {
    if (!newContactName.trim()) { setContactError("Contact name is required."); return }
    try {
      setContactError("")
      await contactMutations.addContact.mutateAsync({
        full_name: newContactName.trim(),
        role: newContactRole.trim() || undefined,
        email: newContactEmail.trim() || undefined,
        phone: newContactPhone.trim() || undefined,
      })
      setAddingContact(false)
      setNewContactName(""); setNewContactRole(""); setNewContactEmail(""); setNewContactPhone("")
    } catch { setContactError("Could not add contact.") }
  }

  function handleStartEditContact(contact: SupplierContact) {
    setEditingContactId(contact.id)
    setEditContactName(contact.full_name)
    setEditContactRole(contact.role ?? "")
    setEditContactEmail(contact.email ?? "")
    setEditContactPhone(contact.phone ?? "")
    setContactError("")
    setAddingContact(false)
  }

  async function handleSaveEditContact(contact: SupplierContact) {
    if (!editContactName.trim()) { setContactError("Contact name is required."); return }
    try {
      setContactError("")
      await contactMutations.updateContact.mutateAsync({
        contactId: contact.id,
        data: { full_name: editContactName.trim(), role: editContactRole.trim(), email: editContactEmail.trim(), phone: editContactPhone.trim() },
      })
      setEditingContactId(null)
    } catch { setContactError("Could not save contact.") }
  }

  async function handleAddCatalogItem() {
    if (!selectedCatalogItem) { setCatalogError("Select an item."); return }
    try {
      setCatalogError("")
      await catalogMutations.addItem.mutateAsync({
        org_item_id: selectedCatalogItem.id,
        unit_cost: newItemUnitCost.trim() || null,
        lead_time_days: newItemLeadTime.trim() ? Number(newItemLeadTime) : null,
        is_preferred: newItemPreferred,
      })
      setAddingCatalogItem(false)
      setSelectedCatalogItem(null); setCatalogItemQuery("")
      setNewItemUnitCost(""); setNewItemLeadTime(""); setNewItemPreferred(false)
    } catch { setCatalogError("Could not add item.") }
  }

  function handleStartEditCatalogItem(item: SupplierCatalogItem) {
    setEditingCatalogItemId(item.id)
    setEditItemUnitCost(item.unit_cost ?? "")
    setEditItemLeadTime(item.lead_time_days != null ? String(item.lead_time_days) : "")
    setEditItemPreferred(item.is_preferred)
    setCatalogError("")
  }

  async function handleSaveCatalogItem(item: SupplierCatalogItem) {
    try {
      setCatalogError("")
      await catalogMutations.updateItem.mutateAsync({
        supplierItemId: item.id,
        data: {
          unit_cost: editItemUnitCost.trim() || null,
          lead_time_days: editItemLeadTime.trim() ? Number(editItemLeadTime) : null,
          is_preferred: editItemPreferred,
        },
      })
      setEditingCatalogItemId(null)
    } catch { setCatalogError("Could not save catalog item.") }
  }

  async function handleRemoveCatalogItem(item: SupplierCatalogItem) {
    try {
      setCatalogError("")
      await catalogMutations.removeItem.mutateAsync(item.id)
    } catch { setCatalogError("Could not remove catalog item.") }
  }

  // ── loading / error states ─────────────────────────────────────────────────

  if (supplierQuery.isLoading) return <DetailSkeleton />

  const errorMessage = supplierQuery.error instanceof Error ? supplierQuery.error.message : ""

  if (errorMessage.includes("404")) {
    return (
      <Card>
        <CardHeader><CardTitle>Supplier not found</CardTitle></CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/suppliers`} className="text-sm text-primary">Back to suppliers</Link>
        </CardContent>
      </Card>
    )
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader><CardTitle>Access denied</CardTitle></CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/suppliers`} className="text-sm text-primary">Back to suppliers</Link>
        </CardContent>
      </Card>
    )
  }

  if (!supplier || supplierQuery.isError) {
    return (
      <Card>
        <CardHeader><CardTitle>Could not load supplier</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Try loading the page again.</p>
          <Button onClick={() => void supplierQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  // ── page ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-muted-foreground">
        <button className="hover:text-foreground" onClick={() => router.push(`/orgs/${orgId}/suppliers`)}>
          Suppliers
        </button>
        {" / "}
        <span>{supplier.display_name}</span>
      </div>

      {/* Header card */}
      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold">{supplier.display_name}</h1>
              <SupplierStatusBadge isActive={supplier.is_active} />
            </div>
            {supplier.code ? <p className="text-sm text-muted-foreground">{supplier.code}</p> : null}
            <p className="text-xs text-muted-foreground">
              Created {new Date(supplier.created_at).toLocaleDateString()} · Updated {new Date(supplier.updated_at).toLocaleDateString()}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canManage && supplier.is_active ? (
              <Button variant="ghost" className="text-red-600 hover:text-red-700" disabled={isBusy} onClick={() => setConfirmDeactivate(true)}>
                Deactivate
              </Button>
            ) : null}
            {canManage && !supplier.is_active ? (
              <Button variant="outline" disabled={isBusy} onClick={() => setConfirmReactivate(true)}>
                Reactivate
              </Button>
            ) : null}
          </div>
        </CardHeader>
      </Card>

      {/* Details card */}
      <Card>
        <CardHeader><CardTitle>Details</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Name *</Label>
              <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
            <div className="space-y-1">
              <Label>Legal name</Label>
              <Input value={legalName} onChange={(e) => setLegalName(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
            <div className="space-y-1">
              <Label>Phone</Label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1">
              <Label>Payment terms (days)</Label>
              <Input type="number" min={0} value={paymentTermsDays} onChange={(e) => setPaymentTermsDays(e.target.value)} readOnly={isReadOnly} disabled={isBusy} placeholder="30" />
            </div>
            <div className="space-y-1">
              <Label>Lead time (days)</Label>
              <Input type="number" min={0} value={leadTimeDays} onChange={(e) => setLeadTimeDays(e.target.value)} readOnly={isReadOnly} disabled={isBusy} placeholder="7" />
            </div>
            <div className="space-y-1">
              <Label>Currency</Label>
              <Input value={currency} maxLength={3} onChange={(e) => setCurrency(e.target.value)} readOnly={isReadOnly} disabled={isBusy} placeholder="USD" />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Tax ID</Label>
              <Input value={taxId} onChange={(e) => setTaxId(e.target.value)} readOnly={isReadOnly} disabled={isBusy} placeholder="VAT / EIN" />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} readOnly={isReadOnly} disabled={isBusy} rows={3} />
          </div>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {!isReadOnly ? (
            <Button onClick={() => void handleSave()} disabled={isBusy || !displayName.trim()}>
              {updateSupplier.isPending ? "Saving…" : "Save changes"}
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {/* Address card */}
      <Card>
        <CardHeader><CardTitle>Address</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label>Line 1</Label>
            <Input value={addressLine1} onChange={(e) => setAddressLine1(e.target.value)} readOnly={isReadOnly} disabled={isBusy} placeholder="Street address" />
          </div>
          <div className="space-y-1">
            <Label>Line 2</Label>
            <Input value={addressLine2} onChange={(e) => setAddressLine2(e.target.value)} readOnly={isReadOnly} disabled={isBusy} placeholder="Suite, unit, etc." />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>City</Label>
              <Input value={city} onChange={(e) => setCity(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
            <div className="space-y-1">
              <Label>State / Region</Label>
              <Input value={addressState} onChange={(e) => setAddressState(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Postal code</Label>
              <Input value={postalCode} onChange={(e) => setPostalCode(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
            <div className="space-y-1">
              <Label>Country</Label>
              <Input value={country} onChange={(e) => setCountry(e.target.value)} readOnly={isReadOnly} disabled={isBusy} />
            </div>
          </div>
          {!isReadOnly ? (
            <Button onClick={() => void handleSave()} disabled={isBusy || !displayName.trim()}>
              {updateSupplier.isPending ? "Saving…" : "Save changes"}
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {/* Contacts card */}
      <Card>
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>Contacts</CardTitle>
          {canManage && supplier.is_active ? (
            <Button variant="outline" size="sm" onClick={() => { setAddingContact((v) => !v); setContactError("") }}>
              {addingContact ? "Cancel" : "Add contact"}
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {addingContact ? (
            <div className="space-y-3 rounded-lg border border-border p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label>Full name *</Label>
                  <Input value={newContactName} onChange={(e) => setNewContactName(e.target.value)} placeholder="Full name" />
                </div>
                <div className="space-y-1">
                  <Label>Role</Label>
                  <Input value={newContactRole} onChange={(e) => setNewContactRole(e.target.value)} placeholder="e.g. Accounts" />
                </div>
                <div className="space-y-1">
                  <Label>Email</Label>
                  <Input type="email" value={newContactEmail} onChange={(e) => setNewContactEmail(e.target.value)} placeholder="email@example.com" />
                </div>
                <div className="space-y-1">
                  <Label>Phone</Label>
                  <Input value={newContactPhone} onChange={(e) => setNewContactPhone(e.target.value)} placeholder="+1 555 000 0000" />
                </div>
              </div>
              {contactError ? <p className="text-sm text-red-600">{contactError}</p> : null}
              <Button size="sm" onClick={() => void handleAddContact()} disabled={contactMutations.addContact.isPending}>
                {contactMutations.addContact.isPending ? "Saving…" : "Save contact"}
              </Button>
            </div>
          ) : null}

          {contacts.length === 0 && !addingContact ? (
            <p className="text-sm text-muted-foreground">No contacts added yet.</p>
          ) : null}

          <div className="divide-y divide-border">
            {contacts.map((contact) => (
              <div key={contact.id} className="py-4 first:pt-0 last:pb-0">
                {editingContactId === contact.id ? (
                  <div className="space-y-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1">
                        <Label>Full name *</Label>
                        <Input value={editContactName} onChange={(e) => setEditContactName(e.target.value)} />
                      </div>
                      <div className="space-y-1">
                        <Label>Role</Label>
                        <Input value={editContactRole} onChange={(e) => setEditContactRole(e.target.value)} placeholder="e.g. Accounts" />
                      </div>
                      <div className="space-y-1">
                        <Label>Email</Label>
                        <Input type="email" value={editContactEmail} onChange={(e) => setEditContactEmail(e.target.value)} placeholder="email@example.com" />
                      </div>
                      <div className="space-y-1">
                        <Label>Phone</Label>
                        <Input value={editContactPhone} onChange={(e) => setEditContactPhone(e.target.value)} placeholder="+1 555 000 0000" />
                      </div>
                    </div>
                    {contactError ? <p className="text-sm text-red-600">{contactError}</p> : null}
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => void handleSaveEditContact(contact)} disabled={contactMutations.updateContact.isPending}>
                        {contactMutations.updateContact.isPending ? "Saving…" : "Save"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingContactId(null)}>Cancel</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-0.5 text-sm">
                      <p className="font-medium">
                        {contact.full_name}
                        {contact.is_primary ? <span className="ml-2 text-xs text-primary">Primary</span> : null}
                        {!contact.is_active ? <span className="ml-2 text-xs text-muted-foreground">(inactive)</span> : null}
                      </p>
                      {contact.role ? <p className="text-muted-foreground">{contact.role}</p> : null}
                      {contact.email ? <p className="text-muted-foreground">{contact.email}</p> : null}
                      {contact.phone ? <p className="text-muted-foreground">{contact.phone}</p> : null}
                    </div>
                    {canManage ? (
                      <div className="flex shrink-0 flex-wrap gap-2 text-xs">
                        {contact.is_active ? (
                          <button className="text-muted-foreground hover:text-foreground" onClick={() => handleStartEditContact(contact)}>Edit</button>
                        ) : null}
                        {contact.is_active && !contact.is_primary && contacts.filter((c) => c.is_active).length > 1 ? (
                          <button className="text-muted-foreground hover:text-foreground" onClick={() => void contactMutations.setPrimaryContact.mutateAsync(contact.id)}>Set primary</button>
                        ) : null}
                        {contact.is_active ? (
                          <button className="text-red-500 hover:text-red-700" onClick={() => void contactMutations.deactivateContact.mutateAsync(contact.id)}>Deactivate</button>
                        ) : (
                          <button className="text-muted-foreground hover:text-foreground" onClick={() => void contactMutations.reactivateContact.mutateAsync(contact.id)}>Reactivate</button>
                        )}
                        <button className="text-red-500 hover:text-red-700" onClick={() => {
                          if (confirm(`Delete ${contact.full_name}? This cannot be undone.`)) {
                            void contactMutations.deleteContact.mutateAsync(contact.id)
                          }
                        }}>Delete</button>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            ))}
          </div>

          {contactError && !addingContact && editingContactId === null ? (
            <p className="text-sm text-red-600">{contactError}</p>
          ) : null}
        </CardContent>
      </Card>

      {/* Catalog card */}
      <Card>
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>Catalog</CardTitle>
          {canManage && supplier.is_active ? (
            <Button variant="outline" size="sm" onClick={() => { setAddingCatalogItem((v) => !v); setCatalogError("") }}>
              {addingCatalogItem ? "Cancel" : "Add item"}
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {addingCatalogItem ? (
            <div className="space-y-3 rounded-lg border border-border p-4">
              <div className="space-y-1">
                <Label>Item *</Label>
                <Input
                  value={catalogItemQuery}
                  onChange={(e) => { setCatalogItemQuery(e.target.value); setSelectedCatalogItem(null) }}
                  placeholder="Search by name or SKU"
                />
                {selectedCatalogItem ? (
                  <p className="text-xs text-muted-foreground">Selected: {selectedCatalogItem.name} ({selectedCatalogItem.sku})</p>
                ) : catalogItemDebouncedQuery.length >= 2 ? (
                  <div className="rounded-md border border-border bg-background">
                    {catalogItemSearchResults.length === 0 ? (
                      <p className="px-3 py-2 text-sm text-muted-foreground">No items found</p>
                    ) : (
                      catalogItemSearchResults
                        .filter((i) => !catalogItems.some((ci) => ci.org_item.id === i.id))
                        .map((item) => (
                          <button
                            key={item.id}
                            type="button"
                            className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                            onClick={() => { setSelectedCatalogItem(item); setCatalogItemQuery(item.name) }}
                          >
                            <span>{item.name}</span>
                            <span className="text-muted-foreground">{item.sku}</span>
                          </button>
                        ))
                    )}
                  </div>
                ) : null}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label>Unit cost</Label>
                  <Input type="number" min="0" step="0.0001" value={newItemUnitCost} onChange={(e) => setNewItemUnitCost(e.target.value)} placeholder="0.00" />
                </div>
                <div className="space-y-1">
                  <Label>Lead time (days)</Label>
                  <Input type="number" min="0" step="1" value={newItemLeadTime} onChange={(e) => setNewItemLeadTime(e.target.value)} placeholder="7" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={newItemPreferred} onChange={(e) => setNewItemPreferred(e.target.checked)} />
                Preferred supplier for this item
              </label>
              {catalogError ? <p className="text-sm text-red-600">{catalogError}</p> : null}
              <Button size="sm" onClick={() => void handleAddCatalogItem()} disabled={catalogMutations.addItem.isPending}>
                {catalogMutations.addItem.isPending ? "Adding…" : "Add to catalog"}
              </Button>
            </div>
          ) : null}

          {catalogItems.length === 0 && !addingCatalogItem ? (
            <p className="text-sm text-muted-foreground">No items in catalog yet.</p>
          ) : null}

          <div className="divide-y divide-border">
            {catalogItems.map((item) => (
              <div key={item.id} className="py-4 first:pt-0 last:pb-0">
                {editingCatalogItemId === item.id ? (
                  <div className="space-y-3">
                    <p className="text-sm font-medium">{item.org_item.name} <span className="text-muted-foreground font-normal">({item.org_item.sku})</span></p>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1">
                        <Label>Unit cost</Label>
                        <Input type="number" min="0" step="0.0001" value={editItemUnitCost} onChange={(e) => setEditItemUnitCost(e.target.value)} placeholder="0.00" />
                      </div>
                      <div className="space-y-1">
                        <Label>Lead time (days)</Label>
                        <Input type="number" min="0" step="1" value={editItemLeadTime} onChange={(e) => setEditItemLeadTime(e.target.value)} placeholder="7" />
                      </div>
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={editItemPreferred} onChange={(e) => setEditItemPreferred(e.target.checked)} />
                      Preferred supplier for this item
                    </label>
                    {catalogError ? <p className="text-sm text-red-600">{catalogError}</p> : null}
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => void handleSaveCatalogItem(item)} disabled={catalogMutations.updateItem.isPending}>
                        {catalogMutations.updateItem.isPending ? "Saving…" : "Save"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingCatalogItemId(null)}>Cancel</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-0.5 text-sm">
                      <p className="font-medium">
                        {item.org_item.name}
                        {item.is_preferred ? <span className="ml-2 text-xs text-primary">Preferred</span> : null}
                      </p>
                      <p className="text-muted-foreground">{item.org_item.sku}</p>
                      {item.unit_cost ? <p className="text-muted-foreground">Cost: {item.unit_cost}</p> : null}
                      {item.lead_time_days != null ? <p className="text-muted-foreground">Lead time: {item.lead_time_days}d</p> : null}
                    </div>
                    {canManage ? (
                      <div className="flex shrink-0 gap-2 text-xs">
                        <button className="text-muted-foreground hover:text-foreground" onClick={() => handleStartEditCatalogItem(item)}>Edit</button>
                        <button className="text-red-500 hover:text-red-700" onClick={() => void handleRemoveCatalogItem(item)} disabled={catalogMutations.removeItem.isPending}>Remove</button>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            ))}
          </div>

          {catalogError && !addingCatalogItem && editingCatalogItemId === null ? (
            <p className="text-sm text-red-600">{catalogError}</p>
          ) : null}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmDeactivate}
        onOpenChange={setConfirmDeactivate}
        title="Deactivate Supplier"
        description="This supplier will be marked inactive and will no longer appear in new purchase orders."
        confirmLabel="Deactivate"
        onConfirm={() => void handleDeactivate()}
        destructive
      />
      <ConfirmDialog
        open={confirmReactivate}
        onOpenChange={setConfirmReactivate}
        title="Reactivate Supplier"
        description="This supplier will be marked active and will appear in new purchase orders again."
        confirmLabel="Reactivate"
        onConfirm={() => void handleReactivate()}
      />
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-5 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  )
}
