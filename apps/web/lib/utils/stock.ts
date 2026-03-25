export function formatQuantity(value: string): string {
  const n = Number(value)
  return Number.isFinite(n) ? n.toString() : value
}
