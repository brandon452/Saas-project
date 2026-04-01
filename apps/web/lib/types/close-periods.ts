export type ClosePeriodStatus = "OPEN" | "CLOSING" | "CLOSED"

export interface ClosePeriodUser {
  id: number
  username: string
}

export interface ClosePeriod {
  id: string
  start_date: string // YYYY-MM-DD
  end_date: string // YYYY-MM-DD
  status: ClosePeriodStatus
  notes: string
  closed_at: string | null
  closed_by: ClosePeriodUser | null
  reopened_at: string | null
  reopened_by: ClosePeriodUser | null
}

export interface CloseSnapshot {
  id: string
  branch: {
    id: string
    name: string
    code: string
  }
  item: {
    id: string
    name: string
    sku: string
  }
  quantity_on_hand: string
  average_unit_cost: string | null
  latest_unit_cost: string | null
  average_valuation: string | null
  latest_valuation: string | null
  valuation_basis: string
}
