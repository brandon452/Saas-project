"use client"

import Link from "next/link"
import { useParams } from "next/navigation"

import { StockTakeHeader } from "@/components/stock-takes/StockTakeHeader"
import { StockTakeLinesTable } from "@/components/stock-takes/StockTakeLinesTable"
import { StockTakeSummaryCards } from "@/components/stock-takes/StockTakeSummaryCards"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useStockTakeDetail } from "@/lib/hooks/stock-takes/useStockTakeDetail"
import { useOrg } from "@/lib/hooks/useOrg"

export default function StockTakeDetailPage() {
  const params = useParams<{ stockTakeId: string }>()
  const { orgId } = useOrg()
  const stockTakeId = params?.stockTakeId ?? ""
  const stockTakeQuery = useStockTakeDetail(orgId, stockTakeId)

  if (stockTakeQuery.isLoading) {
    return <StockTakeDetailSkeleton />
  }

  const errorMessage = stockTakeQuery.error instanceof Error ? stockTakeQuery.error.message : ""

  if (errorMessage.includes("404")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Stock take not found</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/stock-takes`} className="text-sm text-primary">
            Back to stock takes
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Access denied</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/stock-takes`} className="text-sm text-primary">
            Back to stock takes
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (!stockTakeQuery.data || stockTakeQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load stock take</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Try loading the page again.</p>
          <Button onClick={() => void stockTakeQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const stockTake = stockTakeQuery.data

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-sm text-muted-foreground">
          <Link href={`/orgs/${orgId}/stock-takes`} className="hover:text-foreground">
            Stock Takes
          </Link>{" "}
          / {stockTake.id}
        </div>
      </div>

      <StockTakeHeader
        orgId={orgId}
        stockTake={stockTake}
        onChanged={async () => {
          await stockTakeQuery.refetch()
        }}
      />

      <StockTakeSummaryCards lines={stockTake.lines} />

      <Card>
        <CardHeader>
          <CardTitle>Count Lines</CardTitle>
        </CardHeader>
        <CardContent>
          <StockTakeLinesTable
            orgId={orgId}
            stockTakeId={stockTake.id}
            status={stockTake.status}
            lines={stockTake.lines}
            onSaved={async () => {
              await stockTakeQuery.refetch()
            }}
          />
        </CardContent>
      </Card>
    </div>
  )
}

function StockTakeDetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
