export interface Branch {
  id: string
  name: string
  code: string
  organization: string
}

export interface CreateBranchPayload {
  name: string
  code: string
}

export interface UpdateBranchPayload {
  name: string
  code: string
}
