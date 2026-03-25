import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { StockTakeLine } from "@/lib/types/stock-takes"

export function StockTakeSummaryCards({ lines }: { lines: StockTakeLine[] }) {
  const totalLines = lines.length
  const countedLines = lines.filter((line) => line.counted_quantity !== null).length
  const uncountedLines = totalLines - countedLines
  const varianceLines = lines.filter(
    (line) => line.variance_preview !== null && Number(line.variance_preview) !== 0,
  ).length

  const cards = [
    { label: "Total lines", value: totalLines },
    { label: "Counted lines", value: countedLines },
    { label: "Uncounted lines", value: uncountedLines },
    { label: "Variance lines", value: varianceLines },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">{card.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{card.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
