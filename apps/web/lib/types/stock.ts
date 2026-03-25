export interface StockBranch {
  id: string
  name: string
  code: string
}

export interface StockItem {
  id: string
  name: string
  sku: string
}

export interface StockOnHand {
  id: string
  organization: string
  branch: StockBranch
  item: StockItem
  quantity: string
}

export interface StockOnHandListResponse {
  results: StockOnHand[]
  next: string | null
  previous: string | null
  count: number
}

export interface StockItemSearchResult {
  id: string
  name: string
  sku: string
}

export interface StockItemSearchResponse {
  results: StockItemSearchResult[]
  next: string | null
}
