import { apiRequestBlob, getApiErrorMessage } from "@/lib/api"

export async function downloadCsv(
  path: string,
  params: URLSearchParams,
): Promise<{ ok: boolean; error?: string }> {
  const qs = params.toString()
  const fullPath = qs ? `${path}?${qs}` : path

  try {
    const { blob, headers } = await apiRequestBlob(fullPath)

    const disposition = headers.get("content-disposition") ?? ""
    const quoted = /filename="([^"]+)"/.exec(disposition)?.[1]
    const unquoted = !quoted ? /filename=([^\s;]+)/.exec(disposition)?.[1] : undefined
    const filename = quoted ?? unquoted ?? `export-${new Date().toISOString().slice(0, 10)}.csv`

    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    setTimeout(() => URL.revokeObjectURL(url), 100)

    return { ok: true }
  } catch (err) {
    return { ok: false, error: getApiErrorMessage(err, "Export failed. Please try again.") }
  }
}
