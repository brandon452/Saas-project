'use client'

import { useRouter } from 'next/navigation'

import { useOrg } from '../lib/context/org-context'

export function BranchSelector() {
  const { availableBranches, setActiveBranch } = useOrg()
  const router = useRouter()

  function handleSelect(branchId: string) {
    const branch = availableBranches.find((b) => b.id === branchId)
    if (!branch) return
    setActiveBranch(branch)
    router.push('/dashboard')
  }

  return (
    <div>
      <h2>Select Branch</h2>
      {availableBranches.map((branch) => (
        <button key={branch.id} onClick={() => handleSelect(branch.id)} style={{ display: 'block', marginTop: 8 }}>
          {branch.name}
        </button>
      ))}
    </div>
  )
}
