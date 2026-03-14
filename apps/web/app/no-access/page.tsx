import { redirect } from "next/navigation"

export default function LegacyNoAccessPage() {
  redirect("/")
}
