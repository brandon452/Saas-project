"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Camera, CameraOff, Keyboard } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { makeDebouncer, normalizeToken } from "@/lib/scan/scannerUtils"

interface BarcodeScannerProps {
  onScan: (code: string) => void
  disabled?: boolean
  placeholder?: string
  debounceMs?: number
}

const isDuplicate = makeDebouncer(400)

export function BarcodeScanner({
  onScan,
  disabled = false,
  placeholder = "Scan or type a code…",
  debounceMs = 400,
}: BarcodeScannerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [manualValue, setManualValue] = useState("")
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraSupported, setCameraSupported] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const detectorRef = useRef<unknown>(null)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    setCameraSupported(
      typeof window !== "undefined" &&
        "BarcodeDetector" in window &&
        "mediaDevices" in navigator,
    )
  }, [])

  const handleManualSubmit = useCallback(() => {
    const code = normalizeToken(manualValue)
    if (!code || disabled) return
    if (!isDuplicate(code)) onScan(code)
    setManualValue("")
  }, [manualValue, disabled, onScan])

  const handleManualKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault()
        handleManualSubmit()
      }
    },
    [handleManualSubmit],
  )

  const stopCamera = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    detectorRef.current = null
    setCameraActive(false)
  }, [])

  const startCamera = useCallback(async () => {
    if (!cameraSupported) return
    try {
      // @ts-expect-error BarcodeDetector not in lib types yet
      detectorRef.current = new window.BarcodeDetector({ formats: ["qr_code", "code_128", "ean_13", "code_39"] })
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setCameraActive(true)

      const scan = async () => {
        if (!videoRef.current || !detectorRef.current) return
        try {
          // @ts-expect-error BarcodeDetector not in lib types yet
          const results = await detectorRef.current.detect(videoRef.current)
          for (const result of results) {
            const code = normalizeToken(result.rawValue)
            if (code && !isDuplicate(code)) {
              onScan(code)
              break
            }
          }
        } catch {
          // detection errors are non-fatal
        }
        rafRef.current = requestAnimationFrame(scan)
      }
      rafRef.current = requestAnimationFrame(scan)
    } catch {
      stopCamera()
    }
  }, [cameraSupported, onScan, stopCamera])

  useEffect(() => {
    return stopCamera
  }, [stopCamera])

  useEffect(() => {
    if (!disabled) {
      inputRef.current?.focus()
    }
  }, [disabled])

  return (
    <div className="space-y-3">
      {cameraActive && (
        <div className="relative overflow-hidden rounded-lg border bg-black aspect-video max-h-56">
          <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-48 h-28 border-2 border-white/60 rounded-sm" />
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <Input
          ref={inputRef}
          value={manualValue}
          onChange={(e) => setManualValue(e.target.value)}
          onKeyDown={handleManualKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="font-mono"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="characters"
          spellCheck={false}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleManualSubmit}
          disabled={disabled || !manualValue.trim()}
          title="Submit"
        >
          <Keyboard className="h-4 w-4" />
        </Button>
        {cameraSupported && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={cameraActive ? stopCamera : startCamera}
            disabled={disabled}
            title={cameraActive ? "Stop camera" : "Start camera scan"}
          >
            {cameraActive ? <CameraOff className="h-4 w-4" /> : <Camera className="h-4 w-4" />}
          </Button>
        )}
      </div>
    </div>
  )
}
