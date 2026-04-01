"use client"

import { useEffect, useState } from "react"

import { ChevronDown, ChevronRight } from "lucide-react"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"
import { useSupplierContactMutations } from "@/lib/hooks/suppliers/useSupplierContactMutations"
import { useSupplierContacts } from "@/lib/hooks/suppliers/useSupplierContacts"
import { useSupplierMutations } from "@/lib/hooks/suppliers/useSupplierMutations"
import { useOrg } from "@/lib/hooks/useOrg"
import type { Supplier, SupplierContact } from "@/lib/types/suppliers"
import { SupplierStatusBadge } from "./SupplierStatusBadge"

interface SupplierPanelProps {
  orgId: string
  supplier: Supplier | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSupplierChange: (supplier: Supplier) => void
}

export function SupplierPanel({
  orgId,
  supplier,
  open,
  onOpenChange,
  onSupplierChange,
}: SupplierPanelProps) {
  const { canAccess } = useOrg()
  const { updateSupplier, deactivateSupplier, reactivateSupplier } = useSupplierMutations(orgId)
  const contactsQuery = useSupplierContacts(orgId, supplier?.id ?? null)
  const contactMutations = useSupplierContactMutations(orgId, supplier?.id ?? 0)

  // Core
  const [displayName, setDisplayName] = useState("")
  const [error, setError] = useState("")
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [reactivateConfirmOpen, setReactivateConfirmOpen] = useState(false)

  // Details section
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [legalName, setLegalName] = useState("")
  const [email, setEmail] = useState("")
  const [phone, setPhone] = useState("")
  const [paymentTermsDays, setPaymentTermsDays] = useState("")
  const [leadTimeDays, setLeadTimeDays] = useState("")
  const [currency, setCurrency] = useState("")
  const [taxId, setTaxId] = useState("")
  const [notes, setNotes] = useState("")

  // Address section
  const [addressOpen, setAddressOpen] = useState(false)
  const [addressLine1, setAddressLine1] = useState("")
  const [addressLine2, setAddressLine2] = useState("")
  const [city, setCity] = useState("")
  const [state, setState] = useState("")
  const [postalCode, setPostalCode] = useState("")
  const [country, setCountry] = useState("")

  // New contact form state
  const [addingContact, setAddingContact] = useState(false)
  const [newContactName, setNewContactName] = useState("")
  const [newContactRole, setNewContactRole] = useState("")
  const [newContactEmail, setNewContactEmail] = useState("")
  const [newContactPhone, setNewContactPhone] = useState("")
  const [contactError, setContactError] = useState("")

  // Edit contact form state
  const [editingContactId, setEditingContactId] = useState<number | null>(null)
  const [editContactName, setEditContactName] = useState("")
  const [editContactRole, setEditContactRole] = useState("")
  const [editContactEmail, setEditContactEmail] = useState("")
  const [editContactPhone, setEditContactPhone] = useState("")

  useEffect(() => {
    setDisplayName(supplier?.display_name ?? "")
    setLegalName(supplier?.legal_name ?? "")
    setEmail(supplier?.email ?? "")
    setPhone(supplier?.phone ?? "")
    setPaymentTermsDays(supplier?.payment_terms_days != null ? String(supplier.payment_terms_days) : "")
    setLeadTimeDays(supplier?.default_lead_time_days != null ? String(supplier.default_lead_time_days) : "")
    setCurrency(supplier?.currency ?? "")
    setTaxId(supplier?.tax_id ?? "")
    setNotes(supplier?.notes ?? "")
    setAddressLine1(supplier?.address_line1 ?? "")
    setAddressLine2(supplier?.address_line2 ?? "")
    setCity(supplier?.city ?? "")
    setState(supplier?.state ?? "")
    setPostalCode(supplier?.postal_code ?? "")
    setCountry(supplier?.country ?? "")
    setError("")
    setAddingContact(false)
    setContactError("")
    setEditingContactId(null)
  }, [supplier])

  const canManage = canAccess(["OWNER", "ADMIN"])
  const isReadOnly = !supplier || !supplier.is_active || !canManage
  const isBusy =
    updateSupplier.isPending || deactivateSupplier.isPending || reactivateSupplier.isPending
  const canSave =
    !!supplier &&
    supplier.is_active &&
    canManage &&
    displayName.trim().length > 0 &&
    !isBusy

  async function handleSave() {
    if (!supplier || !canSave) return
    try {
      setError("")
      const updated = await updateSupplier.mutateAsync({
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
          state: state.trim(),
          postal_code: postalCode.trim(),
          country: country.trim(),
        },
      })
      onSupplierChange(updated)
    } catch (err) {
      const message = err instanceof Error ? err.message : ""
      if (message.includes("403")) {
        setError("You do not have permission to update suppliers.")
      } else if (message.includes("400")) {
        setError("Supplier name is invalid or already exists.")
      } else {
        setError("Could not save supplier changes.")
      }
    }
  }

  async function handleDeactivate() {
    if (!supplier) return
    try {
      setError("")
      const updated = await deactivateSupplier.mutateAsync(supplier.id)
      onSupplierChange(updated)
    } catch (err) {
      const message = err instanceof Error ? err.message : ""
      setError(message.includes("403") ? "You do not have permission to deactivate suppliers." : "Could not deactivate supplier.")
    }
  }

  async function handleReactivate() {
    if (!supplier) return
    try {
      setError("")
      const updated = await reactivateSupplier.mutateAsync(supplier.id)
      onSupplierChange(updated)
    } catch (err) {
      const message = err instanceof Error ? err.message : ""
      setError(message.includes("403") ? "You do not have permission to reactivate suppliers." : "Could not reactivate supplier.")
    }
  }

  async function handleAddContact() {
    if (!newContactName.trim()) {
      setContactError("Contact name is required.")
      return
    }
    try {
      setContactError("")
      await contactMutations.addContact.mutateAsync({
        full_name: newContactName.trim(),
        role: newContactRole.trim() || undefined,
        email: newContactEmail.trim() || undefined,
        phone: newContactPhone.trim() || undefined,
      })
      setAddingContact(false)
      setContactError("")
      setNewContactName("")
      setNewContactRole("")
      setNewContactEmail("")
      setNewContactPhone("")
    } catch {
      setContactError("Could not add contact.")
    }
  }

  async function handleSetPrimary(contact: SupplierContact) {
    try {
      await contactMutations.setPrimaryContact.mutateAsync(contact.id)
    } catch {
      setContactError("Could not set primary contact.")
    }
  }

  async function handleDeactivateContact(contact: SupplierContact) {
    try {
      await contactMutations.deactivateContact.mutateAsync(contact.id)
    } catch {
      setContactError("Could not deactivate contact.")
    }
  }

  async function handleReactivateContact(contact: SupplierContact) {
    try {
      await contactMutations.reactivateContact.mutateAsync(contact.id)
    } catch {
      setContactError("Could not reactivate contact.")
    }
  }

  async function handleDeleteContact(contact: SupplierContact) {
    if (!confirm(`Delete ${contact.full_name}? This cannot be undone.`)) return
    try {
      await contactMutations.deleteContact.mutateAsync(contact.id)
    } catch {
      setContactError("Could not delete contact.")
    }
  }

  function handleStartEdit(contact: SupplierContact) {
    setEditingContactId(contact.id)
    setEditContactName(contact.full_name)
    setEditContactRole(contact.role ?? "")
    setEditContactEmail(contact.email ?? "")
    setEditContactPhone(contact.phone ?? "")
    setContactError("")
    setAddingContact(false)
  }

  function handleCancelEdit() {
    setEditingContactId(null)
    setContactError("")
  }

  async function handleSaveEdit(contact: SupplierContact) {
    if (!editContactName.trim()) {
      setContactError("Contact name is required.")
      return
    }
    try {
      setContactError("")
      await contactMutations.updateContact.mutateAsync({
        contactId: contact.id,
        data: {
          full_name: editContactName.trim(),
          role: editContactRole.trim() || "",
          email: editContactEmail.trim() || "",
          phone: editContactPhone.trim() || "",
        },
      })
      setEditingContactId(null)
    } catch {
      setContactError("Could not save contact.")
    }
  }

  const contacts = contactsQuery.data ?? []

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="overflow-y-auto">
          {supplier ? (
            <div className="space-y-6">
              <SheetHeader>
                <SheetTitle>{supplier.display_name}</SheetTitle>
                <SheetDescription>
                  <span className="flex items-center gap-2">
                    <SupplierStatusBadge isActive={supplier.is_active} />
                    {supplier.code ? (
                      <span className="text-xs text-muted-foreground">{supplier.code}</span>
                    ) : null}
                  </span>
                </SheetDescription>
              </SheetHeader>

              {/* Name */}
              <div className="space-y-2">
                <Label htmlFor="supplier-panel-name">Name</Label>
                <Input
                  id="supplier-panel-name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  readOnly={isReadOnly}
                  disabled={isBusy}
                />
              </div>

              {/* Details section */}
              <div className="border-t border-border pt-4 space-y-3">
                <button
                  className="flex w-full items-center justify-between text-sm font-medium"
                  onClick={() => setDetailsOpen((v) => !v)}
                >
                  Details
                  {detailsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>

                {detailsOpen ? (
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Legal name</Label>
                      <Input
                        value={legalName}
                        onChange={(e) => setLegalName(e.target.value)}
                        placeholder="Legal entity name"
                        readOnly={isReadOnly}
                        disabled={isBusy}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Email</Label>
                        <Input
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          placeholder="supplier@example.com"
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Phone</Label>
                        <Input
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          placeholder="+1 555 000 0000"
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Payment terms (days)</Label>
                        <Input
                          type="number"
                          min={0}
                          value={paymentTermsDays}
                          onChange={(e) => setPaymentTermsDays(e.target.value)}
                          placeholder="30"
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Lead time (days)</Label>
                        <Input
                          type="number"
                          min={0}
                          value={leadTimeDays}
                          onChange={(e) => setLeadTimeDays(e.target.value)}
                          placeholder="7"
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Currency</Label>
                        <Input
                          value={currency}
                          onChange={(e) => setCurrency(e.target.value)}
                          placeholder="USD"
                          maxLength={3}
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Tax ID</Label>
                        <Input
                          value={taxId}
                          onChange={(e) => setTaxId(e.target.value)}
                          placeholder="VAT / EIN"
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Notes</Label>
                      <Textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="Any notes about this supplier..."
                        readOnly={isReadOnly}
                        disabled={isBusy}
                        rows={3}
                      />
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Address section */}
              <div className="border-t border-border pt-4 space-y-3">
                <button
                  className="flex w-full items-center justify-between text-sm font-medium"
                  onClick={() => setAddressOpen((v) => !v)}
                >
                  Address
                  {addressOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>

                {addressOpen ? (
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Line 1</Label>
                      <Input
                        value={addressLine1}
                        onChange={(e) => setAddressLine1(e.target.value)}
                        placeholder="Street address"
                        readOnly={isReadOnly}
                        disabled={isBusy}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Line 2</Label>
                      <Input
                        value={addressLine2}
                        onChange={(e) => setAddressLine2(e.target.value)}
                        placeholder="Suite, unit, etc."
                        readOnly={isReadOnly}
                        disabled={isBusy}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">City</Label>
                        <Input
                          value={city}
                          onChange={(e) => setCity(e.target.value)}
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">State / Region</Label>
                        <Input
                          value={state}
                          onChange={(e) => setState(e.target.value)}
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Postal code</Label>
                        <Input
                          value={postalCode}
                          onChange={(e) => setPostalCode(e.target.value)}
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Country</Label>
                        <Input
                          value={country}
                          onChange={(e) => setCountry(e.target.value)}
                          readOnly={isReadOnly}
                          disabled={isBusy}
                        />
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="space-y-2 text-xs text-muted-foreground border-t border-border pt-4">
                <p>Created: {new Date(supplier.created_at).toLocaleDateString()}</p>
                <p>Updated: {new Date(supplier.updated_at).toLocaleDateString()}</p>
              </div>

              {error ? <p className="text-sm text-red-600">{error}</p> : null}

              {!isReadOnly ? (
                <div className="flex gap-3">
                  <Button onClick={handleSave} disabled={!canSave}>
                    {updateSupplier.isPending ? "Saving..." : "Save"}
                  </Button>
                  <Button
                    variant="ghost"
                    className="text-red-600 hover:text-red-700"
                    disabled={isBusy}
                    onClick={() => setConfirmOpen(true)}
                  >
                    Deactivate
                  </Button>
                </div>
              ) : null}

              {supplier && !supplier.is_active && canManage ? (
                <Button
                  variant="outline"
                  disabled={isBusy}
                  onClick={() => setReactivateConfirmOpen(true)}
                >
                  Reactivate
                </Button>
              ) : null}

              {/* Contacts section */}
              <div className="space-y-3 border-t border-border pt-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">Contacts</p>
                  {canManage && supplier.is_active ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => { setAddingContact((v) => !v); setContactError("") }}
                    >
                      {addingContact ? "Cancel" : "Add contact"}
                    </Button>
                  ) : null}
                </div>

                {addingContact ? (
                  <div className="space-y-3 rounded-lg border border-border p-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Full name *</Label>
                      <Input
                        value={newContactName}
                        onChange={(e) => setNewContactName(e.target.value)}
                        placeholder="Full name"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Role</Label>
                      <Input
                        value={newContactRole}
                        onChange={(e) => setNewContactRole(e.target.value)}
                        placeholder="e.g. Accounts"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Email</Label>
                      <Input
                        type="email"
                        value={newContactEmail}
                        onChange={(e) => setNewContactEmail(e.target.value)}
                        placeholder="email@example.com"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Phone</Label>
                      <Input
                        value={newContactPhone}
                        onChange={(e) => setNewContactPhone(e.target.value)}
                        placeholder="+1 555 000 0000"
                      />
                    </div>
                    {contactError ? <p className="text-sm text-red-600">{contactError}</p> : null}
                    <Button
                      size="sm"
                      onClick={() => void handleAddContact()}
                      disabled={contactMutations.addContact.isPending}
                    >
                      Save contact
                    </Button>
                  </div>
                ) : null}

                {contacts.length === 0 && !addingContact ? (
                  <p className="text-sm text-muted-foreground">No contacts added yet.</p>
                ) : null}

                {contacts.map((contact) => (
                  <div
                    key={contact.id}
                    className="rounded-lg border border-border p-3 space-y-1 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {contact.full_name}
                        {contact.is_primary ? (
                          <span className="ml-2 text-xs text-primary">Primary</span>
                        ) : null}
                        {!contact.is_active ? (
                          <span className="ml-2 text-xs text-muted-foreground">(inactive)</span>
                        ) : null}
                      </span>
                      {canManage ? (
                        <div className="flex gap-2">
                          {editingContactId === contact.id ? (
                            <button
                              className="text-xs text-muted-foreground hover:text-foreground"
                              onClick={handleCancelEdit}
                            >
                              Cancel
                            </button>
                          ) : (
                            <>
                              {contact.is_active ? (
                                <button
                                  className="text-xs text-muted-foreground hover:text-foreground"
                                  onClick={() => handleStartEdit(contact)}
                                >
                                  Edit
                                </button>
                              ) : null}
                              {contact.is_active && !contact.is_primary && contacts.filter((c) => c.is_active).length > 1 ? (
                                <button
                                  className="text-xs text-muted-foreground hover:text-foreground"
                                  onClick={() => void handleSetPrimary(contact)}
                                >
                                  Set primary
                                </button>
                              ) : null}
                              {contact.is_active ? (
                                <button
                                  className="text-xs text-red-500 hover:text-red-700"
                                  onClick={() => void handleDeactivateContact(contact)}
                                >
                                  Deactivate
                                </button>
                              ) : (
                                <button
                                  className="text-xs text-muted-foreground hover:text-foreground"
                                  onClick={() => void handleReactivateContact(contact)}
                                >
                                  Reactivate
                                </button>
                              )}
                              <button
                                className="text-xs text-red-500 hover:text-red-700"
                                onClick={() => void handleDeleteContact(contact)}
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </div>
                      ) : null}
                    </div>

                    {editingContactId === contact.id ? (
                      <div className="space-y-3 pt-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Full name *</Label>
                          <Input
                            value={editContactName}
                            onChange={(e) => setEditContactName(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Role</Label>
                          <Input
                            value={editContactRole}
                            onChange={(e) => setEditContactRole(e.target.value)}
                            placeholder="e.g. Accounts"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Email</Label>
                          <Input
                            type="email"
                            value={editContactEmail}
                            onChange={(e) => setEditContactEmail(e.target.value)}
                            placeholder="email@example.com"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Phone</Label>
                          <Input
                            value={editContactPhone}
                            onChange={(e) => setEditContactPhone(e.target.value)}
                            placeholder="+1 555 000 0000"
                          />
                        </div>
                        {contactError ? <p className="text-sm text-red-600">{contactError}</p> : null}
                        <Button
                          size="sm"
                          onClick={() => void handleSaveEdit(contact)}
                          disabled={contactMutations.updateContact.isPending}
                        >
                          {contactMutations.updateContact.isPending ? "Saving..." : "Save"}
                        </Button>
                      </div>
                    ) : (
                      <>
                        {contact.role ? <p className="text-muted-foreground">{contact.role}</p> : null}
                        {contact.email ? <p className="text-muted-foreground">{contact.email}</p> : null}
                        {contact.phone ? <p className="text-muted-foreground">{contact.phone}</p> : null}
                      </>
                    )}
                  </div>
                ))}

                {contactError && !addingContact && editingContactId === null ? (
                  <p className="text-sm text-red-600">{contactError}</p>
                ) : null}
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Deactivate Supplier"
        description="This supplier will be marked inactive and will no longer appear in new purchase orders."
        confirmLabel="Deactivate"
        onConfirm={() => {
          void handleDeactivate()
        }}
        destructive
      />

      <ConfirmDialog
        open={reactivateConfirmOpen}
        onOpenChange={setReactivateConfirmOpen}
        title="Reactivate Supplier"
        description="This supplier will be marked active and will appear in new purchase orders again."
        confirmLabel="Reactivate"
        onConfirm={() => {
          void handleReactivate()
        }}
      />
    </>
  )
}
