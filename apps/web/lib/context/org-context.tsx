'use client'

import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

export interface Org {
  id: string
  name: string
  slug: string
}

export interface Branch {
  id: string
  name: string
  code: string
}

interface OrgContextType {
  activeOrg: Org | null
  activeBranch: Branch | null
  availableOrgs: Org[]
  availableBranches: Branch[]
  setAvailableOrgs: (orgs: Org[]) => void
  setAvailableBranches: (branches: Branch[]) => void
  setActiveOrg: (org: Org | null) => void
  setActiveBranch: (branch: Branch | null) => void
}

const OrgContext = createContext<OrgContextType>({
  activeOrg: null,
  activeBranch: null,
  availableOrgs: [],
  availableBranches: [],
  setAvailableOrgs: () => {},
  setAvailableBranches: () => {},
  setActiveOrg: () => {},
  setActiveBranch: () => {},
})

export function OrgProvider({ children }: { children: ReactNode }) {
  const [activeOrg, setActiveOrgState] = useState<Org | null>(null)
  const [activeBranch, setActiveBranchState] = useState<Branch | null>(null)
  const [availableOrgs, setAvailableOrgs] = useState<Org[]>([])
  const [availableBranches, setAvailableBranches] = useState<Branch[]>([])

  function setActiveOrg(org: Org | null) {
    setActiveOrgState(org)
    setActiveBranchState(null)
  }

  return (
    <OrgContext.Provider
      value={{
        activeOrg,
        activeBranch,
        availableOrgs,
        availableBranches,
        setAvailableOrgs,
        setAvailableBranches,
        setActiveOrg,
        setActiveBranch: setActiveBranchState,
      }}
    >
      {children}
    </OrgContext.Provider>
  )
}

export function useOrg() {
  return useContext(OrgContext)
}
