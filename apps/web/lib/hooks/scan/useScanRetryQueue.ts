"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { getCsrfHeader } from "@/lib/csrf"
import { enqueue, dequeue, getAll, update } from "@/lib/scan/retryQueue"
import { isNonRetryableStatus, generateIdempotencyKey } from "@/lib/scan/scannerUtils"
import type { RetryQueueEntry } from "@/lib/types/scan"

const MAX_ATTEMPTS = 5
const BACKOFF_BASE_MS = 1500

function backoffMs(attempt: number) {
  return Math.min(BACKOFF_BASE_MS * 2 ** attempt, 30_000)
}

export function useScanRetryQueue() {
  const [entries, setEntries] = useState<RetryQueueEntry[]>([])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const refreshEntries = useCallback(async () => {
    const all = await getAll()
    setEntries(all)
  }, [])

  useEffect(() => {
    refreshEntries()
  }, [refreshEntries])

  const addEntry = useCallback(
    async (
      workflow: RetryQueueEntry["workflow"],
      endpoint: string,
      method: string,
      payload: unknown,
    ): Promise<string> => {
      const entry: RetryQueueEntry = {
        id: generateIdempotencyKey(),
        idempotencyKey: generateIdempotencyKey(),
        workflow,
        payload,
        endpoint,
        method,
        attemptCount: 0,
        lastAttemptAt: null,
        createdAt: Date.now(),
        nonRetryable: false,
        error: null,
      }
      await enqueue(entry)
      await refreshEntries()
      return entry.idempotencyKey
    },
    [refreshEntries],
  )

  const attemptEntry = useCallback(
    async (entry: RetryQueueEntry) => {
      const updated: RetryQueueEntry = {
        ...entry,
        attemptCount: entry.attemptCount + 1,
        lastAttemptAt: Date.now(),
      }
      await update(updated)

      try {
        const res = await fetch(`/api/${entry.endpoint}`, {
          method: entry.method,
          headers: { "Content-Type": "application/json", ...getCsrfHeader() },
          body: JSON.stringify(entry.payload),
        })

        if (res.ok) {
          await dequeue(entry.id)
          await refreshEntries()
          return
        }

        const isNonRetryable = isNonRetryableStatus(res.status)
        const errText = await res.text().catch(() => res.statusText)
        await update({ ...updated, nonRetryable: isNonRetryable, error: errText })
        await refreshEntries()
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Network error"
        await update({ ...updated, error: msg })
        await refreshEntries()

        if (updated.attemptCount < MAX_ATTEMPTS) {
          timerRef.current = setTimeout(
            () => attemptEntry(updated),
            backoffMs(updated.attemptCount),
          )
        }
      }
    },
    [refreshEntries],
  )

  const retryAll = useCallback(async () => {
    const all = await getAll()
    for (const entry of all) {
      if (!entry.nonRetryable && entry.attemptCount < MAX_ATTEMPTS) {
        await attemptEntry(entry)
      }
    }
  }, [attemptEntry])

  const dismissEntry = useCallback(
    async (id: string) => {
      await dequeue(id)
      await refreshEntries()
    },
    [refreshEntries],
  )

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const pendingCount = entries.filter((e) => !e.nonRetryable && e.attemptCount < MAX_ATTEMPTS).length
  const failedCount = entries.filter((e) => e.nonRetryable || e.attemptCount >= MAX_ATTEMPTS).length

  return { entries, pendingCount, failedCount, addEntry, attemptEntry, retryAll, dismissEntry }
}
