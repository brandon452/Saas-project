import { apiRequestBlob, getApiErrorMessage } from "@/lib/api"

export async function downloadPdf(
  path: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const { blob, headers } = await apiRequestBlob(path)

    const disposition = headers.get("content-disposition") ?? ""
    const quoted = /filename="([^"]+)"/.exec(disposition)?.[1]
    const unquoted = !quoted ? /filename=([^\s;]+)/.exec(disposition)?.[1] : undefined
    const filename = quoted ?? unquoted ?? `purchase-order-${new Date().toISOString().slice(0, 10)}.pdf`

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
    return { ok: false, error: getApiErrorMessage(err, "Download failed. Please try again.") }
  }
}
