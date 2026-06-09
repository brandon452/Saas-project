# Modularity Boundary Inventory

## branches.api Symbols

- `Branch`
- `branches_for_org(organization)`
- `get_branch_for_org(branch_id, organization)`
- `get_branch_for_org_or_none(branch_id, organization)`
- `get_branch_any_org_or_none(branch_id)`
- `network_branches_for_org(organization)`

## Scoped Caller Map

- `branches.views`: branch list/detail and network branch querysets use `branches.api`.
- `branches.middleware`: branch header resolution uses `branches.api`.
- `tenancy.middleware`: branch context resolution uses `branches.api`.
- `tenancy.invitation_views`: staff assigned-branch validation uses `branches.api`.
- `inventory.api`: scan branch resolution uses `branches.api`.
- `inventory.views`: branch item catalog validation uses `branches.api`.
- `inventory.serializers`: branch validation uses `branches.api`.
- `goods_receipts.views`: direct receipt branch context lookup uses `branches.api`.
- `quick_sales.serializers`: branch queryset uses `branches.api`.

Direct `branches.models` imports remain allowed for model foreign keys, tests, and unrewired non-scoped legacy callers until a later boundary cleanup slice.
