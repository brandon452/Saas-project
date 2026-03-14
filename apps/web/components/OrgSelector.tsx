'use client'

import { useRouter } from 'next/navigation'

import { useOrg } from '../lib/context/org-context'

export function OrgSelector() {
  const { availableOrgs, setActiveOrg } = useOrg()
  const router = useRouter()

  function handleSelect(orgId: string) {
    const org = availableOrgs.find((o) => o.id === orgId)
    if (!org) return
    setActiveOrg(org)
    router.push('/select-branch')
  }

  return (
    <div>
      <h2>Select Organization</h2>
      {availableOrgs.map((org) => (
        <button key={org.id} onClick={() => handleSelect(org.id)} style={{ display: 'block', marginTop: 8 }}>
          {org.name}
        </button>
      ))}
    </div>
  )
}
