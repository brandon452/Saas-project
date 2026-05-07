"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { downloadCsv } from "@/lib/utils/download-csv"

type ExportStatus = "idle" | "loading" | "success" | "error"

export function useExportCsv() {
  const [status, setStatus] = useState<ExportStatus>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlightRef = useRef(false)

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      inFlightRef.current = false
    },
    [],
  )

  const trigger = useCallback(async (path: string, params: URLSearchParams) => {
    if (inFlightRef.current) return
    inFlightRef.current = true

    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    setErrorMessage(null)
    setStatus("loading")

    try {
      const result = await downloadCsv(path, params)
      if (result.ok) {
        setStatus("success")
        timerRef.current = setTimeout(() => setStatus("idle"), 1500)
      } else {
        setErrorMessage(result.error ?? "Export failed.")
        setStatus("error")
      }
    } finally {
      inFlightRef.current = false
    }
  }, [])

  return { exportStatus: status, exportError: errorMessage, triggerExport: trigger }
}
